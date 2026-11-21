"""Display-only estimates. Never used for posting, collection or earnings."""
from decimal import Decimal, ROUND_HALF_UP


def delivery_estimate(subtotal):
    if not isinstance(subtotal, Decimal) or not subtotal.is_finite() or subtotal < 0:
        raise ValueError('Invalid authoritative subtotal')
    fee=(subtotal*Decimal('0.03')).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    return dict(estimated_delivery_fee=format(fee,'.2f'),
                estimated_total_with_delivery=format(subtotal+fee,'.2f'))
