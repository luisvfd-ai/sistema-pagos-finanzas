from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum

from .models import EventoPago


# =========================================
# KPI: RESUMEN FINANCIERO GENERAL
# =========================================

def obtener_resumen_financiero():
    """
    Devuelve los principales KPIs financieros del sistema.
    """

    hoy = date.today()
    fin_mes = (hoy.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    total_pendiente = EventoPago.objects.filter(
        estado='pendiente'
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0')

    total_mes = EventoPago.objects.filter(
        estado='pendiente',
        fecha__range=[hoy, fin_mes]
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0')

    total_vencido = EventoPago.objects.filter(
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
    Genera proyección financiera mensual por 12 meses.
    """

    hoy = date.today().replace(day=1)
    proyeccion = []

    for i in range(12):
        inicio = (hoy + timedelta(days=32*i)).replace(day=1)
        fin = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        total = EventoPago.objects.filter(
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
    Calcula índice simple de riesgo financiero.
    """

    hoy = date.today()

    vencidos = EventoPago.objects.filter(
        estado='pendiente',
        fecha__lt=hoy
    ).count()

    proximos = EventoPago.objects.filter(
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
