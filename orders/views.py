from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from cart.models import Cart, CartItem
from userprofile.models import Address
from .models import Order, OrderItem
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
import io
from xhtml2pdf import pisa
from django.db.models import Q
from django.core.paginator import Paginator
from products.models import Variant
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from payments.models import Payment, Wallet, WalletTransaction
from payments.utils import reward_referrer_after_first_order
import razorpay
from coupons.models import Coupon, CouponUsage
from offers.utils import calculate_best_offer
from django.db import models


def credit_wallet(user, amount, order, reason):
    wallet, created = Wallet.objects.get_or_create(user=user)

    wallet.balance += amount
    wallet.save(update_fields=['balance', 'updated_at'])

    WalletTransaction.objects.create(
        wallet=wallet,
        order=order,
        transaction_type='credit',
        amount=amount,
        reason=reason
    )

def get_refund_amount(order, items):
    items = list(items)

    refund_amount = sum(
        item.final_item_total if item.final_item_total > 0 else item.item_total
        for item in items
    )

    return Decimal(refund_amount).quantize(Decimal('0.01'))
    
@login_required
def apply_coupon_view(request):

    if request.method != 'POST':
        return redirect('checkout')

    coupon_code = request.POST.get('coupon_code', '').strip().upper()

    if not coupon_code:
        messages.error(request, "Please enter a coupon code.")
        return redirect('checkout')

    cart = Cart.objects.filter(user=request.user).first()

    if not cart:
        messages.error(request, "Cart not found.")
        return redirect('checkout')

    cart_items = CartItem.objects.filter(cart=cart)

    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('checkout')

    subtotal = Decimal("0.00")

    for item in cart_items:
        offer_data = calculate_best_offer(item.variant)
        subtotal += offer_data["final_price"] * item.quantity

    coupon = Coupon.objects.filter(
        code__iexact=coupon_code,
        is_active=True
    ).first()

    if not coupon:
        messages.error(request, "Invalid or inactive coupon.")
        return redirect('checkout')

    current_time = timezone.now()

    if coupon.valid_from > current_time:
        messages.error(request, "This coupon is not active yet.")
        return redirect('checkout')

    if coupon.valid_to < current_time:
        messages.error(request, "This coupon has expired.")
        return redirect('checkout')

    if coupon.used_count >= coupon.usage_limit:
        messages.error(request, "Coupon usage limit exceeded.")
        return redirect('checkout')
    
    if CouponUsage.objects.filter(coupon=coupon, user=request.user).exists():
        messages.error(request, "You have already used this coupon.")
        return redirect('checkout')

    discount_amount, message = coupon.calculate_discount(subtotal)

    if discount_amount <= 0:
        messages.error(request, message)
        return redirect('checkout')

    request.session['applied_coupon_code'] = coupon.code
    request.session['coupon_discount'] = str(discount_amount)

    success_message = f'Coupon "{coupon.code}" applied successfully.'

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': success_message,
        })

    messages.success(request, success_message)
    return redirect('checkout')


@login_required
def remove_coupon_view(request):

    request.session.pop('applied_coupon_code', None)
    request.session.pop('coupon_discount', None)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': "Coupon removed successfully.",
        })

    messages.success(request, "Coupon removed successfully.")
    return redirect('checkout')

    

