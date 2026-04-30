from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q
from accounts.models import User
from .core_views import admin_required


@never_cache
@admin_required
def user_management_view(request):
    search_query = request.GET.get('q', '').strip()

    all_users = User.objects.filter(is_staff=False)
    
    users = all_users.order_by('-date_joined')

    if search_query:
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
    user.is_blocked = True
    user.save()
    messages.success(request, f"{user.email} has been blocked")
    return redirect('user_management')


@never_cache
@admin_required
@require_POST
def unblock_user_view(request, user_id):
    user = get_object_or_404(User, id=user_id, is_staff=False)
    user.is_blocked = False
    user.save()
    messages.success(request, f"{user.email} has been unblocked")
    return redirect('user_management')