from django.shortcuts import render, redirect
from .models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required

# Create your views here.

def signup_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        full_name = request.POST.get('full_name')
        phone_number = request.POST.get('phone_number')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        #  Email format validation
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Invalid email format")
            return redirect('signup')

        #  Email uniqueness
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect('signup')

        #  Full name validation
        if not full_name or len(full_name) < 8:
            messages.error(request, "Full name must be at least 8 characters")
            return redirect('signup')

        #  Password match
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect('signup')

        #  Create user
        user = User.objects.create(
            email=email,
            full_name=full_name,
            phone_number=phone_number
        )
        user.set_password(password)
        user.save()

        login(request, user)
        return redirect('home')

    return render(request, 'accounts/signup.html')



def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, "Invalid credentials")

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')

# @login_required
def home(request):
    return render(request, 'home.html')