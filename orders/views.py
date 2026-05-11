from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from cart.models import Cart, CartItem
from userprofile.models import Address
from .models import Order, OrderItem
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
import io
from xhtml2pdf import pisa
from django.db.models import Q
from django.core.paginator import Paginator


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

    return render(request, 'orders/order_detail.html', {
        'order': order,
    })


@login_required
@transaction.atomic
def cancel_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    
    if request.method != 'POST':
        return redirect('order_detail', order_id=order.order_id)

    if order.status in ['cancelled', 'delivered']:
        messages.error(request, f"Order cannot be cancelled as it is already {order.status}.")
        return redirect('order_detail', order_id=order_id)
    
    reason = request.POST.get('reason', '').strip()


    order.status = 'cancelled'
    order.cancelled_at = timezone.now()
    order.cancellation_reason = reason
    order.save(update_fields=['status', 'cancelled_at', 'cancellation_reason', 'updated_at'])

    for item in order.items.all():
        if item.status != 'cancelled':
            item.status = 'cancelled'
            item.cancellation_reason = reason
            item.cancelled_at = timezone.now()
            item.save(update_fields=['status', 'cancelled_at', 'cancellation_reason'])


            # Restore stock
            if item.variant:
                item.variant.stock += item.quantity
                if not item.variant.is_active and item.variant.stock > 0:
                    item.variant.is_active = True
                item.variant.save(update_fields=['stock', 'is_active'])

    messages.success(request, "Order cancelled successfully.")
    return redirect('order_detail', order_id=order_id)


@login_required
@transaction.atomic
def cancel_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    if request.method != 'POST':
        return redirect('order_detail', order_id=order.order_id)

    if order.status in ['cancelled', 'delivered']:
        messages.error(request, f"Order cannot be cancelled as it is already {order.status}.")
        return redirect('order_detail', order_id=order.order_id)

    reason = request.POST.get('reason', '').strip()

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

    if order.status in ['cancelled', 'delivered']:
        messages.error(request, f"Item cannot be cancelled because the order is {order.status}.")
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

    for item in order.items.exclude(status__in=['cancelled', 'returned']):
        item.status = 'returned'
        item.return_reason = reason
        item.returned_at = timezone.now()
        item.save(update_fields=['status', 'return_reason', 'returned_at'])

        if item.variant:
            item.variant.stock += item.quantity
            item.variant.is_active = True
            item.variant.save(update_fields=['stock', 'is_active'])

    messages.success(request, "Order return request submitted successfully.")
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

    if item.status in ['cancelled', 'returned']:
        messages.error(request, f"This item is already {item.status}.")
        return redirect('order_detail', order_id=order.order_id)

    item.status = 'returned'
    item.return_reason = reason
    item.returned_at = timezone.now()
    item.save(update_fields=['status', 'return_reason', 'returned_at'])

    if item.variant:
        item.variant.stock += item.quantity
        item.variant.is_active = True
        item.variant.save(update_fields=['stock', 'is_active'])

    messages.success(request, f"Return request submitted for '{item.product_name}'.")
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


