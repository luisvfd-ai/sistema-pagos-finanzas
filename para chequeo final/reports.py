from datetime import timedelta, date
from decimal import Decimal
import json

from django.db.models import Sum, Count
from django.utils import timezone

from .models import EventoPago, PagoProgramado, PagoReal, unidad_negocio_label_from_codigo
from .analytics import obtener_proyeccion_hasta_fecha


# ============================
# CONSULTAS BASE
# ============================

def obtener_pagos_reales_por_rango(desde, hasta, unidad_negocio=None):
    """
    Pagos efectivamente realizados dentro del período, solo de compromisos activos.
    """
    qs = (
        PagoReal.objects
        .filter(fecha_pago__range=[desde, hasta], pago__activo=True)
        .select_related('pago')
        .order_by('fecha_pago', 'id')
    )

    unidad_negocio = (unidad_negocio or '').strip()
    if unidad_negocio:
        qs = qs.filter(pago__unidad_negocio=unidad_negocio)

    return qs


def obtener_eventos_por_rango(desde, hasta, unidad_negocio=None):
    """
    Compatibilidad con el nombre usado por views.py.
    En reportes históricos, 'eventos' = pagos reales de compromisos activos.
    """
    return obtener_pagos_reales_por_rango(desde, hasta, unidad_negocio=unidad_negocio)


def _eventos_pendientes_activos_qs():
    """
    Eventos pendientes pertenecientes a compromisos activos.
    """
    return (
        EventoPago.objects
        .filter(estado='pendiente', pago__activo=True)
        .select_related('pago')
    )


def _eventos_proyeccion_qs(fecha_hasta, unidad_negocio=None):
    """
    Eventos futuros pendientes para análisis de proyección.
    """
    hoy = timezone.now().date()
    qs = (
        _eventos_pendientes_activos_qs()
        .filter(fecha__gte=hoy, fecha__lte=fecha_hasta)
        .order_by('fecha', 'id')
    )

    unidad_negocio = (unidad_negocio or '').strip()
    if unidad_negocio:
        qs = qs.filter(pago__unidad_negocio=unidad_negocio)

    return qs


# ============================
# HELPERS DE REPORTE HISTÓRICO
# ============================

def _decimal_a_numero(valor):
    if valor is None:
        return 0
    try:
        return float(valor)
    except Exception:
        return 0


def resumen_financiero(desde, hasta, unidad_negocio=None):
    pagos = obtener_pagos_reales_por_rango(desde, hasta, unidad_negocio=unidad_negocio)

    total_pagado = pagos.aggregate(total=Sum('monto'))['total'] or Decimal('0')
    cantidad = pagos.count()
    promedio = total_pagado / cantidad if cantidad else Decimal('0')

    return {
        'desde': desde,
        'hasta': hasta,
        'total_pagado': total_pagado,
        'cantidad_registros': cantidad,
        'promedio_pago': promedio,
    }


def obtener_metodo_principal(desde, hasta, unidad_negocio=None):
    pagos = obtener_pagos_reales_por_rango(desde, hasta, unidad_negocio=unidad_negocio)

    fila = (
        pagos.values('metodo_pago')
        .annotate(total=Sum('monto'))
        .order_by('-total', 'metodo_pago')
        .first()
    )

    if not fila:
        return "—"

    return fila['metodo_pago'] or "—"


def obtener_top_compromisos(desde, hasta, limite=3, unidad_negocio=None):
    pagos = obtener_pagos_reales_por_rango(desde, hasta, unidad_negocio=unidad_negocio)

    top = (
        pagos.values('pago__nombre', 'pago__unidad_negocio')
        .annotate(
            total=Sum('monto'),
            cantidad=Count('id')
        )
        .order_by('-total', 'pago__nombre')[:limite]
    )

    resultado = []
    for item in top:
        codigo = item.get('pago__unidad_negocio') or 'otros'
        resultado.append({
            'nombre': item['pago__nombre'] or 'Sin nombre',
            'unidad_negocio': codigo,
            'unidad_negocio_label': unidad_negocio_label_from_codigo(codigo),
            'total': item['total'] or Decimal('0'),
            'cantidad': item['cantidad'] or 0,
        })

    return resultado


