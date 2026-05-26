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

import logging

logger = logging.getLogger(__name__)



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
        
        logger.warning(
            "Invalid apply coupon request method | user_id=%s | email=%s | method=%s",
            request.user.id,
            request.user.email,
            request.method,
        )

        return redirect('checkout')

    coupon_code = request.POST.get('coupon_code', '').strip().upper()

    if not coupon_code:
        
        logger.warning(
            "Coupon apply failed - empty coupon code | user_id=%s | email=%s",
            request.user.id,
            request.user.email,
        )
        
        messages.error(request, "Please enter a coupon code.")
        return redirect('checkout')

    cart = Cart.objects.filter(user=request.user).first()

    if not cart:
        
        logger.warning(
            "Coupon apply failed - cart not found | user_id=%s | email=%s | coupon_code=%s",
            request.user.id,
            request.user.email,
            coupon_code,
        )
        
        messages.error(request, "Cart not found.")
        return redirect('checkout')

    cart_items = CartItem.objects.filter(cart=cart)

    if not cart_items.exists():
        
        logger.warning(
            "Coupon apply failed - empty cart | user_id=%s | email=%s | coupon_code=%s",
            request.user.id,
            request.user.email,
            coupon_code,
        )
        
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
        
        logger.warning(
            "Invalid or inactive coupon attempted | user_id=%s | email=%s | coupon_code=%s | subtotal=%s",
            request.user.id,
            request.user.email,
            coupon_code,
            subtotal,
        )
        
        messages.error(request, "Invalid or inactive coupon.")
        return redirect('checkout')

    current_time = timezone.now()

    if coupon.valid_from > current_time:
        
        logger.warning(
            "Coupon apply failed - coupon not active yet | user_id=%s | email=%s | coupon_code=%s",
            request.user.id,
            request.user.email,
            coupon.code,
        )
        
        messages.error(request, "This coupon is not active yet.")
        return redirect('checkout')

    if coupon.valid_to < current_time:
        
        logger.warning(
            "Coupon apply failed - coupon expired | user_id=%s | email=%s | coupon_code=%s",
            request.user.id,
            request.user.email,
            coupon.code,
        )
        
        messages.error(request, "This coupon has expired.")
        return redirect('checkout')

    if coupon.used_count >= coupon.usage_limit:
        
        logger.warning(
            "Coupon apply failed - usage limit exceeded | user_id=%s | email=%s | coupon_code=%s | used_count=%s | usage_limit=%s",
            request.user.id,
            request.user.email,
            coupon.code,
            coupon.used_count,
            coupon.usage_limit,
        )
        
        messages.error(request, "Coupon usage limit exceeded.")
        return redirect('checkout')
    
    if CouponUsage.objects.filter(coupon=coupon, user=request.user).exists():
        
        logger.warning(
            "Coupon reuse attempt blocked | user_id=%s | email=%s | coupon_code=%s",
            request.user.id,
            request.user.email,
            coupon.code,
        )
        
        messages.error(request, "You have already used this coupon.")
        return redirect('checkout')

    discount_amount, message = coupon.calculate_discount(subtotal)

    if discount_amount <= 0:
        
        logger.warning(
            "Coupon apply failed - discount not applicable | user_id=%s | email=%s | coupon_code=%s | subtotal=%s | message=%s",
            request.user.id,
            request.user.email,
            coupon.code,
            subtotal,
            message,
        )
        
        messages.error(request, message)
        return redirect('checkout')

    request.session['applied_coupon_code'] = coupon.code
    request.session['coupon_discount'] = str(discount_amount)
    
    logger.info(
        "Coupon applied successfully | user_id=%s | email=%s | coupon_code=%s | subtotal=%s | discount=%s",
        request.user.id,
        request.user.email,
        coupon.code,
        subtotal,
        discount_amount,
    )


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
    
    applied_coupon_code = request.session.get('applied_coupon_code')

    request.session.pop('applied_coupon_code', None)
    request.session.pop('coupon_discount', None)
    
    logger.info(
        "Coupon removed from session | user_id=%s | email=%s | coupon_code=%s",
        request.user.id,
        request.user.email,
        applied_coupon_code,
    )

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
        
        logger.info(
            "Checkout opened in buy-now mode | user_id=%s | email=%s | variant_id=%s",
            request.user.id,
            request.user.email,
            buy_now_variant_id,
        )

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
            
            logger.warning(
                "Checkout buy-now item unavailable | user_id=%s | email=%s | variant_id=%s",
                request.user.id,
                request.user.email,
                buy_now_variant_id,
            )
            
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
            
            logger.warning(
                "Checkout blocked - cart not found | user_id=%s | email=%s",
                request.user.id,
                request.user.email,
            )
            
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
            
            logger.warning(
                "Checkout blocked - empty cart | user_id=%s | email=%s",
                request.user.id,
                request.user.email,
            )
            
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
                
                logger.warning(
                    "Checkout blocked - unavailable cart item | user_id=%s | email=%s | variant_id=%s | quantity=%s | stock=%s",
                    request.user.id,
                    request.user.email,
                    variant.id if variant else None,
                    item.quantity,
                    variant.stock if variant else None,
                )
                
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
                
                logger.warning(
                    "Checkout removed invalid coupon discount | user_id=%s | email=%s | coupon_code=%s | subtotal=%s | message=%s",
                    request.user.id,
                    request.user.email,
                    applied_coupon_code,
                    subtotal,
                    message,
                )
                
                request.session.pop('applied_coupon_code', None)
                request.session.pop('coupon_discount', None)
                messages.error(request, message)
        else:
            
            logger.warning(
                "Checkout removed unavailable coupon | user_id=%s | email=%s | coupon_code=%s",
                request.user.id,
                request.user.email,
                applied_coupon_code,
            )
            
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

    logger.info(
        "Checkout viewed | user_id=%s | email=%s | mode=%s | subtotal=%s | discount=%s | final_total=%s | item_count=%s | has_default_address=%s",
        request.user.id,
        request.user.email,
        "buy_now" if buy_now_variant_id else "cart",
        subtotal,
        discount,
        final_total,
        len(cart_items) if isinstance(cart_items, list) else cart_items.count(),
        bool(default_address),
    )

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
        
        logger.warning(
            "Invalid place order request method | user_id=%s | email=%s | method=%s",
            request.user.id,
            request.user.email,
            request.method,
        )
        
        return redirect('checkout')


    selected_address_id = request.POST.get('selected_address')
    payment_method = request.POST.get('payment_method')


    if not selected_address_id:
        
        logger.warning(
            "Order placement blocked - no address selected | user_id=%s | email=%s",
            request.user.id,
            request.user.email,
        )
        
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
        
        logger.warning(
            "Order placement blocked - invalid address | user_id=%s | email=%s | address_id=%s",
            request.user.id,
            request.user.email,
            selected_address_id,
        )

        messages.error(
            request,
            "Selected address is invalid."
        )
        return redirect('checkout')


    if payment_method not in ['cod', 'razorpay', 'wallet']:
        
        logger.warning(
            "Invalid payment method selected | user_id=%s | email=%s | payment_method=%s",
            request.user.id,
            request.user.email,
            payment_method,
        )
        
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
            
            logger.warning(
                "Order placement blocked - buy now variant unavailable | user_id=%s | email=%s | variant_id=%s",
                request.user.id,
                request.user.email,
                buy_now_variant_id,
            )
            
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
            
            logger.warning(
                "Order placement blocked - cart not found | user_id=%s | email=%s",
                request.user.id,
                request.user.email,
            )
            
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
            
            logger.warning(
                "Order placement blocked - empty cart | user_id=%s | email=%s",
                request.user.id,
                request.user.email,
            )
            
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
            
            logger.warning(
                "Order placement blocked - stock validation failed | user_id=%s | email=%s | variant_id=%s | requested_quantity=%s | stock=%s",
                request.user.id,
                request.user.email,
                item.variant_id,
                item.quantity,
                variant.stock if variant else None,
            )
            
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
                
                logger.warning(
                    "Order placement removed invalid coupon discount | user_id=%s | email=%s | coupon_code=%s | subtotal=%s | message=%s",
                    request.user.id,
                    request.user.email,
                    applied_coupon_code,
                    subtotal,
                    message,
                )
                
                request.session.pop('applied_coupon_code', None)
                request.session.pop('coupon_discount', None)

        else:
            
            logger.warning(
                "Order placement removed unavailable coupon | user_id=%s | email=%s | coupon_code=%s",
                request.user.id,
                request.user.email,
                applied_coupon_code,
            )
            
            request.session.pop('applied_coupon_code', None)
            request.session.pop('coupon_discount', None)

    final_total = subtotal + tax + shipping_charge - discount
    
    if payment_method == 'wallet':
        wallet, created = Wallet.objects.get_or_create(user=request.user)

        if wallet.balance < final_total:
            
            logger.warning(
                "Wallet payment failed - insufficient balance | user_id=%s | email=%s | wallet_balance=%s | required_amount=%s",
                request.user.id,
                request.user.email,
                wallet.balance,
                final_total,
            )
            
            messages.error(request, "Insufficient wallet balance.")
            return redirect('checkout')

    logger.info(
        "Order creation initiated | user_id=%s | email=%s | payment_method=%s | subtotal=%s | discount=%s | final_total=%s | coupon_code=%s",
        request.user.id,
        request.user.email,
        payment_method,
        subtotal,
        discount,
        final_total,
        coupon_code,
    )
    

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
    
    logger.info(
        "Order created successfully | user_id=%s | email=%s | order_id=%s | payment_method=%s | final_total=%s",
        request.user.id,
        request.user.email,
        order.order_id,
        payment_method,
        final_total,
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
        
        reward_referrer_after_first_order(order)

        logger.info(
            "COD order placed successfully | user_id=%s | email=%s | order_id=%s | final_total=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            final_total,
        )

        messages.success(request, "Order placed successfully.")
        return redirect('order_success', order_id=order.order_id)
                
    
    if payment_method == 'wallet':
        wallet, created = Wallet.objects.get_or_create(user=request.user)

        old_wallet_balance = wallet.balance

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
        
        logger.info(
            "Wallet order placed successfully | user_id=%s | email=%s | order_id=%s | amount=%s | old_wallet_balance=%s | remaining_wallet_balance=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            final_total,
            old_wallet_balance,
            wallet.balance,
        )
        
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
        
        logger.info(
            "Razorpay order created | user_id=%s | email=%s | order_id=%s | razorpay_order_id=%s | amount=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            razorpay_order['id'],
            final_total,
        )


        return redirect('razorpay_payment', order_id=order.order_id)

    reward_referrer_after_first_order(order)
    
    logger.info(
        "Order placed successfully | user_id=%s | email=%s | order_id=%s | payment_method=%s | final_total=%s",
        request.user.id,
        request.user.email,
        order.order_id,
        payment_method,
        final_total,
    )
    
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
        logger.warning(
            "Invalid Razorpay verification request method | user_id=%s | email=%s | method=%s",
            request.user.id,
            request.user.email,
            request.method,
        )
        return redirect('checkout')

    razorpay_order_id = request.POST.get('razorpay_order_id')
    razorpay_payment_id = request.POST.get('razorpay_payment_id')
    razorpay_signature = request.POST.get('razorpay_signature')

    payment = get_object_or_404(
        Payment,
        razorpay_order_id=razorpay_order_id,
        order__user=request.user
    )
    
    if payment.status == 'paid':

        logger.warning(
            "Duplicate Razorpay verification blocked | user_id=%s | email=%s | order_id=%s | razorpay_order_id=%s",
            request.user.id,
            request.user.email,
            payment.order.order_id,
            razorpay_order_id,
        )

        return redirect(
            'order_success',
            order_id=payment.order.order_id
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
                old_stock = variant.stock

                variant.stock -= item.quantity

                if variant.stock <= 0:
                    variant.stock = 0
                    variant.is_active = False

                variant.save(update_fields=['stock', 'is_active'])

                logger.info(
                    "Stock reduced after Razorpay payment | user_id=%s | email=%s | order_id=%s | variant_id=%s | old_stock=%s | new_stock=%s | quantity=%s",
                    request.user.id,
                    request.user.email,
                    order.order_id,
                    variant.id,
                    old_stock,
                    variant.stock,
                    item.quantity,
                )

        cart = Cart.objects.filter(user=request.user).first()

        if request.session.get('buy_now_variant_id'):
            del request.session['buy_now_variant_id']
        elif cart:
            CartItem.objects.filter(cart=cart).delete()

        reward_referrer_after_first_order(order)

        logger.info(
            "Razorpay payment verified successfully | user_id=%s | email=%s | order_id=%s | razorpay_order_id=%s | razorpay_payment_id=%s | amount=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            razorpay_order_id,
            razorpay_payment_id,
            order.final_total,
        )

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

        logger.exception(
            "Razorpay payment verification failed | user_id=%s | email=%s | order_id=%s | razorpay_order_id=%s | razorpay_payment_id=%s | error=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            razorpay_order_id,
            razorpay_payment_id,
            error,
        )

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

        logger.warning(
            "Razorpay payment marked as failed | user_id=%s | email=%s | order_id=%s",
            request.user.id,
            request.user.email,
            order.order_id,
        )

        order.payment_status = 'failed'
        order.status = 'payment_failed'
        order.save(update_fields=['payment_status', 'status', 'updated_at'])

        if hasattr(order, 'payment') and order.payment.status == 'created':

            logger.warning(
                "Payment object marked as failed | user_id=%s | email=%s | order_id=%s | razorpay_order_id=%s",
                request.user.id,
                request.user.email,
                order.order_id,
                order.payment.razorpay_order_id,
            )

            order.payment.status = 'failed'
            order.payment.failure_reason = 'Payment failed or cancelled by user.'
            order.payment.save(update_fields=['status', 'failure_reason', 'updated_at'])

    logger.info(
        "User viewed payment failed page | user_id=%s | email=%s | order_id=%s",
        request.user.id,
        request.user.email,
        order.order_id,
    )

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

        logger.warning(
            "Order success page access failed - order not found | user_id=%s | email=%s | order_id=%s",
            request.user.id,
            request.user.email,
            order_id,
        )

        messages.error(request, "Order not found.")
        return redirect('home')

    logger.info(
        "User viewed order success page | user_id=%s | email=%s | order_id=%s | payment_method=%s | payment_status=%s | final_total=%s",
        request.user.id,
        request.user.email,
        order.order_id,
        order.payment_method,
        order.payment_status,
        order.final_total,
    )

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

        logger.info(
            "User searched orders | user_id=%s | email=%s | query=%s",
            request.user.id,
            request.user.email,
            search_query,
        )

        orders = orders.filter(
            Q(order_id__icontains=search_query) |
            Q(items__product_name__icontains=search_query)
        ).distinct()

    if status_filter:

        logger.info(
            "User filtered orders by status | user_id=%s | email=%s | status=%s",
            request.user.id,
            request.user.email,
            status_filter,
        )

        orders = orders.filter(status=status_filter)

    paginator = Paginator(orders, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    logger.info(
        "User viewed order list | user_id=%s | email=%s | page=%s | total_orders=%s",
        request.user.id,
        request.user.email,
        page_number or 1,
        orders.count(),
    )

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

        logger.warning(
            "Order detail access failed - order not found | user_id=%s | email=%s | order_id=%s",
            request.user.id,
            request.user.email,
            order_id,
        )

        messages.error(request, "Order not found.")
        return redirect('order_list')

    has_returnable_items = order.items.filter(
        status='delivered'
    ).exists()

    logger.info(
        "User viewed order details | user_id=%s | email=%s | order_id=%s | payment_method=%s | payment_status=%s | order_status=%s | total_items=%s | final_total=%s",
        request.user.id,
        request.user.email,
        order.order_id,
        order.payment_method,
        order.payment_status,
        order.status,
        order.items.count(),
        order.final_total,
    )

    return render(request, 'orders/order_detail.html', {
        'order': order,
        'has_returnable_items': has_returnable_items,
    })

@login_required
@transaction.atomic
def cancel_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    if request.method != 'POST':

        logger.warning(
            "Invalid cancel order request method | user_id=%s | email=%s | order_id=%s | method=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            request.method,
        )

        return redirect('order_detail', order_id=order.order_id)

    if order.status != 'pending':

        logger.warning(
            "Cancel order blocked - invalid order status | user_id=%s | email=%s | order_id=%s | current_status=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            order.status,
        )

        messages.error(request, "Order can only be cancelled before it is shipped.")
        return redirect('order_detail', order_id=order.order_id)

    reason = request.POST.get('reason', '').strip()

    refundable_items = list(order.items.exclude(status__in=['cancelled', 'returned']))

    logger.info(
        "Order cancellation initiated | user_id=%s | email=%s | order_id=%s | payment_method=%s | payment_status=%s | reason=%s",
        request.user.id,
        request.user.email,
        order.order_id,
        order.payment_method,
        order.payment_status,
        reason,
    )

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

                old_stock = item.variant.stock

                item.variant.stock += item.quantity
                item.variant.is_active = True
                item.variant.save(update_fields=['stock', 'is_active'])

                logger.info(
                    "Stock restored after order cancellation | user_id=%s | email=%s | order_id=%s | variant_id=%s | old_stock=%s | new_stock=%s | restored_quantity=%s",
                    request.user.id,
                    request.user.email,
                    order.order_id,
                    item.variant.id,
                    old_stock,
                    item.variant.stock,
                    item.quantity,
                )

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

        logger.info(
            "Refund credited after full order cancellation | user_id=%s | email=%s | order_id=%s | refund_amount=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            refund_amount,
        )

    logger.info(
        "Order cancelled successfully | user_id=%s | email=%s | order_id=%s",
        request.user.id,
        request.user.email,
        order.order_id,
    )

    messages.success(request, "Order cancelled successfully.")
    return redirect('order_detail', order_id=order.order_id)


@login_required
@transaction.atomic
def cancel_order_item(request, item_id):
    if request.method != 'POST':
        logger.warning(
            "Invalid cancel order item request method | user_id=%s | email=%s | item_id=%s | method=%s",
            request.user.id,
            request.user.email,
            item_id,
            request.method,
        )

        return redirect('order_list')

    item = get_object_or_404(
        OrderItem,
        id=item_id,
        order__user=request.user
    )

    order = item.order

    if order.status != 'pending':
        logger.warning(
            "Cancel order item blocked - invalid order status | user_id=%s | email=%s | order_id=%s | item_id=%s | current_order_status=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            item.id,
            order.status,
        )

        messages.error(request, "Items can only be cancelled before the order is shipped.")
        return redirect('order_detail', order_id=order.order_id)

    if item.status in ['cancelled', 'delivered', 'returned']:
        logger.warning(
            "Cancel order item blocked - invalid item status | user_id=%s | email=%s | order_id=%s | item_id=%s | item_status=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            item.id,
            item.status,
        )

        messages.error(request, f"Item cannot be cancelled as it is already {item.status}.")
        return redirect('order_detail', order_id=order.order_id)

    reason = request.POST.get('reason', '').strip()

    logger.info(
        "Order item cancellation initiated | user_id=%s | email=%s | order_id=%s | item_id=%s | product=%s | reason=%s",
        request.user.id,
        request.user.email,
        order.order_id,
        item.id,
        item.product_name,
        reason,
    )

    item.status = 'cancelled'
    item.cancelled_at = timezone.now()
    item.cancellation_reason = reason
    item.save(update_fields=['status', 'cancelled_at', 'cancellation_reason'])

    if item.variant:
        old_stock = item.variant.stock

        item.variant.stock += item.quantity
        item.variant.is_active = True
        item.variant.save(update_fields=['stock', 'is_active'])

        logger.info(
            "Stock restored after item cancellation | user_id=%s | email=%s | order_id=%s | item_id=%s | variant_id=%s | old_stock=%s | new_stock=%s | restored_quantity=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            item.id,
            item.variant.id,
            old_stock,
            item.variant.stock,
            item.quantity,
        )

    if not order.items.exclude(status='cancelled').exists():
        order.status = 'cancelled'
        order.cancelled_at = timezone.now()
        order.cancellation_reason = reason
        order.save(update_fields=['status', 'cancelled_at', 'cancellation_reason', 'updated_at'])

        logger.info(
            "Order marked cancelled because all items cancelled | user_id=%s | email=%s | order_id=%s",
            request.user.id,
            request.user.email,
            order.order_id,
        )

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

        logger.info(
            "Refund credited after item cancellation | user_id=%s | email=%s | order_id=%s | item_id=%s | refund_amount=%s | new_payment_status=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            item.id,
            refund_amount,
            order.payment_status,
        )

    messages.success(request, f"Item '{item.product_name}' cancelled successfully.")
    return redirect('order_detail', order_id=order.order_id)



@login_required
@transaction.atomic
def return_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    if request.method != 'POST':

        logger.warning(
            "Invalid return order request method | user_id=%s | email=%s | order_id=%s | method=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            request.method,
        )

        return redirect('order_detail', order_id=order.order_id)

    reason = request.POST.get('reason', '').strip()

    if not reason:

        logger.warning(
            "Return order blocked - missing reason | user_id=%s | email=%s | order_id=%s",
            request.user.id,
            request.user.email,
            order.order_id,
        )

        messages.error(request, "Return reason is required.")
        return redirect('order_detail', order_id=order.order_id)

    if order.status != 'delivered':

        logger.warning(
            "Return order blocked - invalid order status | user_id=%s | email=%s | order_id=%s | current_status=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            order.status,
        )

        messages.error(request, "Only delivered orders can be returned.")
        return redirect('order_detail', order_id=order.order_id)

    returnable_items = order.items.filter(status='delivered')

    if not returnable_items.exists():

        logger.warning(
            "Return order blocked - no returnable items | user_id=%s | email=%s | order_id=%s",
            request.user.id,
            request.user.email,
            order.order_id,
        )

        messages.error(request, "No delivered items are available for return.")
        return redirect('order_detail', order_id=order.order_id)

    logger.info(
        "Full order return requested | user_id=%s | email=%s | order_id=%s | total_items=%s | reason=%s",
        request.user.id,
        request.user.email,
        order.order_id,
        returnable_items.count(),
        reason,
    )

    for item in returnable_items:
        item.status = 'return_requested'
        item.return_reason = reason
        item.return_requested = timezone.now()
        item.save(update_fields=['status', 'return_reason', 'return_requested'])

        logger.info(
            "Return requested for order item | user_id=%s | email=%s | order_id=%s | item_id=%s | product=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            item.id,
            item.product_name,
        )

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

        logger.warning(
            "Invalid return item request method | user_id=%s | email=%s | order_id=%s | item_id=%s | method=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            item.id,
            request.method,
        )

        return redirect('order_detail', order_id=order.order_id)

    reason = request.POST.get('reason', '').strip()

    if not reason:

        logger.warning(
            "Return item blocked - missing reason | user_id=%s | email=%s | order_id=%s | item_id=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            item.id,
        )

        messages.error(request, "Return reason is required.")
        return redirect('order_detail', order_id=order.order_id)

    if order.status != 'delivered':

        logger.warning(
            "Return item blocked - invalid order status | user_id=%s | email=%s | order_id=%s | current_status=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            order.status,
        )

        messages.error(request, "Only delivered items can be returned.")
        return redirect('order_detail', order_id=order.order_id)

    if item.status != 'delivered':

        logger.warning(
            "Return item blocked - invalid item status | user_id=%s | email=%s | order_id=%s | item_id=%s | item_status=%s",
            request.user.id,
            request.user.email,
            order.order_id,
            item.id,
            item.status,
        )

        messages.error(request, "Only delivered items can be returned.")
        return redirect('order_detail', order_id=order.order_id)

    logger.info(
        "Return requested for individual item | user_id=%s | email=%s | order_id=%s | item_id=%s | product=%s | reason=%s",
        request.user.id,
        request.user.email,
        order.order_id,
        item.id,
        item.product_name,
        reason,
    )

    item.status = 'return_requested'
    item.return_reason = reason
    item.return_requested = timezone.now()

    item.save(update_fields=[
        'status',
        'return_reason',
        'return_requested'
    ])

    logger.info(
        "Return request saved successfully | user_id=%s | email=%s | order_id=%s | item_id=%s",
        request.user.id,
        request.user.email,
        order.order_id,
        item.id,
    )

    messages.success(
        request,
        f"Return request submitted for '{item.product_name}'. Admin will review it."
    )

    return redirect('order_detail', order_id=order.order_id)


@login_required
def download_invoice(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    logger.info(
        "Invoice download requested | user_id=%s | email=%s | order_id=%s",
        request.user.id,
        request.user.email,
        order.order_id,
    )

    html_string = render_to_string('orders/invoice_pdf.html', {
        'order': order,
    })

    buffer = io.BytesIO()

    pisa_status = pisa.CreatePDF(
        io.BytesIO(html_string.encode("UTF-8")),
        dest=buffer
    )

    if pisa_status.err:
        logger.error(
            "Invoice PDF generation failed | user_id=%s | email=%s | order_id=%s",
            request.user.id,
            request.user.email,
            order.order_id,
        )

        return HttpResponse('We had some errors <pre>' + html_string + '</pre>')

    pdf = buffer.getvalue()
    buffer.close()

    logger.info(
        "Invoice PDF generated successfully | user_id=%s | email=%s | order_id=%s",
        request.user.id,
        request.user.email,
        order.order_id,
    )

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="VERSE_Invoice_{order.order_id}.pdf"'
    response.write(pdf)

    return response
