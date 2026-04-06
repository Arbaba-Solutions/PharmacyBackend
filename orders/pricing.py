from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from catalog.models import DeliveryZone

MAX_SURGE_MULTIPLIER = Decimal('2.00')
URGENT_SURGE_MULTIPLIER = Decimal('2.00')


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_order_pricing(*, zone: DeliveryZone, is_customer_urgent: bool) -> dict:
    zone_multiplier = Decimal(str(zone.surge_multiplier)) if zone.surge_enabled else Decimal('1.00')
    customer_multiplier = URGENT_SURGE_MULTIPLIER if is_customer_urgent else Decimal('1.00')
    applied_multiplier = min(MAX_SURGE_MULTIPLIER, max(zone_multiplier, customer_multiplier))

    delivery_price = quantize_money(Decimal(str(zone.base_delivery_price)) * applied_multiplier)

    return {
        'delivery_price': delivery_price,
        'platform_fee': quantize_money(Decimal(str(zone.platform_fee))),
        'applied_surge_multiplier': quantize_money(applied_multiplier),
        'is_zone_surge_active': zone.surge_enabled,
    }
