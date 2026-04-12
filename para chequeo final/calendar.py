from datetime import date, timedelta
import calendar as pycalendar
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from .models import EventoPago


MAX_CUOTAS_EVENTOS = 600
MAX_RECURRENTES_EVENTOS = 240
HORIZONTE_RECURRENTES_MESES = 12


def _safe_month_date(year, month, day):
    ultimo = pycalendar.monthrange(year, month)[1]
    return date(year, month, min(max(int(day or 1), 1), ultimo))


def _monto_evento_recurrente(pago):
    try:
        return Decimal(pago.monto_evento_recurrente() or 0)
    except Exception:
        return Decimal(getattr(pago, 'monto', 0) or 0)


def _generar_eventos_cuotas(pago):
    if (pago.total_cuotas or 0) <= 0:
        return

    if (pago.total_cuotas or 0) > MAX_CUOTAS_EVENTOS:
        raise ValueError("Total de cuotas demasiado alto. Máximo permitido: 600 (50 años).")

    cuotas_pendientes = getattr(pago, 'cuotas_restantes', None)
    if cuotas_pendientes is None:
        raise ValueError("El modelo PagoProgramado no contiene el campo 'cuotas_restantes'.")
    if cuotas_pendientes <= 0:
        return
    if cuotas_pendientes > (pago.total_cuotas or 0):
        raise ValueError("Las cuotas restantes no pueden ser mayores al total de cuotas.")

    fecha = pago.fecha_inicio
    for _ in range(cuotas_pendientes):
        EventoPago.objects.create(
            pago=pago,
            fecha=fecha,
            monto=pago.monto,
            estado='pendiente'
        )

        if pago.frecuencia == 'mensual':
            fecha += relativedelta(months=1)
        elif pago.frecuencia == 'quincenal':
            fecha += timedelta(days=15)
        elif pago.frecuencia == 'semanal':
            fecha += timedelta(days=7)
        elif pago.frecuencia == 'unico':
            break
        else:
            raise ValueError(f"Frecuencia inválida: {pago.frecuencia}")


def _generar_evento_unico(pago):
    EventoPago.objects.create(
        pago=pago,
        fecha=pago.fecha_inicio,
        monto=pago.monto_evento_recurrente(),
        estado='pendiente'
    )


def _generar_eventos_recurrentes(pago):
    fecha_inicio = pago.fecha_inicio
    if not fecha_inicio:
        return

    dia = pago.dia_vencimiento or fecha_inicio.day or 1
    primer_mes = _safe_month_date(fecha_inicio.year, fecha_inicio.month, dia)
    fecha = primer_mes if primer_mes >= fecha_inicio else fecha_inicio

    # Horizonte exacto de 12 eventos mensuales por defecto.
    # Ejemplo: si el primer evento es abril 2026, el último será marzo 2027.
    if getattr(pago, 'indefinido', False):
        cantidad_maxima = HORIZONTE_RECURRENTES_MESES
        fecha_limite = None
    else:
        fecha_limite = pago.fecha_fin
        cantidad_maxima = MAX_RECURRENTES_EVENTOS

    cantidad = 0
    while cantidad < min(cantidad_maxima, MAX_RECURRENTES_EVENTOS):
        if fecha_limite and fecha > fecha_limite:
            break

        EventoPago.objects.create(
            pago=pago,
            fecha=fecha,
            monto=_monto_evento_recurrente(pago),
            estado='pendiente'
        )
        cantidad += 1

        siguiente = fecha + relativedelta(months=1)
        fecha = _safe_month_date(siguiente.year, siguiente.month, dia)


def generar_eventos_pago(pago):
    """
    Genera automáticamente los eventos según el modo de programación del compromiso.

    - CUOTAS: respeta cuotas_restantes reales
    - UNICO: genera solo un evento
    - RECURRENTE: genera eventos mensuales desde fecha_inicio hasta horizonte
    """
    EventoPago.objects.filter(pago=pago).delete()

    if not getattr(pago, 'activo', True):
        return

    modo = getattr(pago, 'modo_programacion', 'CUOTAS') or 'CUOTAS'

    if modo == 'UNICO':
        _generar_evento_unico(pago)
        return

    if modo == 'RECURRENTE':
        _generar_eventos_recurrentes(pago)
        return

    _generar_eventos_cuotas(pago)
