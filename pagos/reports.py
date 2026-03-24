from datetime import timedelta
from django.db.models import Sum, Count
from django.utils import timezone

from .models import EventoPago, PagoProgramado, PagoReal


# ============================
# CONSULTAS BASE
# ============================

def obtener_pagos_reales_por_rango(desde, hasta):
    """
    Pagos efectivamente realizados dentro del período.
    """
    return PagoReal.objects.filter(
        fecha_pago__range=[desde, hasta]
    ).select_related('pago').order_by('fecha_pago')


# ============================
# REPORTES FINANCIEROS REALES
# ============================

def resumen_financiero(desde, hasta):

    pagos = obtener_pagos_reales_por_rango(desde, hasta)

    total_pagado = pagos.aggregate(total=Sum('monto'))['total'] or 0

    return {
        'desde': desde,
        'hasta': hasta,
        'total_pagado': total_pagado,
        'cantidad_registros': pagos.count(),
        'promedio_pago': total_pagado / pagos.count() if pagos.count() else 0
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
