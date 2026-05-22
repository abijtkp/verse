from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from products.models import Product, Category


class OfferBase(models.Model):
    PERCENTAGE = "percentage"
    FLAT = "flat"

    DISCOUNT_TYPE_CHOICES = (
        (PERCENTAGE, "Percentage"),
        (FLAT, "Flat Amount"),
    )

    offer_name = models.CharField(max_length=120)

    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default=PERCENTAGE
    )

    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    maximum_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def is_valid_now(self):
        now = timezone.now()
        return self.is_active and self.valid_from <= now <= self.valid_to

    def calculate_discount(self, amount):
        amount = Decimal(str(amount))

        if self.discount_type == self.PERCENTAGE:
            discount = (amount * self.discount_value) / Decimal("100")

            if self.maximum_discount_amount:
                discount = min(discount, self.maximum_discount_amount)

        else:
            discount = self.discount_value

        discount = min(discount, amount)

        return discount.quantize(Decimal("0.01"))


class ProductOffer(OfferBase):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='product_offers'
    )

    class Meta:
        db_table = 'product_offers'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.offer_name} - {self.product.product_name}"


class CategoryOffer(OfferBase):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='category_offers'
    )

    class Meta:
        db_table = 'category_offers'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.offer_name} - {self.category.category_name}"