@login_required
def checkout_view(request):
    buy_now_variant_id = request.session.get('buy_now_variant_id')

    if buy_now_variant_id:

        variant = Variant.objects.filter(
            id=buy_now_variant_id,
            is_active=True,
            is_deleted=False,
            product__is_active=True,
            product__is_deleted=False,
            product__category__is_active=True,
            product__category__is_deleted=False,
        ).prefetch_related('images').first()

        if not variant or variant.stock <= 0:
            messages.error(request, "Selected product is unavailable.")
            return redirect('product_listing')

        class BuyNowItem:
            def __init__(self, variant, quantity):
                self.variant = variant
                self.variant_id = variant.id
                self.quantity = quantity
                self.subtotal = variant.price * quantity

        cart = None
        cart_items = [BuyNowItem(variant, 1)]

    else:

        cart = Cart.objects.filter(user=request.user).first()

        if not cart:
            messages.error(request, "Your cart is empty.")
            return redirect('cart_view')

        cart_items = CartItem.objects.filter(
            cart=cart
        ).select_related(
            'variant',
            'variant__product',
            'variant__product__category'
        ).prefetch_related(
            'variant__images'
        )

        if not cart_items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect('cart_view')

        for item in cart_items:
            variant = item.variant

            if (
                not variant or
                variant.is_deleted or
                not variant.is_active or
                variant.stock <= 0 or
                variant.stock < item.quantity
            ):
                messages.error(
                    request,
                    f"{variant.product.product_name if variant and variant.product else 'A product'} is no longer available."
                )
                return redirect('cart_view')
    

    addresses = Address.objects.filter(
        user=request.user
    ).order_by('-is_default', '-created_at')

    default_address = addresses.filter(is_default=True).first()

    subtotal = Decimal('0.00')

    for item in cart_items:
        offer_data = calculate_best_offer(item.variant)

        item.offer_data = offer_data
        item.discounted_price = offer_data['final_price']
        item.offer_discount = offer_data['discount_amount']
        item.discounted_subtotal = item.discounted_price * item.quantity

        subtotal += item.discounted_subtotal

    discount = Decimal('0.00')
    shipping_charge = Decimal('0.00')
    tax = Decimal('0.00')
    applied_coupon_code = request.session.get('applied_coupon_code')

    if applied_coupon_code:
        coupon = Coupon.objects.filter(
            code__iexact=applied_coupon_code,
            is_active=True
        ).first()

        if coupon:
            discount, message = coupon.calculate_discount(subtotal)

            if discount <= 0:
                request.session.pop('applied_coupon_code', None)
                request.session.pop('coupon_discount', None)
                messages.error(request, message)
        else:
            request.session.pop('applied_coupon_code', None)
            request.session.pop('coupon_discount', None)
            messages.error(request, "Applied coupon is no longer available.")

    final_total = subtotal + tax + shipping_charge - discount
    
    for item in cart_items:

        item_discount = Decimal('0.00')

        item_subtotal = item.discounted_subtotal

        if subtotal > 0 and discount > 0:
            item_discount = (item_subtotal / subtotal) * discount
            item_discount = item_discount.quantize(Decimal('0.01'))

        item.discount_share = item_discount
        item.final_price_after_discount = item_subtotal - item_discount
        
    available_coupons = Coupon.objects.filter(
        is_active=True,
        valid_from__lte=timezone.now(),
        valid_to__gte=timezone.now(),
        used_count__lt=models.F('usage_limit')
    )
    
    best_coupon = None
    best_discount = 0

    for coupon in available_coupons:
        discount_amount, _ = coupon.calculate_discount(subtotal)

        if discount_amount > best_discount:
            best_discount = discount_amount
            best_coupon = coupon

    context = {
        'cart': cart,
        'cart_items': cart_items,
        'addresses': addresses,
        'default_address': default_address,
        'subtotal': subtotal,
        'discount': discount,
        'shipping_charge': shipping_charge,
        'tax': tax,
        'final_total': final_total,
        'applied_coupon_code': applied_coupon_code,
        'available_coupons': available_coupons,
        'best_coupon': best_coupon,
    }

    return render(request, 'orders/checkout.html', context)