def construir_chart_diario_json(desde, hasta, unidad_negocio=None):
    pagos = obtener_pagos_reales_por_rango(desde, hasta, unidad_negocio=unidad_negocio)

    agrupado = (
        pagos.values('fecha_pago')
        .annotate(total=Sum('monto'))
        .order_by('fecha_pago')
    )

    labels = []
    valores = []

    for fila in agrupado:
        fecha = fila['fecha_pago']
        total = fila['total'] or Decimal('0')

        labels.append(fecha.strftime("%Y-%m-%d"))
        valores.append(_decimal_a_numero(total))

    return json.dumps({
        'labels': labels,
        'valores': valores,
    })


def construir_chart_metodo_json(desde, hasta, unidad_negocio=None):
    pagos = obtener_pagos_reales_por_rango(desde, hasta, unidad_negocio=unidad_negocio)

    agrupado = (
        pagos.values('metodo_pago')
        .annotate(total=Sum('monto'))
        .order_by('-total', 'metodo_pago')
    )

    labels = []
    valores = []

    for fila in agrupado:
        metodo = fila['metodo_pago'] or 'Sin método'
        total = fila['total'] or Decimal('0')

        labels.append(metodo)
        valores.append(_decimal_a_numero(total))

    return json.dumps({
        'labels': labels,
        'valores': valores,
    })


def generar_contexto_reporte_historico(desde, hasta, unidad_negocio=None):
    eventos = obtener_pagos_reales_por_rango(desde, hasta, unidad_negocio=unidad_negocio)

    total = eventos.aggregate(total=Sum('monto'))['total'] or Decimal('0')
    cantidad = eventos.count()
    promedio = total / cantidad if cantidad else Decimal('0')

    return {
        'desde': desde,
        'hasta': hasta,
        'eventos': eventos,
        'total': total,
        'promedio': promedio,
        'metodo_principal': obtener_metodo_principal(desde, hasta, unidad_negocio=unidad_negocio),
        'top_compromisos': obtener_top_compromisos(desde, hasta, limite=3, unidad_negocio=unidad_negocio),
        'chart_diario_json': construir_chart_diario_json(desde, hasta, unidad_negocio=unidad_negocio),
        'chart_metodo_json': construir_chart_metodo_json(desde, hasta, unidad_negocio=unidad_negocio),
    }


# ============================
# ALERTAS Y VENCIMIENTOS
# ============================

def pagos_proximos_a_vencer(dias=3):
    hoy = timezone.now().date()
    limite = hoy + timedelta(days=dias)

    return _eventos_pendientes_activos_qs().filter(
        fecha__range=[hoy, limite]
    ).order_by('fecha')


def pagos_vencidos():
    hoy = timezone.now().date()

    return _eventos_pendientes_activos_qs().filter(
        fecha__lt=hoy
    ).order_by('fecha')


# ============================
# DASHBOARD OFFLINE
# ============================

def dashboard_financiero(desde, hasta):
    return {
        'resumen_general': resumen_financiero(desde, hasta),
        'proximos_vencimientos': list(pagos_proximos_a_vencer()),
        'vencidos': list(pagos_vencidos()),
    }


# ========================
# PROYECCION
# ========================

def generar_proyeccion_json(fecha_hasta, unidad_negocio=None):
    data = obtener_proyeccion_hasta_fecha(
        fecha_hasta,
        unidad_negocio=unidad_negocio
    )

    labels = []
    valores = []
    acumulado_vals = []

    acumulado = 0

    for item in data:
        labels.append(item['fecha'].strftime("%Y-%m-%d"))

        monto = float(item['monto'])
        acumulado += monto

        valores.append(monto)
        acumulado_vals.append(acumulado)

    return json.dumps({
        'labels': labels,
        'valores': valores,
        'acumulado': acumulado_vals
    })


