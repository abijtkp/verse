from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.http import JsonResponse

def user_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "success": False,
                    "login_required": True,
                    "message": "Please login to continue."
                }, status=401)

            messages.error(request, "Please login to continue")
            return redirect('login')

        if request.user.is_staff:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "success": False,
                    "message": "Admin users cannot access user panel."
                }, status=403)

            messages.error(request, "Admin users cannot access user panel")
            return redirect('admin_dashboard')

        if request.user.is_blocked:
            logout(request)
            messages.error(request, "Your account has been blocked")
            return redirect('login')

        return view_func(request, *args, **kwargs)
    return wrapper




def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please login to continue.")
            return redirect('admin_login')  

        if not request.user.is_staff:
            messages.error(request, "You are not authorized to access admin panel.")
            return redirect('home')

        return view_func(request, *args, **kwargs)
    return wrapper