@login_required
@transaction.atomic
def place_order_view(request):

    if request.method != 'POST':
        return redirect('checkout')


    selected_address_id = request.POST.get('selected_address')
    payment_method = request.POST.get('payment_method')


    if not selected_address_id:
        messages.error(
            request,
            "Please add or select a delivery address before placing your order."
        )
        return redirect('checkout')

    address = Address.objects.filter(
        id=selected_address_id,
        user=request.user
    ).first()

    if not address:
        messages.error(
            request,
            "Selected address is invalid."
        )
        return redirect('checkout')


    if payment_method not in ['cod', 'razorpay', 'wallet']:
        messages.error(request, "Invalid payment method selected.")
        return redirect('checkout')


    buy_now_variant_id = request.session.get('buy_now_variant_id')

    if buy_now_variant_id:

        variant = Variant.objects.filter(
            id=buy_now_variant_id,
            is_active=True,
            is_deleted=False,
            product__is_active=True,
            product__is_deleted=False,
            product__category__is_active=True,
            product__category__is_deleted=False,
        ).first()

        if not variant or variant.stock <= 0:
            messages.error(request, "Selected product is unavailable.")
            return redirect('checkout')

        class BuyNowItem:
            def __init__(self, variant, quantity):
                self.variant = variant
                self.variant_id = variant.id
                self.quantity = quantity
                self.subtotal = variant.price * quantity

        cart = None
        cart_items = [BuyNowItem(variant, 1)]
        variant_ids = [variant.id]

    else:

        cart = Cart.objects.filter(user=request.user).first()

        if not cart:
            messages.error(request, "Your cart is empty.")
            return redirect('cart_view')

        cart_items = CartItem.objects.filter(
            cart=cart
        ).select_related(
            'variant',
            'variant__product',
            'variant__product__category'
        ).order_by('variant_id')

        if not cart_items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect('cart_view')

        variant_ids = list(cart_items.values_list('variant_id', flat=True))

    locked_variants = {
        variant.id: variant
        for variant in Variant.objects.select_for_update().filter(id__in=variant_ids)
    }

    for item in cart_items:
        variant = locked_variants.get(item.variant_id)
        if (
            not variant or
            variant.is_deleted or
            not variant.is_active or
            variant.stock <= 0 or
            variant.stock < item.quantity
        ):
            product_name = item.variant.product.product_name if item.variant and item.variant.product else 'Product'
            messages.error(
                request,
                f"{product_name} is out of stock or unavailable."
            )
            return redirect('cart_view')


    subtotal = Decimal('0.00')

    for item in cart_items:
        offer_data = calculate_best_offer(item.variant)

        item.original_subtotal = item.variant.price * item.quantity
        item.offer_discount = offer_data['discount_amount'] * item.quantity
        item.discounted_price = offer_data['final_price']
        item.discounted_subtotal = item.discounted_price * item.quantity

        subtotal += item.discounted_subtotal

    discount = Decimal('0.00')
    shipping_charge = Decimal('0.00')
    tax = Decimal('0.00')
    coupon_code = None

    applied_coupon_code = request.session.get('applied_coupon_code')

    if applied_coupon_code:

        coupon = Coupon.objects.filter(
            code__iexact=applied_coupon_code,
            is_active=True
        ).first()

        if coupon:

            discount, message = coupon.calculate_discount(subtotal)

            if discount > 0:
                coupon_code = coupon.code
            else:
                request.session.pop('applied_coupon_code', None)
                request.session.pop('coupon_discount', None)

        else:
            request.session.pop('applied_coupon_code', None)
            request.session.pop('coupon_discount', None)

    final_total = subtotal + tax + shipping_charge - discount
    
    if payment_method == 'wallet':
        wallet, created = Wallet.objects.get_or_create(user=request.user)

        if wallet.balance < final_total:
            messages.error(request, "Insufficient wallet balance.")
            return redirect('checkout')


    order = Order.objects.create(
        user=request.user,

        full_name=address.full_name,
        phone_number=address.phone_number,
        address_line1=address.address_line1,
        address_line2=address.address_line2,
        city=address.city,
        state=address.state,
        pincode=address.pincode,
        country=address.country,

        payment_method=payment_method,
        payment_status='pending',
        status='pending',

        subtotal=subtotal,
        discount=discount,
        coupon_code=coupon_code,
        shipping_charge=shipping_charge,
        tax=tax,
        final_total=final_total,
    )
    
    
    item_pricing_data = {}

    for item in cart_items:
        original_item_total = item.original_subtotal
        offer_discount = item.offer_discount
        discounted_item_total = item.discounted_subtotal

        coupon_discount_share = Decimal('0.00')

        if subtotal > 0 and discount > 0:
            coupon_discount_share = (discounted_item_total / subtotal) * discount
            coupon_discount_share = coupon_discount_share.quantize(Decimal('0.01'))

        final_item_total = discounted_item_total - coupon_discount_share

        item_pricing_data[item.variant_id] = {
            "original_item_total": original_item_total,
            "offer_discount": offer_discount,
            "coupon_discount_share": coupon_discount_share,
            "final_item_total": final_item_total,
        }
    
    

    for item in cart_items:
        variant = locked_variants[item.variant_id]
        
        OrderItem.objects.create(
            order=order,
            variant=variant,
            product_name=variant.product.product_name,
            category_name=variant.product.category.category_name if variant.product.category else '',
            color=variant.color,
            size=variant.size,
            sku=variant.sku,
            price=variant.price,
            quantity=item.quantity,
            item_total=item.discounted_subtotal,
            original_item_total=item_pricing_data[item.variant_id]["original_item_total"],
            offer_discount=item_pricing_data[item.variant_id]["offer_discount"],
            coupon_discount_share=item_pricing_data[item.variant_id]["coupon_discount_share"],
            final_item_total=item_pricing_data[item.variant_id]["final_item_total"],
            status='pending',
        )

    
    if payment_method == 'cod':

        for item in cart_items:
            variant = locked_variants[item.variant_id]

            variant.stock -= item.quantity

            if variant.stock <= 0:
                variant.stock = 0
                variant.is_active = False

            variant.save(update_fields=['stock', 'is_active'])

        if cart:
            cart_items.delete()

        if request.session.get('buy_now_variant_id'):
            del request.session['buy_now_variant_id']
        
        if coupon_code:
            used_coupon = Coupon.objects.filter(code__iexact=coupon_code).first()

            if used_coupon:
                CouponUsage.objects.get_or_create(
                    coupon=used_coupon,
                    user=request.user,
                    defaults={"order": order}
                )

                Coupon.objects.filter(id=used_coupon.id).update(
                    used_count=models.F('used_count') + 1
                )

        request.session.pop('applied_coupon_code', None)
        request.session.pop('coupon_discount', None)
                
    
    if payment_method == 'wallet':
        wallet, created = Wallet.objects.get_or_create(user=request.user)

        wallet.balance -= final_total
        wallet.save(update_fields=['balance', 'updated_at'])

        WalletTransaction.objects.create(
            wallet=wallet,
            order=order,
            transaction_type='debit',
            amount=final_total,
            reason=f"Wallet payment for order {order.order_id}"
        )

        for item in cart_items:
            variant = locked_variants[item.variant_id]

            variant.stock -= item.quantity

            if variant.stock <= 0:
                variant.stock = 0
                variant.is_active = False

            variant.save(update_fields=['stock', 'is_active'])

        Payment.objects.create(
            order=order,
            method='wallet',
            status='paid',
            amount=final_total
        )

        order.payment_status = 'paid'
        order.save(update_fields=['payment_status', 'updated_at'])

        if cart:
            cart_items.delete()

        if request.session.get('buy_now_variant_id'):
            del request.session['buy_now_variant_id']

        if coupon_code:
            used_coupon = Coupon.objects.filter(code__iexact=coupon_code).first()

            if used_coupon:
                CouponUsage.objects.get_or_create(
                    coupon=used_coupon,
                    user=request.user,
                    defaults={"order": order}
                )

                Coupon.objects.filter(id=used_coupon.id).update(
                    used_count=models.F('used_count') + 1
                )

        request.session.pop('applied_coupon_code', None)
        request.session.pop('coupon_discount', None)
        
        reward_referrer_after_first_order(order)
        
        messages.success(request, "Order placed successfully using wallet.")
        return redirect('order_success', order_id=order.order_id)    
        
    

    if payment_method == 'razorpay':
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        razorpay_order = client.order.create({
            "amount": int(order.final_total * 100),
            "currency": "INR",
            "payment_capture": 1,
            "receipt": order.order_id,
        })

        Payment.objects.create(
            order=order,
            method='razorpay',
            status='created',
            amount=order.final_total,
            razorpay_order_id=razorpay_order['id'],
        )

        return redirect('razorpay_payment', order_id=order.order_id)

    reward_referrer_after_first_order(order)
    
    messages.success(request, "Order placed successfully.")
    return redirect('order_success', order_id=order.order_id)