def resumen_proyeccion(fecha_hasta, unidad_negocio=None):
    data = obtener_proyeccion_hasta_fecha(
        fecha_hasta,
        unidad_negocio=unidad_negocio
    )

    total = sum([d['monto'] for d in data], Decimal('0'))
    cantidad = len(data)

    mayor_dia = max(data, key=lambda x: x['monto'], default=None)

    return {
        'total_proyectado': total,
        'cantidad_eventos': cantidad,
        'promedio': total / cantidad if cantidad else 0,
        'mayor_dia': mayor_dia
    }


# ========================
# ANALISIS DE PROYECCION
# ========================

def analisis_proyeccion_recurrentes(fecha_hasta, unidad_negocio=None):
    """
    Resume la proyección futura separando cuotas/unicos/recurrentes y
    desglosando la carga recurrente por categoría y por unidad.
    """
    eventos = list(_eventos_proyeccion_qs(fecha_hasta, unidad_negocio=unidad_negocio))

    total_recurrentes = Decimal('0')
    total_cuotas = Decimal('0')
    total_unicos = Decimal('0')
    cantidad_recurrentes = 0
    cantidad_cuotas = 0
    cantidad_unicos = 0

    categorias = {}
    unidades = {}
    primeros_eventos_recurrentes = {}

    for evento in eventos:
        pago = getattr(evento, 'pago', None)
        monto = Decimal(evento.monto or 0)
        modo = getattr(pago, 'modo_programacion', 'CUOTAS') or 'CUOTAS'
        try:
            categoria = pago.categoria_recurrente_codigo_actual() if hasattr(pago, 'categoria_recurrente_codigo_actual') else (getattr(pago, 'categoria_recurrente', '') or '')
        except Exception:
            categoria = getattr(pago, 'categoria_recurrente', '') or ''
        unidad = getattr(pago, 'unidad_negocio', None) or 'otros'
        unidad_label = unidad_negocio_label_from_codigo(unidad)

        if modo == 'RECURRENTE':
            total_recurrentes += monto
            cantidad_recurrentes += 1

            categoria_label = (
                pago.categoria_recurrente_label_actual()
                if categoria and hasattr(pago, 'categoria_recurrente_label_actual')
                else (categoria.replace('_', ' ').title() if categoria else 'Otros')
            )

            cat = categorias.setdefault(categoria or 'OTRO', {
                'categoria': categoria or 'OTRO',
                'categoria_label': categoria_label or 'Otros',
                'total': Decimal('0'),
                'cantidad_eventos': 0,
            })
            cat['total'] += monto
            cat['cantidad_eventos'] += 1

            uni = unidades.setdefault(unidad, {
                'unidad_negocio': unidad,
                'unidad_negocio_label': unidad_label,
                'total_recurrente': Decimal('0'),
                'cantidad_eventos': 0,
            })
            uni['total_recurrente'] += monto
            uni['cantidad_eventos'] += 1

            if pago and pago.id not in primeros_eventos_recurrentes:
                primeros_eventos_recurrentes[pago.id] = monto

        elif modo == 'UNICO':
            total_unicos += monto
            cantidad_unicos += 1
        else:
            total_cuotas += monto
            cantidad_cuotas += 1

    carga_recurrente_mensual_estimada = sum(primeros_eventos_recurrentes.values(), Decimal('0'))

    categorias_ordenadas = sorted(
        categorias.values(),
        key=lambda item: (-item['total'], item['categoria_label'].lower())
    )

    unidades_ordenadas = sorted(
        unidades.values(),
        key=lambda item: (-item['total_recurrente'], item['unidad_negocio_label'].lower())
    )

    total_proyeccion = total_recurrentes + total_cuotas + total_unicos

    return {
        'total_proyeccion': total_proyeccion,
        'total_recurrentes': total_recurrentes,
        'total_cuotas': total_cuotas,
        'total_unicos': total_unicos,
        'cantidad_recurrentes': cantidad_recurrentes,
        'cantidad_cuotas': cantidad_cuotas,
        'cantidad_unicos': cantidad_unicos,
        'carga_recurrente_mensual_estimada': carga_recurrente_mensual_estimada,
        'categorias': categorias_ordenadas,
        'unidades': unidades_ordenadas,
    }
