from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter
def compact_money(value):
    try:
        value = Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        value = Decimal("0")

    if value >= 1000000:
        return f"₹{value / Decimal('1000000'):.1f}M"

    if value >= 1000:
        return f"₹{value / Decimal('1000'):.1f}K"

    return f"₹{value:.0f}"