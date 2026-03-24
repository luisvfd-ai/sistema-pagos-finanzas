from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


def _to_decimal(value):
    if value in (None, ""):
        return Decimal("0")

    if isinstance(value, Decimal):
        return value

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _format_clp_number(value):
    value = _to_decimal(value)
    entero = int(value.quantize(Decimal("1")))
    # 1,234,567 -> 1.234.567
    return f"{entero:,}".replace(",", ".")


@register.filter
def clp(value):
    """
    Ejemplo:
    {{ monto|clp }} -> $1.234.567 CLP
    """
    return f"${_format_clp_number(value)} CLP"


@register.filter
def clp_s(value):
    """
    Ejemplo:
    {{ monto|clp_s }} -> $1.234.567
    """
    return f"${_format_clp_number(value)}"