@login_required
def razorpay_payment_view(request, order_id):
    order = get_object_or_404(
        Order,
        order_id=order_id,
        user=request.user,
        payment_method='razorpay'
    )

    payment = get_object_or_404(Payment, order=order)

    context = {
        'order': order,
        'payment': payment,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'razorpay_amount': int(order.final_total * 100),
    }

    return render(request, 'orders/razorpay_payment.html', context)


@csrf_exempt
@login_required
@transaction.atomic
def verify_razorpay_payment(request):
    if request.method != 'POST':
        return redirect('checkout')

    razorpay_order_id = request.POST.get('razorpay_order_id')
    razorpay_payment_id = request.POST.get('razorpay_payment_id')
    razorpay_signature = request.POST.get('razorpay_signature')

    payment = get_object_or_404(
        Payment,
        razorpay_order_id=razorpay_order_id,
        order__user=request.user
    )

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })

        payment.status = 'paid'
        payment.razorpay_payment_id = razorpay_payment_id
        payment.razorpay_signature = razorpay_signature
        payment.save(update_fields=[
            'status',
            'razorpay_payment_id',
            'razorpay_signature',
            'updated_at'
        ])

        order = payment.order
        
        if order.coupon_code:
            used_coupon = Coupon.objects.filter(code__iexact=order.coupon_code).first()

            if used_coupon:
                CouponUsage.objects.get_or_create(
                    coupon=used_coupon,
                    user=request.user,
                    defaults={"order": order}
                )

                Coupon.objects.filter(id=used_coupon.id).update(
                    used_count=models.F('used_count') + 1
                )

        request.session.pop('applied_coupon_code', None)
        request.session.pop('coupon_discount', None)
        
        order.payment_status = 'paid'
        

        if order.status == 'payment_failed':
            order.status = 'pending'

        order.save(update_fields=['payment_status', 'status', 'updated_at'])
        
        for item in order.items.select_related('variant').all():
            variant = item.variant

            if variant:
                variant.stock -= item.quantity

                if variant.stock <= 0:
                    variant.stock = 0
                    variant.is_active = False

                variant.save(update_fields=['stock', 'is_active'])

        cart = Cart.objects.filter(user=request.user).first()

        if request.session.get('buy_now_variant_id'):
            del request.session['buy_now_variant_id']
        elif cart:
            CartItem.objects.filter(cart=cart).delete()
        
        reward_referrer_after_first_order(order)    

        messages.success(request, "Payment completed successfully.")
        return redirect('order_success', order_id=order.order_id)

    except Exception as error:
        payment.status = 'failed'
        payment.failure_reason = str(error)
        payment.save(update_fields=['status', 'failure_reason', 'updated_at'])

        order = payment.order
        order.payment_status = 'failed'
        order.status = 'payment_failed'
        order.save(update_fields=['payment_status', 'status', 'updated_at'])

        messages.error(request, "Payment verification failed.")
        return redirect('payment_failed', order_id=order.order_id)
    

