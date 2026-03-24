from datetime import timedelta
from dateutil.relativedelta import relativedelta

from .models import EventoPago


def generar_eventos_pago(pago):
    """
    Genera automáticamente el calendario real de pagos,
    respetando exclusivamente las cuotas restantes reales.
    """

    # =========================
    # VALIDACIONES DURAS
    # =========================

    if pago.total_cuotas <= 0:
        return

    if pago.total_cuotas > 600:
        raise ValueError("Total de cuotas demasiado alto. Máximo permitido: 600 (50 años).")

    # 🔥 Ajuste clave: usamos el nombre REAL del campo
    cuotas_pendientes = getattr(pago, 'cuotas_restantes', None)

    if cuotas_pendientes is None:
        raise ValueError("El modelo PagoProgramado no contiene el campo 'cuotas_restantes'.")

    if cuotas_pendientes <= 0:
        return

    if cuotas_pendientes > pago.total_cuotas:
        raise ValueError("Las cuotas restantes no pueden ser mayores al total de cuotas.")

    # =========================
    # LIMPIEZA DE EVENTOS PREVIOS
    # =========================

    EventoPago.objects.filter(pago=pago).delete()

    # =========================
    # GENERACIÓN DE EVENTOS
    # =========================

    fecha = pago.fecha_inicio

    for i in range(cuotas_pendientes):

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
