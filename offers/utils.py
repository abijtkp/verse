from decimal import Decimal
from django.utils import timezone

from offers.models import ProductOffer, CategoryOffer


def calculate_best_offer(variant):
    product = variant.product
    category = product.category
    now = timezone.now()

    base_price = variant.price

    best_discount = Decimal("0.00")
    applied_offer = None

    # PRODUCT OFFERS
    product_offers = ProductOffer.objects.filter(
        product=product,
        is_active=True,
        valid_from__lte=now,
        valid_to__gte=now,
    )

    for offer in product_offers:

        if offer.discount_type == "percentage":
            discount = (base_price * offer.discount_value) / Decimal("100")

            if offer.maximum_discount_amount:
                discount = min(discount, offer.maximum_discount_amount)

        else:
            discount = offer.discount_value

        if discount > best_discount:
            best_discount = discount
            applied_offer = offer

    # CATEGORY OFFERS
    category_offers = CategoryOffer.objects.filter(
        category=category,
        is_active=True,
        valid_from__lte=now,
        valid_to__gte=now,
    )

    for offer in category_offers:

        if offer.discount_type == "percentage":
            discount = (base_price * offer.discount_value) / Decimal("100")

            if offer.maximum_discount_amount:
                discount = min(discount, offer.maximum_discount_amount)

        else:
            discount = offer.discount_value

        if discount > best_discount:
            best_discount = discount
            applied_offer = offer

    minimum_price = Decimal("1.00")
    maximum_allowed_discount = base_price - minimum_price

    if maximum_allowed_discount < Decimal("0.00"):
        maximum_allowed_discount = Decimal("0.00")

    best_discount = min(best_discount, maximum_allowed_discount)

    final_price = base_price - best_discount

    return {
        "base_price": base_price,
        "discount_amount": best_discount,
        "final_price": final_price,
        "applied_offer": applied_offer,
    }