from decimal import Decimal

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from cart.models import Cart, CartItem
from userprofile.models import Address
from .models import Order, OrderItem
from django.db import transaction


@login_required
def checkout_view(request):
    cart = Cart.objects.filter(user=request.user).first()

    if not cart:
        messages.error(request, "Your cart is empty.")
        return redirect('cart')

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
        return redirect('cart')
    

    addresses = Address.objects.filter(
        user=request.user
    ).order_by('-is_default', '-created_at')

    default_address = addresses.filter(is_default=True).first()

    subtotal = sum(item.subtotal for item in cart_items)

    discount = Decimal('0.00')
    shipping_charge = Decimal('0.00')
    tax = Decimal('0.00')

    final_total = subtotal + tax + shipping_charge - discount

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


    if payment_method != 'cod':
        messages.error(
            request,
            "Currently only Cash on Delivery is available."
        )
        return redirect('checkout')


    cart = Cart.objects.filter(user=request.user).first()

    if not cart:
        messages.error(request, "Your cart is empty.")
        return redirect('cart')

    cart_items = CartItem.objects.filter(
        cart=cart
    ).select_related(
        'variant',
        'variant__product',
        'variant__product__category'
    )

    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('cart')


    for item in cart_items:

        variant = item.variant

        if (
            not variant or
            variant.is_deleted or
            not variant.is_active or
            variant.stock < item.quantity
        ):
            messages.error(
                request,
                f"{variant.product.product_name if variant and variant.product else 'Product'} is out of stock or unavailable."
            )
            return redirect('cart')


    subtotal = sum(item.subtotal for item in cart_items)

    discount = Decimal('0.00')
    shipping_charge = Decimal('0.00')
    tax = Decimal('0.00')

    final_total = subtotal + tax + shipping_charge - discount


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

        payment_method='cod',
        payment_status='pending',
        status='pending',

        subtotal=subtotal,
        discount=discount,
        shipping_charge=shipping_charge,
        tax=tax,
        final_total=final_total,
    )

    for item in cart_items:

        variant = item.variant

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
            item_total=item.subtotal,

            status='pending',
        )

        variant.stock -= item.quantity

        if variant.stock <= 0:
            variant.stock = 0
            variant.is_active = False

        variant.save()


    cart_items.delete()

    messages.success(
        request,
        "Order placed successfully."
    )

    return redirect('order_success', order_id=order.order_id)

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
    orders = (
        Order.objects
        .filter(user=request.user)
        .order_by('-created_at')
    )

    return render(request, 'orders/order_list.html', {
        'orders': orders,
    })    
    

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

    return render(request, 'orders/order_detail.html', {
        'order': order,
    })    