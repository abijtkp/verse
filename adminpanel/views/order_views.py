from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.contrib.auth.decorators import login_required
from adminpanel.views.core_views import admin_required
from orders.models import Order, OrderItem
from django.contrib import messages
from django.views.decorators.http import require_POST
from adminpanel.views.core_views import admin_required
from django.utils import timezone
from django.db import transaction



@login_required
@admin_required
def admin_order_list_view(request):

    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    sort_by = request.GET.get('sort', '-created_at')

    orders = (
        Order.objects
        .select_related('user')
        .prefetch_related('items', 'items__variant__images')
        .order_by('-created_at')
    )

    if search_query:

        cleaned_query = search_query.replace('#', '').strip()

        orders = orders.filter(
            Q(order_id__icontains=cleaned_query) |
            Q(user__email__icontains=search_query) |
            Q(user__full_name__icontains=search_query) |
            Q(items__product_name__icontains=search_query)
        ).distinct()

    if status_filter:
        orders = orders.filter(status=status_filter)

    allowed_sorts = [
        '-created_at',
        'created_at',
        '-final_total',
        'final_total',
    ]

    if sort_by not in allowed_sorts:
        sort_by = '-created_at'

    orders = orders.order_by(sort_by)


    total_orders = Order.objects.count()

    pending_orders = Order.objects.filter(
        status__in=['pending', 'placed', 'shipped']
    ).count()

    revenue = (
        Order.objects.filter(status='delivered')
        .aggregate(total=Sum('final_total'))['total']
        or 0
    )

    issue_orders = Order.objects.filter(
        status__in=['cancelled', 'returned']
    ).count()

    paginator = Paginator(orders, 10)

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)

    context = {
        'orders': page_obj,
        'page_obj': page_obj,

        'search_query': search_query,
        'status_filter': status_filter,
        'sort_by': sort_by,

        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'revenue': revenue,
        'issue_orders': issue_orders,
    }

    return render(
        request,
        'adminpanel/order_list.html',
        context
    )
    
@login_required
@admin_required
def admin_order_detail_view(request, order_id):
    order = get_object_or_404(
        Order.objects
        .select_related('user')
        .prefetch_related('items', 'items__variant__images'),
        order_id=order_id
    )

    return render(request, 'adminpanel/order_detail.html', {
        'order': order,
    })    
    
    
@admin_required
@require_POST
@transaction.atomic
def update_order_status_view(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__variant'),
        order_id=order_id
    )

    old_status = order.status
    new_status = request.POST.get('status')
    
    

    ALLOWED_ORDER_TRANSITIONS = {
        'pending': ['shipped', 'cancelled'],
        'shipped': ['out_for_delivery'],
        'out_for_delivery': ['delivered'],
        'delivered': [],
        'cancelled': [],
        'returned': [],
    }

    allowed_statuses = [
        'pending',
        'shipped',
        'out_for_delivery',
        'delivered',
        'cancelled',
    ]

    if new_status not in allowed_statuses:
        messages.error(request, "Invalid order status.")
        return redirect('admin_order_detail', order_id=order.order_id)

    if old_status == new_status:
        messages.info(request, "Order status is already updated.")
        return redirect('admin_order_detail', order_id=order.order_id)

    allowed_next_statuses = ALLOWED_ORDER_TRANSITIONS.get(old_status, [])

    if new_status not in allowed_next_statuses:
        messages.error(
            request,
            f"Invalid status transition: "
            f"{old_status.replace('_', ' ').title()} → "
            f"{new_status.replace('_', ' ').title()}."
        )
        return redirect('admin_order_detail', order_id=order.order_id)

    if new_status in'cancelled':
        for item in order.items.exclude(status__in=['cancelled', 'returned']):
            item.status = new_status

            if new_status == 'cancelled':
                item.cancelled_at = timezone.now()


            item.save()

            if item.variant:
                item.variant.stock += item.quantity
                item.variant.is_active = True
                item.variant.save(update_fields=['stock', 'is_active'])

        order.status = new_status

        if new_status == 'cancelled':
            order.cancelled_at = timezone.now()

        order.save()

        messages.success(
            request,
            f"Order marked as {new_status.replace('_', ' ').title()} and stock restored."
        )
        return redirect('admin_order_detail', order_id=order.order_id)

    order.status = new_status

    if new_status == 'delivered':
        order.delivered_at = timezone.now()

        if order.payment_method == 'cod':
            order.payment_status = 'paid'

    order.save()

    order.items.exclude(
        status__in=['cancelled', 'returned']
    ).update(status=new_status)

    messages.success(
        request,
        f"Order status updated to {new_status.replace('_', ' ').title()}."
    )

    return redirect('admin_order_detail', order_id=order.order_id)


@login_required
@admin_required
def admin_return_list_view(request):
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    return_items = (
        OrderItem.objects
        .filter(status__in=['return_requested', 'return_rejected', 'returned'])
        .select_related('order', 'order__user', 'variant')
        .order_by('-return_requested', '-created_at')
    )

    if search_query:
        cleaned_query = search_query.replace('#', '').strip()

        return_items = return_items.filter(
            Q(order__order_id__icontains=cleaned_query) |
            Q(order__user__email__icontains=search_query) |
            Q(order__user__full_name__icontains=search_query) |
            Q(product_name__icontains=search_query) |
            Q(sku__icontains=search_query)
        ).distinct()

    if status_filter:
        return_items = return_items.filter(status=status_filter)

    paginator = Paginator(return_items, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'return_items': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'total_returns': return_items.count(),
        'pending_returns': return_items.filter(status='return_requested').count(),
        'approved_returns': return_items.filter(status='returned').count(),
        'rejected_returns': return_items.filter(status='return_rejected').count(),
    }

    return render(request, 'adminpanel/return_list.html', context)


@login_required
@admin_required
@require_POST
@transaction.atomic
def approve_return_request_view(request, item_id):
    item = get_object_or_404(
        OrderItem.objects.select_related('order', 'variant'),
        id=item_id,
        status='return_requested'
    )

    item.status = 'returned'
    item.return_reviewed_at = timezone.now()
    item.returned_at = timezone.now()
    item.save(update_fields=['status', 'return_reviewed_at', 'returned_at'])

    if item.variant:
        item.variant.stock += item.quantity
        item.variant.is_active = True
        item.variant.save(update_fields=['stock', 'is_active'])

    order = item.order

    if not order.items.exclude(status__in=['cancelled', 'returned']).exists():
        order.status = 'returned'
        order.save(update_fields=['status', 'updated_at'])

    messages.success(request, f"Return approved for '{item.product_name}'. Stock restored.")
    return redirect('admin_return_list')


@login_required
@admin_required
@require_POST
@transaction.atomic
def reject_return_request_view(request, item_id):
    item = get_object_or_404(
        OrderItem.objects.select_related('order'),
        id=item_id,
        status='return_requested'
    )

    rejection_reason = request.POST.get('rejection_reason', '').strip()

    if not rejection_reason:
        messages.error(request, "Rejection reason is required.")
        return redirect('admin_return_list')

    item.status = 'return_rejected'
    item.return_rejection_reason = rejection_reason
    item.return_reviewed_at = timezone.now()
    item.save(update_fields=['status', 'return_rejection_reason', 'return_reviewed_at'])

    messages.success(request, f"Return rejected for '{item.product_name}'.")
    return redirect('admin_return_list')