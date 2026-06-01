from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Wallet
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
import razorpay
from payments.models import WalletTransaction
from django.core.paginator import Paginator

import logging

logger = logging.getLogger(__name__)

MAX_WALLET_BALANCE = Decimal("50000.00")

@login_required
def wallet_view(request):
    wallet, created = Wallet.objects.get_or_create(user=request.user)

    transactions_queryset = (
        wallet.transactions
        .select_related('order')
        .order_by('-created_at')
    )

    paginator = Paginator(transactions_queryset, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    logger.info(
        "User viewed wallet | user_id=%s | email=%s | balance=%s | page=%s",
        request.user.id,
        request.user.email,
        wallet.balance,
        page_number or 1,
    )

    return render(request, 'payments/wallet.html', {
        'wallet': wallet,
        'transactions': page_obj,
        'page_obj': page_obj,
    })
    
@login_required
def add_money_view(request):
    return render(request, 'payments/add_money.html')


@login_required
def create_wallet_topup_view(request):

    if request.method != 'POST':
        
        logger.warning(
            "Invalid wallet topup request method | user_id=%s | email=%s | method=%s",
            request.user.id,
            request.user.email,
            request.method,
        )
        
        return redirect('add_money')

    amount = request.POST.get('amount')

    try:
        amount = Decimal(amount)

        if amount <= 0:
            raise ValueError
        
        if amount > MAX_WALLET_BALANCE:
            messages.error(
                request,
                "Maximum wallet top-up amount is ₹50,000."
            )
            return redirect('add_money')

    except Exception:
        
        logger.warning(
            "Invalid wallet topup amount | user_id=%s | email=%s | amount=%s",
            request.user.id,
            request.user.email,
            amount,
        )
        
        messages.error(request, "Invalid amount.")
        return redirect('add_money')
    
    wallet, _ = Wallet.objects.get_or_create(
        user=request.user
    )

    if wallet.balance + amount > MAX_WALLET_BALANCE:
        messages.error(
            request,
            f"Wallet balance cannot exceed ₹50,000. Current balance: ₹{wallet.balance}"
        )
        return redirect('add_money')

    client = razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET
        )
    )

    razorpay_order = client.order.create({
        "amount": int(amount * 100),
        "currency": "INR",
        "payment_capture": 1,
    })
    
    logger.info(
        "Razorpay wallet order created | user_id=%s | email=%s | razorpay_order_id=%s | amount=%s",
        request.user.id,
        request.user.email,
        razorpay_order['id'],
        amount,
    )

    context = {
        'amount': amount,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'razorpay_amount': int(amount * 100),
        'razorpay_order_id': razorpay_order['id'],
    }

    return render(request, 'payments/add_money.html', context)


@csrf_exempt
@login_required
def verify_wallet_topup_view(request):

    if request.method != 'POST':
        
        logger.warning(
            "Invalid wallet topup verification method | user_id=%s | email=%s | method=%s",
            request.user.id,
            request.user.email,
            request.method,
        )
        
        return redirect('wallet')

    razorpay_order_id = request.POST.get('razorpay_order_id')
    razorpay_payment_id = request.POST.get('razorpay_payment_id')
    razorpay_signature = request.POST.get('razorpay_signature')
    amount = request.POST.get('amount')

    try:
        amount = Decimal(amount)

        client = razorpay.Client(
            auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET
            )
        )

        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })

        wallet, created = Wallet.objects.get_or_create(
            user=request.user
        )
        
        if wallet.balance + amount > MAX_WALLET_BALANCE:

            logger.warning(
                "Wallet balance limit exceeded | user_id=%s | email=%s | current_balance=%s | amount=%s",
                request.user.id,
                request.user.email,
                wallet.balance,
                amount,
            )

            messages.error(
                request,
                "Wallet balance cannot exceed ₹50,000."
            )

            return redirect('wallet')
        
        old_balance = wallet.balance
        wallet.balance += amount

        wallet.save(update_fields=[
            'balance',
            'updated_at'
        ])

        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='credit',
            amount=amount,
            reason='Wallet top-up'
        )
        
        logger.info(
            "Wallet topup verified successfully | user_id=%s | email=%s | razorpay_order_id=%s | razorpay_payment_id=%s | amount=%s | old_balance=%s | new_balance=%s",
            request.user.id,
            request.user.email,
            razorpay_order_id,
            razorpay_payment_id,
            amount,
            old_balance,
            wallet.balance,
        )

        messages.success(
            request,
            f"₹{amount} added to wallet successfully."
        )

        return redirect('wallet')

    except (ValueError, TypeError):
        
        logger.exception(
            "Wallet topup verification failed | user_id=%s | email=%s | razorpay_order_id=%s | razorpay_payment_id=%s | amount=%s",
            request.user.id,
            request.user.email,
            razorpay_order_id,
            razorpay_payment_id,
            amount,
        )
        
        messages.error(
            request,
            "Wallet top-up failed."
        )

        return redirect('add_money')    