@login_required
def payment_failed_view(request, order_id):
    order = get_object_or_404(
        Order,
        order_id=order_id,
        user=request.user
    )

    if order.payment_method == 'razorpay' and order.payment_status == 'pending':
        order.payment_status = 'failed'
        order.status = 'payment_failed'
        order.save(update_fields=['payment_status', 'status', 'updated_at'])

        if hasattr(order, 'payment') and order.payment.status == 'created':
            order.payment.status = 'failed'
            order.payment.failure_reason = 'Payment failed or cancelled by user.'
            order.payment.save(update_fields=['status', 'failure_reason', 'updated_at'])

    return render(request, 'orders/payment_failed.html', {
        'order': order,
    })



@login_required
def order_success_view(request, order_id):

    order = Order.objects.filter(
        order_id=order_id,
        user=request.user
    ).first()

    if not order:
        messages.error(request, "Order not found.")
        return redirect('home')

    context = {
        'order': order,
    }

    return render(
        request,
        'orders/order_success.html',
        context
    )
    
@login_required
def order_list_view(request):
    search_query = request.GET.get('q', '').strip().replace('#', '')
    status_filter = request.GET.get('status', '').strip()

    orders = (
        Order.objects
        .filter(user=request.user)
        .prefetch_related('items')
        .order_by('-created_at')
    )

    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query) |
            Q(items__product_name__icontains=search_query)
        ).distinct()

    if status_filter:
        orders = orders.filter(status=status_filter)

    paginator = Paginator(orders, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'orders': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'total_orders': orders.count(),
    }

    return render(request, 'orders/order_list.html', context)
    

