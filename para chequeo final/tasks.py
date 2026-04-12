from datetime import timedelta
from django.utils import timezone
from django.db import transaction

from .models import PagoProgramado, EventoPago
from .calendar import generar_eventos_pago


# ============================
# CREAR EVENTOS MASIVOS
# ============================

def generar_eventos_masivos():
    """
    Genera eventos para todos los pagos programados que no tengan eventos aún.
    Usa la lógica oficial: calendar.py (respeta cuotas_restantes).
    """
    pagos = PagoProgramado.objects.all()
    total = 0

    for pago in pagos:
        if not EventoPago.objects.filter(pago=pago).exists():
            generar_eventos_pago(pago)
            total += 1

    return total


# ============================
# LIMPIEZA DE EVENTOS ANTIGUOS
# ============================

def limpiar_eventos_antiguos(dias=365):
    """
    Borra eventos PAGADOS con más de X días para mantener la base liviana.
    (No borra pendientes).
    """
    limite = timezone.now().date() - timedelta(days=dias)
    eliminados, _ = EventoPago.objects.filter(
        estado='pagado',
        fecha__lt=limite
    ).delete()

    return eliminados


# ============================
# MOTOR FINANCIERO DIARIO
# ============================

def motor_financiero_diario():
    """
    Ejecuta tareas automáticas del sistema.
    Ideal para ejecución diaria.
    """

    with transaction.atomic():
        eventos_creados = generar_eventos_masivos()

    return {
        'eventos_creados': eventos_creados,
    }