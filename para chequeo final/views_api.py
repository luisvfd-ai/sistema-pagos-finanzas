from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Sum

from .models import PagoProgramado


def api_pago_info(request, pk):
    pago = get_object_or_404(PagoProgramado, pk=pk)

    # Total deuda real del compromiso:
    # - Como tus eventos se generan SOLO por cuotas_restantes,
    #   el total real del compromiso es el total de esos eventos (pendiente+pagado).
    total_eventos = pago.eventos.aggregate(total=Sum('monto'))['total']

    if total_eventos is None:
        total = (Decimal(pago.cuotas_restantes or 0) * Decimal(pago.monto or 0))
    else:
        total = Decimal(total_eventos)

    pagado = pago.pagos_realizados.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    saldo = total - pagado
    if saldo < 0:
        saldo = Decimal('0.00')

    if total <= 0:
        porcentaje = 0
    else:
        porcentaje = round(float((pagado / total) * 100), 2)

    if saldo <= 0 and total > 0:
        estado = 'PAGADO'
    elif pagado > 0:
        estado = 'PARCIAL'
    else:
        estado = 'PENDIENTE'

    data = {
        "id": pago.id,
        "nombre": pago.nombre,
        "total": float(total),
        "pagado": float(pagado),
        "saldo": float(saldo),
        "porcentaje": float(porcentaje),
        "estado": estado,
    }

    return JsonResponse(data)