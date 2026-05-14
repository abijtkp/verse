from django.db import models
from orders.models import Order
from django.conf import settings


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('razorpay', 'Razorpay'),
        ('wallet', 'Wallet'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('created', 'Created'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='payment'
    )

    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='created')

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    razorpay_order_id = models.CharField(max_length=120, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=120, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)

    failure_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'

    def __str__(self):
        return f"{self.order.order_id} - {self.method} - {self.status}"
    

    
class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet'
    )
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallets'

    def __str__(self):
        return f"{self.user.email} - ₹{self.balance}"
    
    
class WalletTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transactions'
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_transactions'
    )

    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPE_CHOICES
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wallet_transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.wallet.user.email} - {self.transaction_type} - ₹{self.amount}"