from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.cache import never_cache
from functools import wraps


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please login to continue")
            return redirect('admin_login')

        if not request.user.is_staff:
            messages.error(request, "You are not authorized to access admin panel")
            return redirect('home')
        
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