@login_required
def order_detail_view(request, order_id):
    order = Order.objects.filter(
        order_id=order_id,
        user=request.user
    ).prefetch_related(
        'items',
        'items__variant',
        'items__variant__images'
    ).first()

    if not order:
        messages.error(request, "Order not found.")
        return redirect('order_list')

    has_returnable_items = order.items.filter(
        status='delivered'
    ).exists()

    return render(request, 'orders/order_detail.html', {
        'order': order,
        'has_returnable_items': has_returnable_items,
    })



@login_required
@transaction.atomic
def cancel_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    if request.method != 'POST':
        return redirect('order_detail', order_id=order.order_id)

    if order.status != 'pending':
        messages.error(request, "Order can only be cancelled before it is shipped.")
        return redirect('order_detail', order_id=order.order_id)

    reason = request.POST.get('reason', '').strip()
    
    refundable_items = list(order.items.exclude(status__in=['cancelled', 'returned']))

    order.status = 'cancelled'
    order.cancelled_at = timezone.now()
    order.cancellation_reason = reason
    order.save(update_fields=['status', 'cancelled_at', 'cancellation_reason', 'updated_at'])

    for item in order.items.all():
        if item.status != 'cancelled':
            item.status = 'cancelled'
            item.cancelled_at = timezone.now()
            item.cancellation_reason = reason
            item.save(update_fields=['status', 'cancelled_at', 'cancellation_reason'])

            if item.variant:
                item.variant.stock += item.quantity
                item.variant.is_active = True
                item.variant.save(update_fields=['stock', 'is_active'])
                
    
    if order.payment_method in ['razorpay', 'wallet'] and order.payment_status == 'paid':
        refund_amount = get_refund_amount(order, refundable_items)

        credit_wallet(
            user=request.user,
            amount=refund_amount,
            order=order,
            reason=f"Refund for cancelled order {order.order_id}"
        )

        order.payment_status = 'refunded'
        order.save(update_fields=['payment_status', 'updated_at'])

        if hasattr(order, 'payment'):
            order.payment.status = 'refunded'
            order.payment.save(update_fields=['status', 'updated_at'])            

    messages.success(request, "Order cancelled successfully.")
    return redirect('order_detail', order_id=order.order_id)


