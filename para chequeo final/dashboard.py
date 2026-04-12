from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import EventoPago, PagoProgramado, PagoReal


# ==================================================
# HELPERS INTERNOS
# ==================================================


def _sumar_monto(qs):
    return qs.aggregate(
        total=Coalesce(
            Sum('monto'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )['total']



def _sumar_relacion(objetos, attr='monto'):
    total = Decimal('0.00')
    for obj in objetos:
        total += Decimal(getattr(obj, attr, 0) or 0)
    return total



def _pagos_programados_operativos_qs():
    return PagoProgramado.objects.filter(activo=True)



def _eventos_operativos_qs():
    return EventoPago.objects.filter(pago__activo=True)



def _pagos_reales_operativos_qs():
    return PagoReal.objects.filter(pago__activo=True)



def _unidad_pago_info(pago):
    if not pago:
        return {
            'unidad_negocio': 'otros',
            'unidad_negocio_label': 'Otros',
        }

    codigo = pago.unidad_negocio_codigo_actual() if hasattr(pago, 'unidad_negocio_codigo_actual') else (getattr(pago, 'unidad_negocio', None) or 'otros')
    label = pago.unidad_negocio_label_actual() if hasattr(pago, 'unidad_negocio_label_actual') else 'Otros'

    return {
        'unidad_negocio': codigo or 'otros',
        'unidad_negocio_label': label or 'Otros',
    }



def _modo_programacion_info(pago):
    modo = getattr(pago, 'modo_programacion', 'CUOTAS') or 'CUOTAS'
    try:
        modo_label = pago.get_modo_programacion_display()
    except Exception:
        modo_label = modo.title()

    try:
        categoria = pago.categoria_recurrente_codigo_actual() if hasattr(pago, 'categoria_recurrente_codigo_actual') else (getattr(pago, 'categoria_recurrente', '') or '')
    except Exception:
        categoria = getattr(pago, 'categoria_recurrente', '') or ''
    try:
        categoria_label = pago.categoria_recurrente_label_actual() if categoria and hasattr(pago, 'categoria_recurrente_label_actual') else ''
    except Exception:
        categoria_label = categoria.replace('_', ' ').title() if categoria else ''

    return {
        'modo_programacion': modo,
        'modo_programacion_label': modo_label,
        'categoria_recurrente': categoria,
        'categoria_recurrente_label': categoria_label,
    }



def _resumen_compromiso_alerta(pago, eventos_pendientes):
    eventos_pendientes = sorted(eventos_pendientes, key=lambda e: e.fecha)
    primer_evento = eventos_pendientes[0]

    eventos_todos = list(pago.eventos.all()) if hasattr(pago, '_prefetched_objects_cache') and 'eventos' in pago._prefetched_objects_cache else list(pago.eventos.all())
    pagos_realizados = list(pago.pagos_realizados.all()) if hasattr(pago, '_prefetched_objects_cache') and 'pagos_realizados' in pago._prefetched_objects_cache else list(pago.pagos_realizados.all())

    total_compromiso = _sumar_relacion(eventos_todos)
    if total_compromiso <= 0:
        if hasattr(pago, 'es_recurrente') and (pago.es_recurrente() or pago.es_unico()):
            total_compromiso = Decimal(pago.monto_evento_recurrente() or 0)
        else:
            total_compromiso = Decimal(pago.total_cuotas or 0) * Decimal(pago.monto or 0)

    pagado_acumulado = _sumar_relacion(pagos_realizados)
    saldo_pendiente_real = total_compromiso - pagado_acumulado
    if saldo_pendiente_real < 0:
        saldo_pendiente_real = Decimal('0.00')

    es_recurrente = hasattr(pago, 'es_recurrente') and pago.es_recurrente()
    es_unico = hasattr(pago, 'es_unico') and pago.es_unico()

    if es_recurrente or es_unico:
        cuota_operativa = _resolver_cuota_operativa(
            pago=pago,
            eventos_todos=eventos_todos,
            pagado_real=pagado_acumulado,
            total_compromiso=total_compromiso,
            saldo_real=saldo_pendiente_real,
        )
        total_compromiso = _to_decimal(cuota_operativa.get('monto_cuota_actual') or 0)
        pagado_acumulado = _to_decimal(cuota_operativa.get('abonado_cuota_actual') or 0)
        saldo_pendiente_real = _to_decimal(cuota_operativa.get('saldo_cuota_actual') or 0)

    if saldo_pendiente_real <= 0:
        estado_compromiso = 'PAGADO'
        porcentaje_pagado = 100
    elif pagado_acumulado > 0 and total_compromiso > 0:
        estado_compromiso = 'PARCIAL'
        porcentaje_pagado = round((pagado_acumulado / total_compromiso) * 100, 2)
    else:
        estado_compromiso = 'PENDIENTE'
        porcentaje_pagado = 0

    return {
        'pago_id': pago.id,
        'nombre': pago.nombre,
        'tipo': pago.tipo,
        **_modo_programacion_info(pago),
        'unidad_negocio': _unidad_pago_info(pago)['unidad_negocio'],
        'unidad_negocio_label': _unidad_pago_info(pago)['unidad_negocio_label'],
        'fecha': primer_evento.fecha,
        'monto_evento': Decimal(primer_evento.monto or 0),
        'pagado_acumulado': pagado_acumulado,
        'saldo_pendiente_real': saldo_pendiente_real,
        'total_compromiso': total_compromiso,
        'estado_compromiso': estado_compromiso,
        'porcentaje_pagado': porcentaje_pagado,
        'cantidad_eventos_pendientes': len(eventos_pendientes),
        'cantidad_eventos_vencidos': sum(1 for e in eventos_pendientes if e.fecha < timezone.now().date()),
        'descripcion': pago.descripcion or '',
    }



def _agrupar_compromisos_por_alerta(limite=None):
    hoy = timezone.now().date()
    fin_3 = hoy + timedelta(days=3)
    fin_7 = hoy + timedelta(days=7)

    compromisos = (
        _pagos_programados_operativos_qs()
        .filter(eventos__estado='pendiente')
        .prefetch_related('eventos', 'pagos_realizados')
        .distinct()
        .order_by('nombre', 'id')
    )

    grupos = {
        'vencidas': [],
        'vencen_hoy': [],
        'urgentes': [],
        'proximas': [],
    }

    for pago in compromisos:
        eventos_pendientes = [e for e in pago.eventos.all() if e.estado == 'pendiente']
        if not eventos_pendientes:
            continue

        eventos_pendientes.sort(key=lambda e: e.fecha)
        primer_evento = eventos_pendientes[0]

        if primer_evento.fecha < hoy:
            bucket = 'vencidas'
        elif primer_evento.fecha == hoy:
            bucket = 'vencen_hoy'
        elif primer_evento.fecha <= fin_3:
            bucket = 'urgentes'
        elif primer_evento.fecha <= fin_7:
            bucket = 'proximas'
        else:
            continue

        grupos[bucket].append(_resumen_compromiso_alerta(pago, eventos_pendientes))

    for key in grupos.keys():
        grupos[key].sort(key=lambda item: (item['fecha'], -item['saldo_pendiente_real'], item['nombre'].lower()))
        if limite is not None:
            grupos[key] = grupos[key][:limite]

    return grupos



def _sumar_saldos(items):
    total = Decimal('0.00')
    for item in items:
        total += Decimal(item.get('saldo_pendiente_real') or 0)
    return total



def _to_decimal(value):
    if value in (None, '', False):
        return Decimal('0.00')
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0.00')



def _estado_cuota_visual(fecha_cuota, saldo_cuota, abonado_cuota):
    hoy = timezone.now().date()
    saldo_cuota = _to_decimal(saldo_cuota)
    abonado_cuota = _to_decimal(abonado_cuota)

    if saldo_cuota <= 0:
        return 'Pagada', 'success'

    if fecha_cuota and fecha_cuota < hoy:
        return ('Vencida parcial', 'danger') if abonado_cuota > 0 else ('Vencida', 'danger')

    if fecha_cuota and fecha_cuota == hoy:
        return ('Hoy parcial', 'warning') if abonado_cuota > 0 else ('Hoy', 'warning')

    if abonado_cuota > 0:
        return 'Parcial', 'warning'

    return 'Pendiente', 'danger'



def _distribuir_pagado_en_eventos(eventos, pagado_real):
    restante = _to_decimal(pagado_real)
    detalle = []

    for idx, evento in enumerate(eventos, start=1):
        monto_evento = _to_decimal(getattr(evento, 'monto', 0))
        abonado_evento = min(monto_evento, restante)
        saldo_evento = monto_evento - abonado_evento
        if saldo_evento < 0:
            saldo_evento = Decimal('0.00')

        detalle.append({
            'evento': evento,
            'numero_cuota': idx,
            'fecha_cuota': getattr(evento, 'fecha', None),
            'monto_cuota': monto_evento,
            'abonado_cuota': abonado_evento,
            'saldo_cuota': saldo_evento,
            'estado_evento': getattr(evento, 'estado', None),
        })

        restante -= abonado_evento
        if restante < 0:
            restante = Decimal('0.00')

    return detalle




def _resolver_cuota_operativa(pago, eventos_todos, pagado_real, total_compromiso, saldo_real):
    eventos_ordenados = sorted(eventos_todos, key=lambda e: ((getattr(e, 'fecha', None) or timezone.now().date()), e.id))
    es_recurrente = hasattr(pago, 'es_recurrente') and pago.es_recurrente()
    es_unico = hasattr(pago, 'es_unico') and pago.es_unico()
    total_cuotas_ref = max(int(pago.total_cuotas or 0), len(eventos_ordenados), 1)

    if eventos_ordenados:
        detalle_eventos = _distribuir_pagado_en_eventos(eventos_ordenados, pagado_real)
        detalle_pendientes = [d for d in detalle_eventos if d.get('estado_evento') == 'pendiente']

        cuota_actual = None
        if detalle_pendientes:
            cuota_actual = detalle_pendientes[0]
        else:
            cuota_actual = next((d for d in detalle_eventos if d['saldo_cuota'] > 0), None)
            if cuota_actual is None:
                cuota_actual = detalle_eventos[-1]

        estado_label, estado_clase = _estado_cuota_visual(
            cuota_actual['fecha_cuota'],
            cuota_actual['saldo_cuota'],
            cuota_actual['abonado_cuota'],
        )

        if es_recurrente:
            cuota_label = 'Mensual'
        elif es_unico:
            cuota_label = 'Único'
        else:
            cuota_label = f"{cuota_actual['numero_cuota']}/{total_cuotas_ref}"

        return {
            'tiene_evento_operativo': True,
            'cuota_actual_numero': cuota_actual['numero_cuota'],
            'cuota_actual_label': cuota_label,
            'fecha_cuota_actual': cuota_actual['fecha_cuota'],
            'monto_cuota_actual': cuota_actual['monto_cuota'],
            'abonado_cuota_actual': cuota_actual['abonado_cuota'],
            'saldo_cuota_actual': cuota_actual['saldo_cuota'],
            'estado_cuota_actual': estado_label,
            'estado_cuota_clase': estado_clase,
        }

    monto_unitario = _to_decimal(pago.monto_evento_recurrente() if (es_recurrente or es_unico) else getattr(pago, 'monto', 0))
    total_cuotas_plan = int(pago.total_cuotas or 0) or 1

    if monto_unitario > 0:
        pagado_cap = min(_to_decimal(pagado_real), _to_decimal(total_compromiso))
        cuotas_completas = int(pagado_cap // monto_unitario)
        if cuotas_completas >= total_cuotas_plan:
            cuota_numero = total_cuotas_plan
            abonado_cuota = monto_unitario
        else:
            cuota_numero = max(1, cuotas_completas + 1)
            abonado_cuota = pagado_cap - (monto_unitario * Decimal(cuotas_completas))
            if abonado_cuota < 0:
                abonado_cuota = Decimal('0.00')
            if abonado_cuota > monto_unitario:
                abonado_cuota = monto_unitario

        saldo_cuota = monto_unitario - abonado_cuota
        if saldo_cuota < 0:
            saldo_cuota = Decimal('0.00')
        monto_cuota = monto_unitario
    else:
        cuota_numero = 1
        monto_cuota = _to_decimal(total_compromiso)
        abonado_cuota = min(_to_decimal(pagado_real), monto_cuota)
        saldo_cuota = monto_cuota - abonado_cuota
        if saldo_cuota < 0:
            saldo_cuota = Decimal('0.00')

    estado_label, estado_clase = _estado_cuota_visual(
        getattr(pago, 'fecha_inicio', None),
        saldo_cuota,
        abonado_cuota,
    )

    if es_recurrente:
        cuota_label = 'Mensual'
    elif es_unico:
        cuota_label = 'Único'
    else:
        cuota_label = f"{cuota_numero}/{total_cuotas_plan}"

    return {
        'tiene_evento_operativo': False,
        'cuota_actual_numero': cuota_numero,
        'cuota_actual_label': cuota_label,
        'fecha_cuota_actual': getattr(pago, 'fecha_inicio', None),
        'monto_cuota_actual': monto_cuota,
        'abonado_cuota_actual': abonado_cuota,
        'saldo_cuota_actual': saldo_cuota,
        'estado_cuota_actual': estado_label,
        'estado_cuota_clase': estado_clase,
    }


def _resumen_compromiso_financiero(pago):
    eventos_todos = list(pago.eventos.all()) if hasattr(pago, '_prefetched_objects_cache') and 'eventos' in pago._prefetched_objects_cache else list(pago.eventos.all())
    pagos_realizados = list(pago.pagos_realizados.all()) if hasattr(pago, '_prefetched_objects_cache') and 'pagos_realizados' in pago._prefetched_objects_cache else list(pago.pagos_realizados.all())

    total_compromiso = _sumar_relacion(eventos_todos)
    if total_compromiso <= 0:
        total_compromiso = Decimal(pago.total_cuotas or 0) * Decimal(pago.monto or 0)

    pagado_real = _sumar_relacion(pagos_realizados)
    saldo_real = total_compromiso - pagado_real
    if saldo_real < 0:
        saldo_real = Decimal('0.00')

    cuota_operativa = _resolver_cuota_operativa(
        pago=pago,
        eventos_todos=eventos_todos,
        pagado_real=pagado_real,
        total_compromiso=total_compromiso,
        saldo_real=saldo_real,
    )

    es_recurrente = hasattr(pago, 'es_recurrente') and pago.es_recurrente()
    es_unico = hasattr(pago, 'es_unico') and pago.es_unico()

    if es_recurrente:
        monto_visible = _to_decimal(cuota_operativa.get('monto_cuota_actual') or 0)
        abonado_visible = _to_decimal(cuota_operativa.get('abonado_cuota_actual') or 0)
        saldo_visible = _to_decimal(cuota_operativa.get('saldo_cuota_actual') or 0)

        if saldo_visible <= 0:
            estado = 'PAGADO'
            porcentaje_pagado = 100
        elif abonado_visible > 0 and monto_visible > 0:
            estado = 'PARCIAL'
            porcentaje_pagado = round((abonado_visible / monto_visible) * 100, 2)
        else:
            estado = 'PENDIENTE'
            porcentaje_pagado = 0

        saldo_visible_label = 'Pendiente del mes'
        proyeccion_horizonte = saldo_real
        proyeccion_horizonte_label = 'Proyección horizonte'
    else:
        if total_compromiso <= 0:
            estado = 'PENDIENTE'
            porcentaje_pagado = 0
        elif saldo_real <= 0:
            estado = 'PAGADO'
            porcentaje_pagado = 100
        elif pagado_real > 0:
            estado = 'PARCIAL'
            porcentaje_pagado = round((pagado_real / total_compromiso) * 100, 2)
        else:
            estado = 'PENDIENTE'
            porcentaje_pagado = 0

        saldo_visible = saldo_real
        saldo_visible_label = 'Saldo total pendiente'
        proyeccion_horizonte = saldo_real
        proyeccion_horizonte_label = 'Saldo total pendiente'

    return {
        'id': pago.id,
        'fecha_inicio': pago.fecha_inicio,
        'nombre': pago.nombre,
        'tipo': pago.tipo,
        **_modo_programacion_info(pago),
        'unidad_negocio': _unidad_pago_info(pago)['unidad_negocio'],
        'unidad_negocio_label': _unidad_pago_info(pago)['unidad_negocio_label'],
        'activo': pago.activo,
        'total_cuotas': pago.total_cuotas,
        'cuotas_restantes': pago.cuotas_restantes,
        'total_compromiso': total_compromiso,
        'pagado_real': pagado_real,
        'saldo_real': saldo_real,
        'saldo_visible': saldo_visible,
        'saldo_visible_label': saldo_visible_label,
        'proyeccion_horizonte': proyeccion_horizonte,
        'proyeccion_horizonte_label': proyeccion_horizonte_label,
        'es_recurrente': es_recurrente,
        'es_unico': es_unico,
        'estado_real': estado,
        'porcentaje_pagado': porcentaje_pagado,
        'porcentaje_visible': porcentaje_pagado,
        **cuota_operativa,
    }



def listar_compromisos_financieros(include_pagados=True, q=None, tipo=None, estado=None, activo=None):
    compromisos_qs = PagoProgramado.objects.all()
    if activo in (True, False):
        compromisos_qs = compromisos_qs.filter(activo=activo)
    else:
        compromisos_qs = compromisos_qs.filter(activo=True)

    compromisos = (
        compromisos_qs
        .prefetch_related('eventos', 'pagos_realizados')
        .order_by('-fecha_inicio', '-id')
    )

    items = []
    q_norm = (q or '').strip().lower()
    tipo = (tipo or '').strip().lower()
    estado = (estado or '').strip().upper()

    for pago in compromisos:
        item = _resumen_compromiso_financiero(pago)

        if not include_pagados and item['estado_real'] == 'PAGADO':
            continue
        if q_norm and q_norm not in (item['nombre'] or '').lower() and q_norm not in (pago.descripcion or '').lower():
            continue
        if tipo and item['tipo'] != tipo:
            continue
        if estado and item['estado_real'] != estado:
            continue

        items.append(item)

    orden_estado = {'PENDIENTE': 0, 'PARCIAL': 1, 'PAGADO': 2}
    items.sort(key=lambda item: (
        orden_estado.get(item['estado_real'], 9),
        item.get('fecha_cuota_actual') or item['fecha_inicio'] or timezone.now().date(),
        -(item.get('saldo_cuota_actual') or Decimal('0.00')),
        -(item.get('saldo_visible') or Decimal('0.00')),
        -(item['saldo_real'] or Decimal('0.00')),
        (item['nombre'] or '').lower(),
    ))
    return items



def resumen_estados_compromisos():
    items = listar_compromisos_financieros(include_pagados=True)

    pendientes = [i for i in items if i['estado_real'] == 'PENDIENTE']
    parciales = [i for i in items if i['estado_real'] == 'PARCIAL']
    pagados = [i for i in items if i['estado_real'] == 'PAGADO']

    def _sumar(items_local, key):
        total = Decimal('0.00')
        for item in items_local:
            total += Decimal(item.get(key) or 0)
        return total

    return {
        'pendientes_count': len(pendientes),
        'pendientes_saldo': _sumar(pendientes, 'saldo_real'),
        'parciales_count': len(parciales),
        'parciales_saldo': _sumar(parciales, 'saldo_real'),
        'pagados_count': len(pagados),
        'pagados_total': _sumar(pagados, 'total_compromiso'),
        'total_compromisos': len(items),
    }



def resumen_compromisos_por_unidad(items=None):
    if items is None:
        items = listar_compromisos_financieros(include_pagados=True)

    grupos = {}
    for item in items:
        unidad = item.get('unidad_negocio') or 'otros'
        unidad_label = item.get('unidad_negocio_label') or 'Otros'

        if unidad not in grupos:
            grupos[unidad] = {
                'unidad_negocio': unidad,
                'unidad_negocio_label': unidad_label,
                'cantidad': 0,
                'total_compromiso': Decimal('0.00'),
                'pagado_real': Decimal('0.00'),
                'saldo_real': Decimal('0.00'),
                'pendientes': 0,
                'parciales': 0,
                'pagados': 0,
            }

        grupos[unidad]['cantidad'] += 1
        grupos[unidad]['total_compromiso'] += Decimal(item.get('total_compromiso') or 0)
        grupos[unidad]['pagado_real'] += Decimal(item.get('pagado_real') or 0)
        grupos[unidad]['saldo_real'] += Decimal(item.get('saldo_real') or 0)

        estado = item.get('estado_real')
        if estado == 'PENDIENTE':
            grupos[unidad]['pendientes'] += 1
        elif estado == 'PARCIAL':
            grupos[unidad]['parciales'] += 1
        elif estado == 'PAGADO':
            grupos[unidad]['pagados'] += 1

    resultado = list(grupos.values())
    resultado.sort(key=lambda x: (-x['saldo_real'], x['unidad_negocio_label'].lower()))
    return resultado


def resumen_recurrentes_por_categoria(items=None):
    if items is None:
        items = listar_compromisos_financieros(include_pagados=True)

    grupos = {}
    for item in items:
        modo = (item.get('modo_programacion') or '').upper()
        categoria = item.get('categoria_recurrente') or ''
        categoria_label = item.get('categoria_recurrente_label') or 'Sin categoría'
        if modo != 'RECURRENTE' or not categoria:
            continue

        key = categoria
        if key not in grupos:
            grupos[key] = {
                'categoria_recurrente': categoria,
                'categoria_recurrente_label': categoria_label,
                'cantidad': 0,
                'saldo_visible_total': Decimal('0.00'),
                'proyeccion_horizonte_total': Decimal('0.00'),
                'pendientes': 0,
                'parciales': 0,
                'pagados': 0,
            }

        grupos[key]['cantidad'] += 1
        grupos[key]['saldo_visible_total'] += Decimal(item.get('saldo_visible') or item.get('saldo_real') or 0)
        grupos[key]['proyeccion_horizonte_total'] += Decimal(item.get('proyeccion_horizonte') or 0)

        estado = item.get('estado_real')
        if estado == 'PENDIENTE':
            grupos[key]['pendientes'] += 1
        elif estado == 'PARCIAL':
            grupos[key]['parciales'] += 1
        elif estado == 'PAGADO':
            grupos[key]['pagados'] += 1

    resultado = list(grupos.values())
    resultado.sort(key=lambda x: (-x['saldo_visible_total'], x['categoria_recurrente_label'].lower()))
    return resultado


def resumen_recurrentes_por_unidad_categoria(items=None):
    if items is None:
        items = listar_compromisos_financieros(include_pagados=True)

    grupos = {}
    for item in items:
        modo = (item.get('modo_programacion') or '').upper()
        categoria = item.get('categoria_recurrente') or ''
        categoria_label = item.get('categoria_recurrente_label') or 'Sin categoría'
        unidad = item.get('unidad_negocio') or 'otros'
        unidad_label = item.get('unidad_negocio_label') or 'Otros'

        if modo != 'RECURRENTE' or not categoria:
            continue

        key = (unidad, categoria)
        if key not in grupos:
            grupos[key] = {
                'unidad_negocio': unidad,
                'unidad_negocio_label': unidad_label,
                'categoria_recurrente': categoria,
                'categoria_recurrente_label': categoria_label,
                'cantidad': 0,
                'saldo_visible_total': Decimal('0.00'),
                'proyeccion_horizonte_total': Decimal('0.00'),
                'pendientes': 0,
                'parciales': 0,
                'pagados': 0,
            }

        grupos[key]['cantidad'] += 1
        grupos[key]['saldo_visible_total'] += Decimal(item.get('saldo_visible') or item.get('saldo_real') or 0)
        grupos[key]['proyeccion_horizonte_total'] += Decimal(item.get('proyeccion_horizonte') or 0)

        estado = item.get('estado_real')
        if estado == 'PENDIENTE':
            grupos[key]['pendientes'] += 1
        elif estado == 'PARCIAL':
            grupos[key]['parciales'] += 1
        elif estado == 'PAGADO':
            grupos[key]['pagados'] += 1

    resultado = list(grupos.values())
    resultado.sort(key=lambda x: (-x['saldo_visible_total'], x['unidad_negocio_label'].lower(), x['categoria_recurrente_label'].lower()))
    return resultado


def resumen_recurrentes_por_categoria(items=None):
    if items is None:
        items = listar_compromisos_financieros(include_pagados=True)

    grupos = {}
    for item in items:
        if (item.get('modo_programacion') or 'CUOTAS') != 'RECURRENTE':
            continue

        categoria = item.get('categoria_recurrente') or 'OTRO'
        categoria_label = item.get('categoria_recurrente_label') or 'Otro'

        if categoria not in grupos:
            grupos[categoria] = {
                'categoria_recurrente': categoria,
                'categoria_recurrente_label': categoria_label,
                'cantidad': 0,
                'saldo_visible_total': Decimal('0.00'),
                'proyeccion_horizonte_total': Decimal('0.00'),
                'pagados': 0,
                'parciales': 0,
                'pendientes': 0,
            }

        grupos[categoria]['cantidad'] += 1
        grupos[categoria]['saldo_visible_total'] += Decimal(item.get('saldo_visible') or 0)
        grupos[categoria]['proyeccion_horizonte_total'] += Decimal(item.get('proyeccion_horizonte') or 0)

        estado = item.get('estado_real')
        if estado == 'PAGADO':
            grupos[categoria]['pagados'] += 1
        elif estado == 'PARCIAL':
            grupos[categoria]['parciales'] += 1
        else:
            grupos[categoria]['pendientes'] += 1

    resultado = [
        grupo for grupo in grupos.values()
        if grupo['saldo_visible_total'] > 0 or grupo['proyeccion_horizonte_total'] > 0 or grupo['cantidad'] > 0
    ]
    resultado.sort(key=lambda x: (-x['proyeccion_horizonte_total'], -x['saldo_visible_total'], x['categoria_recurrente_label'].lower()))
    return resultado



# ==================================================
# KPIs FINANCIEROS EJECUTIVOS (REALIDAD FINANCIERA)
# ==================================================


def obtener_kpis_financieros():
    hoy = timezone.now().date()
    fin_30 = hoy + timedelta(days=30)

    eventos_qs = _eventos_operativos_qs()
    pagos_qs = _pagos_reales_operativos_qs()

    total_plan = eventos_qs.aggregate(
        total=Coalesce(
            Sum('monto'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )['total']

    saldo_pendiente_eventos = eventos_qs.filter(
        estado='pendiente'
    ).aggregate(
        total=Coalesce(
            Sum('monto'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )['total']

    total_pagado = pagos_qs.aggregate(
        total=Coalesce(
            Sum('monto'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )['total']

    total_adeudado_real = total_plan - total_pagado
    if total_adeudado_real < 0:
        total_adeudado_real = Decimal('0.00')

    flujo_futuro = eventos_qs.filter(
        estado='pendiente',
        fecha__gte=hoy
    ).aggregate(
        total=Coalesce(
            Sum('monto'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )['total']

    total_proximos_30 = eventos_qs.filter(
        estado='pendiente',
        fecha__range=[hoy, fin_30]
    ).aggregate(
        total=Coalesce(
            Sum('monto'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )['total']

    cantidad_eventos = eventos_qs.filter(
        estado='pendiente'
    ).count()

    monto_vencido = eventos_qs.filter(
        estado='pendiente',
        fecha__lt=hoy
    ).aggregate(
        total=Coalesce(
            Sum('monto'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )['total']

    cuotas_vencidas = eventos_qs.filter(
        estado='pendiente',
        fecha__lt=hoy
    ).count()

    return {
        'total_plan': total_plan,
        'total_comprometido': saldo_pendiente_eventos,
        'total_pagado': total_pagado,
        'total_adeudado_real': total_adeudado_real,
        'flujo_futuro': flujo_futuro,
        'total_proximo_mes': total_proximos_30,
        'cantidad_eventos': cantidad_eventos,
        'monto_vencido': monto_vencido,
        'cuotas_vencidas': cuotas_vencidas,
    }


# ==================================================
# FLUJO PROYECTADO PARA CHART
# ==================================================


def flujo_proyectado_mensual_chart(meses=6):
    hoy = timezone.now().date().replace(day=1)

    labels = []
    valores = []

    eventos_qs = _eventos_operativos_qs()

    for i in range(meses):
        inicio = (hoy + timedelta(days=32 * i)).replace(day=1)
        fin = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        total = eventos_qs.filter(
            fecha__range=[inicio, fin],
            estado='pendiente'
        ).aggregate(
            total=Coalesce(
                Sum('monto'),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=14, decimal_places=2)
            )
        )['total']

        labels.append(inicio.strftime('%b %Y'))
        valores.append(float(total))

    return {
        'labels': labels,
        'valores': valores
    }


# ==================================================
# RIESGO FINANCIERO EJECUTIVO
# ==================================================


def calcular_riesgo_financiero():
    hoy = timezone.now().date()
    eventos_qs = _eventos_operativos_qs()

    vencidos = eventos_qs.filter(
        estado='pendiente',
        fecha__lt=hoy
    ).count()

    proximos = eventos_qs.filter(
        estado='pendiente',
        fecha__range=[hoy, hoy + timedelta(days=3)]
    ).count()

    total = vencidos + proximos

    if total == 0:
        return {
            'vencidos': 0,
            'proximos': 0,
            'nivel': 'BAJO',
            'porcentaje': 0.0
        }

    score = (vencidos * 0.7 + proximos * 0.3) / total
    porcentaje = round(score * 100, 2)

    if vencidos == 0 and proximos <= 1:
        nivel = 'BAJO'
    elif vencidos <= 2:
        nivel = 'MEDIO'
    else:
        nivel = 'ALTO'

    return {
        'vencidos': vencidos,
        'proximos': proximos,
        'nivel': nivel,
        'porcentaje': porcentaje
    }


# ==================================================
# EVENTOS CRÍTICOS
# ==================================================


def eventos_criticos(dias=7):
    hoy = timezone.now().date()
    limite = hoy + timedelta(days=dias)

    return _eventos_operativos_qs().filter(
        estado='pendiente',
        fecha__lte=limite
    ).select_related('pago', 'pago__unidad_negocio_ref').order_by('fecha')


# ==================================================
# EVENTOS VENCIDOS
# ==================================================


def eventos_vencidos():
    hoy = timezone.now().date()

    return _eventos_operativos_qs().filter(
        estado='pendiente',
        fecha__lt=hoy
    ).select_related('pago', 'pago__unidad_negocio_ref').order_by('fecha')


# ==================================================
# EVENTOS PRÓXIMOS (7 DÍAS)
# ==================================================


def eventos_proximos(dias=7):
    hoy = timezone.now().date()
    limite = hoy + timedelta(days=dias)

    return _eventos_operativos_qs().filter(
        estado='pendiente',
        fecha__range=[hoy, limite]
    ).select_related('pago', 'pago__unidad_negocio_ref').order_by('fecha')


# ==================================================
# EVENTOS AGRUPADOS POR UNIDAD (DASHBOARD)
# ==================================================


def _unidad_evento_dashboard(evento):
    pago = getattr(evento, 'pago', None)
    if not pago:
        return {
            'unidad_negocio': 'otros',
            'unidad_negocio_label': 'Otros',
        }

    return _unidad_pago_info(pago)



def _resumen_evento_dashboard(evento):
    unidad_data = _unidad_evento_dashboard(evento)
    pago = getattr(evento, 'pago', None)

    return {
        'evento_id': evento.id,
        'pago_id': getattr(pago, 'id', None),
        'fecha': evento.fecha,
        'nombre': getattr(pago, 'nombre', '—'),
        'monto': Decimal(evento.monto or 0),
        'unidad_negocio': unidad_data['unidad_negocio'],
        'unidad_negocio_label': unidad_data['unidad_negocio_label'],
    }



def _agrupar_eventos_dashboard_por_unidad(eventos_qs):
    grupos = {}

    for evento in eventos_qs:
        item = _resumen_evento_dashboard(evento)
        unidad = item['unidad_negocio']
        unidad_label = item['unidad_negocio_label']

        if unidad not in grupos:
            grupos[unidad] = {
                'unidad_negocio': unidad,
                'unidad': unidad_label,
                'cantidad': 0,
                'monto_total': Decimal('0.00'),
                'eventos': [],
            }

        grupos[unidad]['cantidad'] += 1
        grupos[unidad]['monto_total'] += item['monto']
        grupos[unidad]['eventos'].append(item)

    resultado = list(grupos.values())

    for grupo in resultado:
        grupo['eventos'].sort(
            key=lambda e: (
                e['fecha'],
                -Decimal(e['monto'] or 0),
                (e['nombre'] or '').lower(),
            )
        )

    resultado.sort(
        key=lambda g: (
            -Decimal(g['monto_total'] or 0),
            g['unidad'].lower(),
        )
    )

    return resultado



def eventos_vencidos_agrupados():
    return _agrupar_eventos_dashboard_por_unidad(eventos_vencidos())



def eventos_proximos_agrupados(dias=7):
    return _agrupar_eventos_dashboard_por_unidad(eventos_proximos(dias=dias))


# ==================================================
# ALERTAS FINANCIERAS
# ==================================================


def resumen_alertas_financieras():
    panel = _agrupar_compromisos_por_alerta(limite=None)

    total_vencidas = len(panel['vencidas'])
    total_hoy = len(panel['vencen_hoy'])
    total_proximas_3 = len(panel['urgentes'])
    total_proximas_7 = len(panel['proximas'])

    total_alertas = total_vencidas + total_hoy + total_proximas_3 + total_proximas_7
    total_urgentes = total_vencidas + total_hoy + total_proximas_3

    return {
        'total_alertas': total_alertas,
        'total_urgentes': total_urgentes,
        'vencidas_count': total_vencidas,
        'vencidas_monto': _sumar_saldos(panel['vencidas']),
        'hoy_count': total_hoy,
        'hoy_monto': _sumar_saldos(panel['vencen_hoy']),
        'proximas_3_count': total_proximas_3,
        'proximas_3_monto': _sumar_saldos(panel['urgentes']),
        'proximas_7_count': total_proximas_7,
        'proximas_7_monto': _sumar_saldos(panel['proximas']),
    }



def obtener_panel_alertas_financieras(limite=10):
    """
    Panel SIN DUPLICADOS VISUALES por compromiso.

    Cada compromiso aparece solo una vez, asignado al bloque de mayor prioridad
    según su evento pendiente más próximo.
    """
    return _agrupar_compromisos_por_alerta(limite=limite)


# ==================================================
# ALERTAS URGENTES PARA EMAIL
# ==================================================


def _compromisos_urgentes_para_email(dias=2):
    hoy = timezone.now().date()
    limite_fecha = hoy + timedelta(days=dias)

    compromisos = (
        _pagos_programados_operativos_qs()
        .filter(eventos__estado='pendiente', eventos__fecha__lte=limite_fecha)
        .prefetch_related('eventos', 'pagos_realizados')
        .distinct()
        .order_by('nombre', 'id')
    )

    items = []

    for pago in compromisos:
        eventos_pendientes = [
            e for e in pago.eventos.all()
            if e.estado == 'pendiente' and e.fecha <= limite_fecha
        ]
        if not eventos_pendientes:
            continue

        resumen = _resumen_compromiso_alerta(pago, eventos_pendientes)

        if resumen['saldo_pendiente_real'] <= 0:
            continue

        items.append(resumen)

    items.sort(
        key=lambda item: (
            item['fecha'],
            -(item.get('cantidad_eventos_vencidos') or 0),
            -Decimal(item.get('saldo_pendiente_real') or 0),
            (item.get('nombre') or '').lower(),
        )
    )
    return items



def obtener_alertas_urgentes_email(dias=2, limite=200):
    items = _compromisos_urgentes_para_email(dias=dias)
    if limite is not None:
        return items[:limite]
    return items



def resumen_alertas_urgentes_email(dias=2):
    hoy = timezone.now().date()
    items = _compromisos_urgentes_para_email(dias=dias)

    vencidas = [item for item in items if item['fecha'] < hoy]
    hoy_items = [item for item in items if item['fecha'] == hoy]
    proximas = [item for item in items if hoy < item['fecha'] <= hoy + timedelta(days=dias)]

    total_saldo = _sumar_saldos(items)
    vencidas_saldo = _sumar_saldos(vencidas)
    hoy_saldo = _sumar_saldos(hoy_items)
    proximas_saldo = _sumar_saldos(proximas)

    return {
        'dias': dias,
        'total_eventos': len(items),
        'total_compromisos': len(items),
        'total_monto': total_saldo,
        'total_saldo_pendiente': total_saldo,
        'vencidas_count': len(vencidas),
        'vencidas_monto': vencidas_saldo,
        'vencidas_saldo': vencidas_saldo,
        'hoy_count': len(hoy_items),
        'hoy_monto': hoy_saldo,
        'hoy_saldo': hoy_saldo,
        'proximas_count': len(proximas),
        'proximas_monto': proximas_saldo,
        'proximas_saldo': proximas_saldo,
    }



def _categoria_alerta_email(item):
    nombre = str(item.get('nombre') or '').strip().lower()
    tipo = str(item.get('tipo') or '').strip().lower()
    descripcion = str(item.get('descripcion') or '').strip().lower()

    texto = f"{nombre} {descripcion}".strip()

    def contiene(*palabras):
        return any(p in texto for p in palabras)

    if contiene('arriendo', 'rent', 'alquiler'):
        return 'Arriendos'

    if contiene('saesa', 'luz', 'electricidad', 'energia', 'energía'):
        return 'Luz'

    if contiene('agua', 'essal', 'sanitaria'):
        return 'Agua'

    if contiene('iva', 'impuesto', 'sii', 'tesoreria', 'tesorería', 'contribuciones'):
        return 'Impuestos'

    if contiene('prestamo', 'préstamo'):
        return 'Préstamos'

    if tipo == 'credito' or contiene('credito', 'crédito', 'banco', 'santander', 'estado', 'cmr', 'scotiabank'):
        return 'Créditos'

    if tipo == 'fijo':
        return 'Fijos operativos'

    return 'Otros'



def agrupar_alertas_urgentes_email_por_categoria(dias=2, limite=200):
    hoy = timezone.now().date()
    items = obtener_alertas_urgentes_email(dias=dias, limite=limite)

    bloques = [
        ('vencidas', 'Vencidas'),
        ('hoy', 'Vencen hoy'),
        ('proximas', f'Próximas hasta {dias} día(s)'),
    ]

    resultado = {
        'vencidas': [],
        'hoy': [],
        'proximas': [],
    }

    for item in items:
        fecha = item.get('fecha')

        if fecha < hoy:
            bucket = 'vencidas'
        elif fecha == hoy:
            bucket = 'hoy'
        else:
            bucket = 'proximas'

        categoria = _categoria_alerta_email(item)
        item['categoria_alerta'] = categoria
        resultado[bucket].append(item)

    for bucket, _label in bloques:
        grupos = {}
        for item in resultado[bucket]:
            categoria = item['categoria_alerta']
            grupos.setdefault(categoria, []).append(item)

        grupos_ordenados = []
        for categoria, eventos in grupos.items():
            eventos = sorted(
                eventos,
                key=lambda x: (
                    x.get('fecha'),
                    -Decimal(x.get('saldo_pendiente_real') or 0),
                    (x.get('nombre') or '').lower(),
                )
            )

            grupos_ordenados.append({
                'categoria': categoria,
                'cantidad': len(eventos),
                'saldo_total': _sumar_saldos(eventos),
                'eventos': eventos,
            })

        grupos_ordenados.sort(
            key=lambda g: (
                0 if g['categoria'] == 'Arriendos' else
                1 if g['categoria'] == 'Luz' else
                2 if g['categoria'] == 'Agua' else
                3 if g['categoria'] == 'Créditos' else
                4 if g['categoria'] == 'Préstamos' else
                5 if g['categoria'] == 'Impuestos' else
                6 if g['categoria'] == 'Fijos operativos' else
                9,
                -Decimal(g['saldo_total'] or 0),
                g['categoria'].lower(),
            )
        )

        resultado[bucket] = grupos_ordenados

    return resultado
