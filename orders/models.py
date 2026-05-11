from django.db import models
from django.conf import settings
from django.utils import timezone
from products.models import Variant


class Order(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('razorpay', 'Razorpay'),
        ('wallet', 'Wallet'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )

    order_id = models.CharField(max_length=30, unique=True, editable=False)

    full_name = models.CharField(max_length=120)
    phone_number = models.CharField(max_length=15)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default='India')

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cod'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )

    status = models.CharField(
        max_length=30,
        choices=ORDER_STATUS_CHOICES,
        default='pending'
    )

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    cancellation_reason = models.TextField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    delivered_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'orders'

    def save(self, *args, **kwargs):
        if not self.order_id:
            today = timezone.now().strftime('%Y%m%d')
            last_order = Order.objects.filter(
                order_id__startswith=f'VERSE-{today}'
            ).order_by('-id').first()

            if last_order:
                last_number = int(last_order.order_id.split('-')[-1])
                next_number = last_number + 1
            else:
                next_number = 1

            self.order_id = f'VERSE-{today}-{next_number:04d}'

        super().save(*args, **kwargs)
        
        
    @property
    def cancelled_total(self):
        return sum(
            item.item_total
            for item in self.items.filter(status='cancelled')
        )


    @property
    def returned_total(self):
        return sum(
            item.item_total
            for item in self.items.filter(status='returned')
        )
           
    @property
    def cancelled_or_returned_total(self):
        return sum(
            item.item_total
            for item in self.items.filter(status__in=['cancelled', 'returned'])
        )

    @property
    def active_items_total(self):
        return sum(
            item.item_total
            for item in self.items.exclude(status__in=['cancelled', 'returned'])
        )

    @property
    def adjusted_final_total(self):
        total = self.active_items_total + self.tax + self.shipping_charge - self.discount
        return max(total, 0)    

    def __str__(self):
        return self.order_id


class OrderItem(models.Model):
    ITEM_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )

    variant = models.ForeignKey(
        Variant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items'
    )


    product_name = models.CharField(max_length=255)
    category_name = models.CharField(max_length=255, blank=True, null=True)
    color = models.CharField(max_length=100)
    size = models.CharField(max_length=50)
    sku = models.CharField(max_length=100, blank=True, null=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    item_total = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=30,
        choices=ITEM_STATUS_CHOICES,
        default='pending'
    )

    cancellation_reason = models.TextField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    return_reason = models.TextField(blank=True, null=True)
    returned_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_items'

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"