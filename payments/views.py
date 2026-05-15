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


@login_required
def wallet_view(request):
    wallet, created = Wallet.objects.get_or_create(user=request.user)

    transactions = (
        wallet.transactions
        .select_related('order')
        .order_by('-created_at')
    )

    return render(request, 'payments/wallet.html', {
        'wallet': wallet,
        'transactions': transactions,
    })
    
@login_required
def add_money_view(request):
    return render(request, 'payments/add_money.html')


@login_required
def create_wallet_topup_view(request):

    if request.method != 'POST':
        return redirect('add_money')

    amount = request.POST.get('amount')

    try:
        amount = Decimal(amount)

        if amount <= 0:
            raise ValueError

    except:
        messages.error(request, "Invalid amount.")
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

        messages.success(
            request,
            f"₹{amount} added to wallet successfully."
        )

        return redirect('wallet')

    except Exception:
        messages.error(
            request,
            "Wallet top-up failed."
        )

        return redirect('add_money')    