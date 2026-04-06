from datetime import timedelta
from decimal import Decimal
import json
from datetime import date

from django.db.models import Sum, Count
from django.utils import timezone

from .models import EventoPago, PagoReal, unidad_negocio_label_from_codigo
from .analytics import obtener_proyeccion_hasta_fecha


# ============================
# CONSULTAS BASE
# ============================

def obtener_pagos_reales_por_rango(desde, hasta, unidad_negocio=None):
    """
    Pagos efectivamente realizados dentro del período.
    """

    qs = (
        PagoReal.objects
        .filter(fecha_pago__range=[desde, hasta])
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
    En reportes históricos, 'eventos' = pagos reales.
    """
    return obtener_pagos_reales_por_rango(desde, hasta, unidad_negocio=unidad_negocio)


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

    return EventoPago.objects.filter(
        fecha__range=[hoy, limite],
        estado='pendiente'
    ).order_by('fecha')


def pagos_vencidos():
    hoy = timezone.now().date()

    return EventoPago.objects.filter(
        fecha__lt=hoy,
        estado='pendiente'
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