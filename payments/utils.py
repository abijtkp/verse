from decimal import Decimal
from django.db import transaction
from orders.models import Order
from payments.models import Wallet, WalletTransaction


REFERRER_REWARD_AMOUNT = Decimal("500.00")
REFERRED_USER_REWARD_AMOUNT = Decimal("200.00")

@transaction.atomic
def reward_referrer_after_first_order(order):
    user = order.user

    if not user.referred_by:
        return

    if user.referral_reward_given:
        return

    successful_orders_count = Order.objects.filter(
        user=user,
        payment_status__in=["paid", "pending"]
    ).exclude(
        status__in=["cancelled", "payment_failed"]
    ).count()

    if successful_orders_count != 1:
        return

    referrer = user.referred_by

    if referrer == user:
        return

    wallet, created = Wallet.objects.get_or_create(user=referrer)

    wallet.balance += REFERRER_REWARD_AMOUNT
    wallet.save(update_fields=["balance", "updated_at"])

    WalletTransaction.objects.create(
        wallet=wallet,
        order=order,
        transaction_type="credit",
        amount=REFERRER_REWARD_AMOUNT,
        reason=f"Referral reward for inviting {user.email}"
    )
    
    referred_user_wallet, created = Wallet.objects.get_or_create(user=user)

    referred_user_wallet.balance += REFERRED_USER_REWARD_AMOUNT
    referred_user_wallet.save(update_fields=["balance", "updated_at"])

    WalletTransaction.objects.create(
        wallet=referred_user_wallet,
        order=order,
        transaction_type="credit",
        amount=REFERRED_USER_REWARD_AMOUNT,
        reason="Referral signup reward after first order"
    )

    user.referral_reward_given = True
    user.save(update_fields=["referral_reward_given"])