from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.conf import settings


class Coupon(models.Model):
    PERCENTAGE = "percentage"
    FIXED = "fixed"

    DISCOUNT_TYPE_CHOICES = (
        (PERCENTAGE, "Percentage"),
        (FIXED, "Fixed Amount"),
    )

    code = models.CharField(max_length=50, unique=True)

    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES
    )

    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    minimum_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))]
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

    usage_limit = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "coupons"
        ordering = ["-created_at"]

    def __str__(self):
        return self.code
    
    @property
    def current_status(self):
        now = timezone.now()

        if self.valid_to < now:
            return "expired"

        if self.valid_from > now:
            return "scheduled"

        if not self.is_active:
            return "inactive"

        return "active"

    def is_valid_now(self):
        now = timezone.now()
        return self.valid_from <= now <= self.valid_to

    def is_usage_limit_reached(self):
        return self.used_count >= self.usage_limit

    def is_eligible(self, subtotal):
        subtotal = Decimal(str(subtotal))

        if not self.is_active:
            return False, "This coupon is inactive."

        if not self.is_valid_now():
            return False, "This coupon is expired or not yet active."

        if self.is_usage_limit_reached():
            return False, "This coupon usage limit has been reached."

        if subtotal < self.minimum_order_amount:
            return False, f"Minimum order amount should be ₹{self.minimum_order_amount}."

        return True, "Coupon is eligible."

    def calculate_discount(self, subtotal):
        subtotal = Decimal(str(subtotal))

        is_eligible, message = self.is_eligible(subtotal)

        if not is_eligible:
            return Decimal("0.00"), message

        if self.discount_type == self.PERCENTAGE:
            discount = (subtotal * self.discount_value) / Decimal("100")

            if self.maximum_discount_amount:
                discount = min(discount, self.maximum_discount_amount)

        else:
            discount = self.discount_value

        discount = min(discount, subtotal)

        return discount.quantize(Decimal("0.01")), "Coupon applied successfully."
    
 
    
class CouponUsage(models.Model):
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name="usages"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "coupon_usages"
        unique_together = ("coupon", "user")

    def __str__(self):
        return f"{self.user} used {self.coupon.code}"    