@login_required
@transaction.atomic
def cancel_order_item(request, item_id):
    if request.method != 'POST':
        return redirect('order_list')

    item = get_object_or_404(
        OrderItem,
        id=item_id,
        order__user=request.user
    )

    order = item.order

    if order.status != 'pending':
        messages.error(request, "Items can only be cancelled before the order is shipped.")
        return redirect('order_detail', order_id=order.order_id)

    if item.status in ['cancelled', 'delivered', 'returned']:
        messages.error(request, f"Item cannot be cancelled as it is already {item.status}.")
        return redirect('order_detail', order_id=order.order_id)

    reason = request.POST.get('reason', '').strip()

    item.status = 'cancelled'
    item.cancelled_at = timezone.now()
    item.cancellation_reason = reason
    item.save(update_fields=['status', 'cancelled_at', 'cancellation_reason'])

    if item.variant:
        item.variant.stock += item.quantity
        item.variant.is_active = True
        item.variant.save(update_fields=['stock', 'is_active'])

    if not order.items.exclude(status='cancelled').exists():
        order.status = 'cancelled'
        order.cancelled_at = timezone.now()
        order.cancellation_reason = reason
        order.save(update_fields=['status', 'cancelled_at', 'cancellation_reason', 'updated_at'])
        
    if order.payment_method in ['razorpay', 'wallet'] and order.payment_status == 'paid':
        refund_amount = get_refund_amount(order, [item])

        credit_wallet(
            user=request.user,
            amount=refund_amount,
            order=order,
            reason=f"Refund for cancelled item: {item.product_name}"
        )

        remaining_active_items = order.items.exclude(status='cancelled')

        if not remaining_active_items.exists():
            order.payment_status = 'refunded'
        else:
            order.payment_status = 'paid'

        order.save(update_fields=['payment_status', 'updated_at'])    

    messages.success(request, f"Item '{item.product_name}' cancelled successfully.")
    return redirect('order_detail', order_id=order.order_id)


@login_required
@transaction.atomic
def return_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    if request.method != 'POST':
        return redirect('order_detail', order_id=order.order_id)

    reason = request.POST.get('reason', '').strip()

    if not reason:
        messages.error(request, "Return reason is required.")
        return redirect('order_detail', order_id=order.order_id)

    if order.status != 'delivered':
        messages.error(request, "Only delivered orders can be returned.")
        return redirect('order_detail', order_id=order.order_id)

    returnable_items = order.items.filter(status='delivered')

    if not returnable_items.exists():
        messages.error(request, "No delivered items are available for return.")
        return redirect('order_detail', order_id=order.order_id)

    for item in returnable_items:
        item.status = 'return_requested'
        item.return_reason = reason
        item.return_requested = timezone.now()
        item.save(update_fields=['status', 'return_reason', 'return_requested'])

    messages.success(request, "Return request submitted. Admin will review it.")
    return redirect('order_detail', order_id=order.order_id)



@login_required
@transaction.atomic
def return_order_item(request, item_id):
    item = get_object_or_404(
        OrderItem,
        id=item_id,
        order__user=request.user
    )

    order = item.order

    if request.method != 'POST':
        return redirect('order_detail', order_id=order.order_id)

    reason = request.POST.get('reason', '').strip()

    if not reason:
        messages.error(request, "Return reason is required.")
        return redirect('order_detail', order_id=order.order_id)

    if order.status != 'delivered':
        messages.error(request, "Only delivered items can be returned.")
        return redirect('order_detail', order_id=order.order_id)

    if item.status != 'delivered':
        messages.error(request, "Only delivered items can be returned.")
        return redirect('order_detail', order_id=order.order_id)

    item.status = 'return_requested'
    item.return_reason = reason
    item.return_requested = timezone.now()
    item.save(update_fields=['status', 'return_reason', 'return_requested'])

    messages.success(request, f"Return request submitted for '{item.product_name}'. Admin will review it.")
    return redirect('order_detail', order_id=order.order_id)



@login_required
def download_invoice(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    html_string = render_to_string('orders/invoice_pdf.html', {
        'order': order,
    })

    buffer = io.BytesIO()

    pisa_status = pisa.CreatePDF(
        io.BytesIO(html_string.encode("UTF-8")),
        dest=buffer
    )

    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html_string + '</pre>')

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="VERSE_Invoice_{order.order_id}.pdf"'
    response.write(pdf)

    return response


