from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()

def _to_decimal(value, default=Decimal("0")):
    if value is None:
        return default
    try:
        # str() évite les surprises avec float
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default

@register.filter(name="multiply")
def multiply(value, arg):
    """
    Usage: {{ value|multiply:0.8 }}
    Retourne value * arg en Decimal (robuste: None/valeurs invalides => 0)
    """
    v = _to_decimal(value)
    a = _to_decimal(arg)
    return v * a
