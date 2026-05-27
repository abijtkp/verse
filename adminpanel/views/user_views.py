import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q
from accounts.models import User

from django.db.models import Count, Sum, Q
from django.db.models.functions import Coalesce
from decimal import Decimal

from .core_views import admin_required

logger = logging.getLogger(__name__)

@never_cache
@admin_required
def user_management_view(request):
    search_query = request.GET.get('q', '').strip()

    all_users = User.objects.filter(is_staff=False)

    users = all_users.annotate(
        total_orders=Count(
            'orders',
            filter=Q(
                orders__payment_status__in=['paid', 'pending']
            ) & ~Q(
                orders__status__in=['cancelled', 'payment_failed']
            ),
            distinct=True
        ),
        total_spent=Coalesce(
            Sum(
                'orders__final_total',
                filter=Q(
                    orders__payment_status__in=['paid', 'pending']
                ) & ~Q(
                    orders__status__in=['cancelled', 'payment_failed']
                )
            ),
            Decimal('0.00')
        )
    ).order_by('-date_joined')

    if search_query:
        
        logger.info(
            "Admin searched users | admin_id=%s | admin_email=%s | query=%s",
            request.user.id,
            request.user.email,
            search_query,
        )
        
        users = users.filter(
            Q(full_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )

    paginator = Paginator(users, 10)   
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    total_users = all_users.count()
    active_users = all_users.filter(is_blocked=False).count()
    blocked_users = all_users.filter(is_blocked=True).count()
    new_users = all_users.order_by('-date_joined')[:10].count()
    
    logger.info(
        "Admin viewed user management | admin_id=%s | admin_email=%s | page=%s",
        request.user.id,
        request.user.email,
        page_number or 1,
    )

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'total_users': total_users,
        'active_users': active_users,
        'blocked_users':blocked_users,
        'new_users':new_users
    }
    return render(request, 'adminpanel/user_management.html', context)


@never_cache
@admin_required
@require_POST
def block_user_view(request, user_id):
    user = get_object_or_404(User, id=user_id, is_staff=False)

    if user.is_blocked:
        logger.warning(
            "Admin attempted to block already blocked user | admin_id=%s | admin_email=%s | target_user_id=%s | target_email=%s",
            request.user.id,
            request.user.email,
            user.id,
            user.email,
        )

        messages.info(request, f"{user.email} is already blocked")
        return redirect('user_management')

    user.is_blocked = True
    user.save(update_fields=['is_blocked'])

    logger.warning(
        "Admin blocked user | admin_id=%s | admin_email=%s | target_user_id=%s | target_email=%s",
        request.user.id,
        request.user.email,
        user.id,
        user.email,
    )

    messages.success(request, f"{user.email} has been blocked")
    return redirect('user_management')


@never_cache
@admin_required
@require_POST
def unblock_user_view(request, user_id):
    user = get_object_or_404(User, id=user_id, is_staff=False)

    if not user.is_blocked:
        logger.warning(
            "Admin attempted to unblock already active user | admin_id=%s | admin_email=%s | target_user_id=%s | target_email=%s",
            request.user.id,
            request.user.email,
            user.id,
            user.email,
        )

        messages.info(request, f"{user.email} is already active")
        return redirect('user_management')

    user.is_blocked = False
    user.save(update_fields=['is_blocked'])

    logger.warning(
        "Admin unblocked user | admin_id=%s | admin_email=%s | target_user_id=%s | target_email=%s",
        request.user.id,
        request.user.email,
        user.id,
        user.email,
    )

    messages.success(request, f"{user.email} has been unblocked")
    return redirect('user_management')