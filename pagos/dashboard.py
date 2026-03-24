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


def _resumen_compromiso_alerta(pago, eventos_pendientes):
    eventos_pendientes = sorted(eventos_pendientes, key=lambda e: e.fecha)
    primer_evento = eventos_pendientes[0]

    eventos_todos = list(pago.eventos.all()) if hasattr(pago, '_prefetched_objects_cache') and 'eventos' in pago._prefetched_objects_cache else list(pago.eventos.all())
    pagos_realizados = list(pago.pagos_realizados.all()) if hasattr(pago, '_prefetched_objects_cache') and 'pagos_realizados' in pago._prefetched_objects_cache else list(pago.pagos_realizados.all())

    total_compromiso = _sumar_relacion(eventos_todos)
    if total_compromiso <= 0:
        total_compromiso = Decimal(pago.total_cuotas or 0) * Decimal(pago.monto or 0)

    pagado_acumulado = _sumar_relacion(pagos_realizados)
    saldo_pendiente_real = total_compromiso - pagado_acumulado
    if saldo_pendiente_real < 0:
        saldo_pendiente_real = Decimal('0.00')

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
        PagoProgramado.objects
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


def _resumen_compromiso_financiero(pago):
    eventos_todos = list(pago.eventos.all())
    pagos_realizados = list(pago.pagos_realizados.all())

    total_compromiso = _sumar_relacion(eventos_todos)
    if total_compromiso <= 0:
        total_compromiso = Decimal(pago.total_cuotas or 0) * Decimal(pago.monto or 0)

    pagado_real = _sumar_relacion(pagos_realizados)
    saldo_real = total_compromiso - pagado_real
    if saldo_real < 0:
        saldo_real = Decimal('0.00')

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

    return {
        'id': pago.id,
        'fecha_inicio': pago.fecha_inicio,
        'nombre': pago.nombre,
        'tipo': pago.tipo,
        'activo': pago.activo,
        'total_cuotas': pago.total_cuotas,
        'cuotas_restantes': pago.cuotas_restantes,
        'total_compromiso': total_compromiso,
        'pagado_real': pagado_real,
        'saldo_real': saldo_real,
        'estado_real': estado,
        'porcentaje_pagado': porcentaje_pagado,
    }


def listar_compromisos_financieros(include_pagados=True, q=None, tipo=None, estado=None, activo=None):
    compromisos = (
        PagoProgramado.objects
        .all()
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
        if activo in (True, False) and bool(item['activo']) != activo:
            continue

        items.append(item)

    orden_estado = {'PENDIENTE': 0, 'PARCIAL': 1, 'PAGADO': 2}
    items.sort(key=lambda item: (orden_estado.get(item['estado_real'], 9), item['fecha_inicio'] or timezone.now().date(), -(item['saldo_real'] or Decimal('0.00')), (item['nombre'] or '').lower()))
    return items


def resumen_estados_compromisos():
    items = listar_compromisos_financieros(include_pagados=True)

    pendientes = [i for i in items if i['estado_real'] == 'PENDIENTE']
    parciales = [i for i in items if i['estado_real'] == 'PARCIAL']
    pagados = [i for i in items if i['estado_real'] == 'PAGADO']

    def _sumar(items, key):
        total = Decimal('0.00')
        for item in items:
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


# ==================================================
# KPIs FINANCIEROS EJECUTIVOS (REALIDAD FINANCIERA)
# ==================================================

def obtener_kpis_financieros():
    hoy = timezone.now().date()
    fin_30 = hoy + timedelta(days=30)

    total_plan = EventoPago.objects.aggregate(
        total=Coalesce(
            Sum('monto'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )['total']

    saldo_pendiente_eventos = EventoPago.objects.filter(
        estado='pendiente'
    ).aggregate(
        total=Coalesce(
            Sum('monto'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )['total']

    total_pagado = PagoReal.objects.aggregate(
        total=Coalesce(
            Sum('monto'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )['total']

    total_adeudado_real = total_plan - total_pagado
    if total_adeudado_real < 0:
        total_adeudado_real = Decimal('0.00')

    flujo_futuro = EventoPago.objects.filter(
        estado='pendiente',
        fecha__gte=hoy
    ).aggregate(
        total=Coalesce(
            Sum('monto'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )['total']

    total_proximos_30 = EventoPago.objects.filter(
        estado='pendiente',
        fecha__range=[hoy, fin_30]
    ).aggregate(
        total=Coalesce(
            Sum('monto'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )['total']

    cantidad_eventos = EventoPago.objects.filter(
        estado='pendiente'
    ).count()

    monto_vencido = EventoPago.objects.filter(
        estado='pendiente',
        fecha__lt=hoy
    ).aggregate(
        total=Coalesce(
            Sum('monto'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )['total']

    cuotas_vencidas = EventoPago.objects.filter(
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

    for i in range(meses):
        inicio = (hoy + timedelta(days=32 * i)).replace(day=1)
        fin = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        total = EventoPago.objects.filter(
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

    vencidos = EventoPago.objects.filter(
        estado='pendiente',
        fecha__lt=hoy
    ).count()

    proximos = EventoPago.objects.filter(
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

    return EventoPago.objects.filter(
        estado='pendiente',
        fecha__lte=limite
    ).select_related('pago').order_by('fecha')


# ==================================================
# EVENTOS VENCIDOS
# ==================================================

def eventos_vencidos():
    hoy = timezone.now().date()

    return EventoPago.objects.filter(
        estado='pendiente',
        fecha__lt=hoy
    ).select_related('pago').order_by('fecha')


# ==================================================
# EVENTOS PRÓXIMOS (7 DÍAS)
# ==================================================

def eventos_proximos(dias=7):
    hoy = timezone.now().date()
    limite = hoy + timedelta(days=dias)

    return EventoPago.objects.filter(
        estado='pendiente',
        fecha__range=[hoy, limite]
    ).select_related('pago').order_by('fecha')


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

    - vencidas: tiene al menos un evento pendiente vencido
    - vencen_hoy: su próximo evento pendiente vence hoy
    - urgentes: su próximo evento pendiente vence entre mañana y +3 días
    - proximas: su próximo evento pendiente vence entre +4 y +7 días
    """
    return _agrupar_compromisos_por_alerta(limite=limite)


# ==================================================
# ALERTAS URGENTES PARA EMAIL
# ==================================================

def _compromisos_urgentes_para_email(dias=2):
    hoy = timezone.now().date()
    limite_fecha = hoy + timedelta(days=dias)

    compromisos = (
        PagoProgramado.objects
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
