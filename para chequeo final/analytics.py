from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum

from .models import EventoPago


# =========================================
# HELPERS INTERNOS
# =========================================


def _eventos_operativos_qs():
    return EventoPago.objects.filter(pago__activo=True)


# =========================================
# KPI: RESUMEN FINANCIERO GENERAL
# =========================================


def obtener_resumen_financiero():
    """
    Devuelve los principales KPIs financieros del sistema,
    excluyendo compromisos anulados/inactivos.
    """

    hoy = date.today()
    fin_mes = (hoy.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    eventos_qs = _eventos_operativos_qs()

    total_pendiente = eventos_qs.filter(
        estado='pendiente'
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0')

    total_mes = eventos_qs.filter(
        estado='pendiente',
        fecha__range=[hoy, fin_mes]
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0')

    total_vencido = eventos_qs.filter(
        estado='pendiente',
        fecha__lt=hoy
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0')

    return {
        'total_pendiente': total_pendiente,
        'total_mes': total_mes,
        'total_vencido': total_vencido,
        'hoy': hoy,
        'fin_mes': fin_mes
    }


# =========================================
# KPI: PROYECCIÓN FINANCIERA 12 MESES
# =========================================


def obtener_proyeccion_12_meses():
    """
    Genera proyección financiera mensual por 12 meses,
    excluyendo compromisos anulados/inactivos.
    """

    hoy = date.today().replace(day=1)
    proyeccion = []
    eventos_qs = _eventos_operativos_qs()

    for i in range(12):
        inicio = (hoy + timedelta(days=32 * i)).replace(day=1)
        fin = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        total = eventos_qs.filter(
            estado='pendiente',
            fecha__range=[inicio, fin]
        ).aggregate(total=Sum('monto'))['total'] or Decimal('0')

        proyeccion.append({
            'mes': inicio.strftime("%Y-%m"),
            'total': total
        })

    return proyeccion


# =========================================
# KPI: RIESGO FINANCIERO
# =========================================


def calcular_indice_riesgo():
    """
    Calcula índice simple de riesgo financiero,
    excluyendo compromisos anulados/inactivos.
    """

    hoy = date.today()
    eventos_qs = _eventos_operativos_qs()

    vencidos = eventos_qs.filter(
        estado='pendiente',
        fecha__lt=hoy
    ).count()

    proximos = eventos_qs.filter(
        estado='pendiente',
        fecha__range=[hoy, hoy + timedelta(days=3)]
    ).count()

    riesgo = "BAJO"

    if vencidos > 0:
        riesgo = "ALTO"
    elif proximos > 3:
        riesgo = "MEDIO"

    return {
        'vencidos': vencidos,
        'proximos': proximos,
        'nivel': riesgo
    }


# =========================================
# PROYECCIÓN FUTURA HASTA FECHA
# =========================================


def obtener_proyeccion_hasta_fecha(fecha_hasta, unidad_negocio=None):
    """
    Proyección diaria de egresos futuros hasta una fecha dada.

    Si se recibe unidad_negocio, filtra solo eventos pendientes
    pertenecientes a esa unidad.

    Excluye compromisos anulados/inactivos.
    """

    hoy = date.today()

    eventos = _eventos_operativos_qs().filter(
        estado='pendiente',
        fecha__gte=hoy,
        fecha__lte=fecha_hasta
    ).select_related('pago', 'pago__unidad_negocio_ref').order_by('fecha', 'id')

    unidad_negocio = (unidad_negocio or '').strip()
    if unidad_negocio:
        eventos = eventos.filter(pago__unidad_negocio=unidad_negocio)

    proyeccion = []
    acumulado = Decimal('0')

    for e in eventos:
        monto = e.monto or Decimal('0')
        acumulado += monto

        pago = getattr(e, 'pago', None)

        proyeccion.append({
            'fecha': e.fecha,
            'nombre': pago.nombre if pago else '—',
            'unidad_negocio': (
                pago.unidad_negocio_codigo_actual() if pago and hasattr(pago, 'unidad_negocio_codigo_actual') else 'otros'
            ),
            'unidad_negocio_label': (
                pago.unidad_negocio_label_actual() if pago and hasattr(pago, 'unidad_negocio_label_actual') else 'Otros'
            ),
            'monto': monto,
            'acumulado': acumulado
        })

    return proyeccion
