from datetime import timedelta
from decimal import Decimal

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Sum

from .models import EventoPago, PagoProgramado, PagoReal
from .calendar import generar_eventos_pago


@receiver(pre_save, sender=PagoProgramado)
def snapshot_pago_programado(sender, instance, **kwargs):
    if not instance.pk:
        instance._old = None
        return

    try:
        instance._old = PagoProgramado.objects.get(pk=instance.pk)
    except PagoProgramado.DoesNotExist:
        instance._old = None


@receiver(post_save, sender=PagoProgramado)
def crear_o_regenerar_calendario(sender, instance, created, **kwargs):
    if created:
        generar_eventos_pago(instance)
        return

    old = getattr(instance, "_old", None)
    if not old:
        return

    campos_clave_cambiaron = any([
        old.modo_programacion != instance.modo_programacion,
        old.tipo != instance.tipo,
        old.monto != instance.monto,
        old.fecha_inicio != instance.fecha_inicio,
        old.frecuencia != instance.frecuencia,
        old.total_cuotas != instance.total_cuotas,
        old.cuotas_restantes != instance.cuotas_restantes,
        old.categoria_recurrente != instance.categoria_recurrente,
        old.indefinido != instance.indefinido,
        old.fecha_fin != instance.fecha_fin,
        old.dia_vencimiento != instance.dia_vencimiento,
        old.metodo_proyeccion != instance.metodo_proyeccion,
        old.monto_proyeccion_manual != instance.monto_proyeccion_manual,
        old.activo != instance.activo,
    ])

    if campos_clave_cambiaron:
        generar_eventos_pago(instance)
        conciliar_eventos_con_pagos_reales(instance)



def conciliar_eventos_con_pagos_reales_por_id(pago_id):
    if not pago_id:
        return

    pago = PagoProgramado.objects.filter(pk=pago_id).first()
    if pago is None:
        return

    conciliar_eventos_con_pagos_reales(pago)

def conciliar_eventos_con_pagos_reales(pago: PagoProgramado):
    total_pagado = pago.pagos_realizados.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    eventos = list(pago.eventos.order_by('fecha', 'id').only('id', 'monto', 'estado'))

    EventoPago.objects.filter(pago=pago).update(estado='pendiente')

    restante = Decimal(total_pagado)
    ids_a_pagar = []
    for e in eventos:
        monto_evento = Decimal(e.monto or 0)
        if monto_evento <= 0:
            continue
        if restante >= monto_evento:
            ids_a_pagar.append(e.id)
            restante -= monto_evento
        else:
            break

    if ids_a_pagar:
        EventoPago.objects.filter(id__in=ids_a_pagar).update(estado='pagado')


@receiver(pre_save, sender=PagoReal)
def snapshot_pago_real(sender, instance, **kwargs):
    instance._old_pago_id = None

    if not instance.pk:
        return

    try:
        old = PagoReal.objects.only('id', 'pago_id').get(pk=instance.pk)
        instance._old_pago_id = old.pago_id
    except PagoReal.DoesNotExist:
        instance._old_pago_id = None


@receiver(post_save, sender=PagoReal)
def conciliar_eventos_al_guardar_pago_real(sender, instance, created, **kwargs):
    pago_actual_id = getattr(instance, 'pago_id', None)
    pago_anterior_id = getattr(instance, '_old_pago_id', None)

    if pago_anterior_id and pago_anterior_id != pago_actual_id:
        conciliar_eventos_con_pagos_reales_por_id(pago_anterior_id)

    conciliar_eventos_con_pagos_reales_por_id(pago_actual_id)


@receiver(post_delete, sender=PagoReal)
def conciliar_eventos_al_eliminar_pago_real(sender, instance, **kwargs):
    conciliar_eventos_con_pagos_reales_por_id(getattr(instance, 'pago_id', None))


def detectar_eventos_por_alertar():
    hoy = timezone.now().date()
    fecha_preventiva = hoy + timedelta(days=3)
    fecha_urgente = hoy + timedelta(days=1)

    alerta_preventiva = EventoPago.objects.filter(
        fecha=fecha_preventiva,
        estado='pendiente',
        pago__activo=True,
    )

    alerta_urgente = EventoPago.objects.filter(
        fecha=fecha_urgente,
        estado='pendiente',
        pago__activo=True,
    )

    return alerta_preventiva, alerta_urgente


def ejecutar_alertas():
    preventivas, urgentes = detectar_eventos_por_alertar()

    for evento in preventivas:
        enviar_alerta(evento, tipo='preventiva')

    for evento in urgentes:
        enviar_alerta(evento, tipo='urgente')

    return {
        'preventivas': preventivas.count(),
        'urgentes': urgentes.count()
    }


def enviar_alerta(evento, tipo='preventiva'):
    pago = evento.pago

    if tipo == 'urgente':
        asunto = "🚨 ALERTA URGENTE DE PAGO"
        mensaje = f"""
        ⚠️ PAGO MAÑANA

        Concepto: {pago.nombre}
        Tipo: {pago.tipo}
        Monto pendiente: ${float(evento.monto):,.0f}
        Fecha: {evento.fecha}
        """
    else:
        asunto = "🔔 Recordatorio de pago próximo"
        mensaje = f"""
        📅 PAGO PRÓXIMO

        Concepto: {pago.nombre}
        Tipo: {pago.tipo}
        Monto pendiente: ${float(evento.monto):,.0f}
        Fecha: {evento.fecha}
        """

    print("=" * 60)
    print(asunto)
    print(mensaje)
    print("=" * 60)
