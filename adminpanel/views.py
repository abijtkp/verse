from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from functools import wraps
from accounts.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please login to continue")
            return redirect('admin_login')

        if not request.user.is_staff:
            messages.error(request, "You are not authorized to access admin panel")
            return redirect('admin_login')
        
        if request.user.is_blocked:
            logout(request)
            messages.error(request, "Your account has been blocked")
            return redirect('admin_login')
            
        return view_func(request, *args, **kwargs)
    return wrapper


@never_cache
def admin_login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard')
        else:
            logout(request)

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        user = authenticate(request, email=email, password=password)

        if user is None:
            messages.error(request, "Invalid email or password")
            return redirect('admin_login')

        if not user.is_staff:
            messages.error(request, "You are not authorized to access admin panel")
            return redirect('admin_login')

        if user.is_blocked:
            messages.error(request, "Your account has been blocked")
            return redirect('admin_login')

        login(request, user)
        messages.success(request, "Welcome to admin panel")
        return redirect('admin_dashboard')

    return render(request, 'adminpanel/login.html')


@never_cache
@admin_required
def admin_dashboard_view(request):
    return render(request, 'adminpanel/dashboard.html')


@never_cache
@admin_required
def admin_logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully")
    return redirect('admin_login')


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