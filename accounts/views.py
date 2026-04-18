from django.shortcuts import render, redirect
from .models import User, OTP
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from .utils import generate_otp, send_otp_email
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError  
from django.contrib.auth.hashers import make_password
from userprofile.models import Profile
from django.views.decorators.cache import never_cache


def signup_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        # Email validation
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Invalid email format")
            return redirect('signup')

       
        
        # Full name validation
        if not full_name or len(full_name.strip()) < 4:
            messages.error(request, "Full name must be at least 4 characters")
            return redirect('signup')
        
        try:
            validate_password(password)
        except ValidationError as e:
            for error in e:
                messages.error(request, error)
            return redirect('signup')

        # Password match
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect('signup')
        
         # Check existing user (IMPROVED LOGIC)
        existing_user = User.objects.filter(email=email).first()
        
        if existing_user:
            if existing_user.is_verified:
                messages.error(request, "Email already exists")
                return redirect('signup')
            else:
                existing_user.full_name = full_name
                existing_user.set_password(password)
                existing_user.is_verified = False
                existing_user.save()
                user = existing_user
        else:
             user = User.objects.create_user(
                email=email,
                full_name=full_name,
                password=password,
                is_verified=False
            )
            
        
        # GENERATE OTP (SIGNUP PURPOSE)
        request.session['otp_user_id'] = user.id
        request.session['otp_purpose'] = 'signup'

        otp_obj = generate_otp(user, purpose='signup')
        send_otp_email(user, otp_obj)

        messages.success(request, "OTP sent to your email")
        return redirect('verify_otp')

    return render(request, 'accounts/signup.html')

def verify_otp_view(request):
    if request.method == 'POST':
        otp_input = request.POST.get('otp')
        user_id = request.session.get('otp_user_id')
        purpose = request.session.get('otp_purpose', 'signup')

        if not user_id:
            messages.error(request, "Session expired. Try again.")
            return redirect('signup')

        
        user = User.objects.filter(id=user_id).first()
        
        if not user:
            messages.error(request, "User not found")
            return redirect('signup')
        
        # GET LATEST OTP
        otp_obj = OTP.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False
        ).order_by('-created_at').first()

        # Handle no OTP safely
        if not otp_obj:
            messages.error(request, "No OTP found")
            return redirect('verify_otp')

        # CHECK OTP
        if otp_obj.code != otp_input:
            messages.error(request, "Invalid OTP")
            return redirect('verify_otp')

        # CHECK EXPIRY
        if otp_obj.expired_at < timezone.now():
            messages.error(request, "OTP expired")
            return redirect('verify_otp')

        # MARK OTP USED
        otp_obj.is_used = True
        otp_obj.save(update_fields=['is_used'])
        
        # FORGOT PASSWORD FLOW
        if purpose == 'reset_password':
            request.session['otp_verified'] = True
            request.session.pop('otp_purpose', None) 
            messages.success(request, "OTP verified successfully")
            return redirect('reset_password')
        
        # EMAIL CHANGE FLOW
        if purpose == 'email_change':
            if not request.user.is_authenticated:
                messages.error(request, "Authentication required")
                return redirect('login')
            
            new_email = request.session.get('new_email')

            if not new_email:
                messages.error(request, "Session expired")
                return redirect('profile')
            
            if User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
                messages.error(request, "Email already in use")
                return redirect('profile')

            request.user.email = new_email
            request.user.is_verified = True
            request.user.save(update_fields=['email', 'is_verified'])

            # Clear session
            request.session.pop('otp_user_id', None)
            request.session.pop('otp_purpose', None)
            request.session.pop('new_email', None)
            request.session.pop('otp_verified', None)

            messages.success(request, "Email updated successfully")
            return redirect('profile')

         #  SIGNUP FLOW
        # SAFE USER FETCH (no crash)
        user.is_verified = True
        user.save(update_fields=['is_verified'])
            
        # Clear session after success
        request.session.pop('otp_user_id', None)
        request.session.pop('otp_purpose', None)

        messages.success(request, "Account verified successfully")
        return redirect('login')
    
    return render(request, 'accounts/verify_otp.html')




def resend_otp_view(request):
    # Prevent GET request abuse
    if request.method != 'POST':
        return redirect('verify_otp')
    
    user_id = request.session.get('otp_user_id')
    purpose = request.session.get('otp_purpose', 'signup')

    if not user_id:
        messages.error(request, "Session expired. Try again.")
        return redirect('signup')
    
    # GET USER
    user = User.objects.filter(id=user_id).first()

    if not user:
        messages.error(request, "User not found")
        return redirect('signup')

    #  Get latest OTP
    last_otp = OTP.objects.filter(user=user, purpose=purpose, is_used = False).order_by('-created_at').first()

    # Accurate cooldown calculation
    if last_otp:
        time_diff = (timezone.now() - last_otp.created_at).total_seconds()

        if time_diff < 30:
            messages.error(request, f"Please wait {int(30 - time_diff)} seconds before requesting new OTP")
            return redirect('verify_otp')

    # Generate new OTP
    otp_obj = generate_otp(user, purpose=purpose)
    
    if purpose == 'email_change':
        new_email = request.session.get('new_email')
        send_otp_email(user, otp_obj, to_email=new_email)
    else:
        #  Send email
        send_otp_email(user, otp_obj)

    messages.success(request, "New OTP sent successfully")

    return redirect('verify_otp')



def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)

        if user is not None:
            
            if user.is_blocked:
                messages.error(request, "Your account has been blocked")
                return redirect('login')
            
            # BLOCK UNVERIFIED USERS
            if not user.is_verified:
                request.session['otp_user_id'] = user.id 
                request.session['otp_purpose'] = 'signup'
                messages.error(request, "Please verify your account first")
                return redirect('verify_otp')
            
            login(request, user)
            return redirect('home')
        
        messages.error(request, "Invalid credentials")

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')

@never_cache
@login_required
def home(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    return render(request, 'home.html')


def forgot_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email',{
            'profile' : Profile
        })
        
        # EMAIL VALIDATION ADDED
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Invalid email format")
            return redirect('forgot_password')

        # Check if user exists
        user = User.objects.filter(email=email).first()

        if not user:
            messages.error(request, "No account found with this email")
            return redirect('forgot_password')
        
        request.session['otp_user_id'] = user.id
        request.session['otp_purpose'] = 'reset_password'

        # Generate OTP
        otp_obj = generate_otp(user, purpose='reset_password')

        # Send email
        send_otp_email(user, otp_obj)

        # Store email in session
        messages.success(request, "OTP sent to your email")

        return redirect('verify_otp')  # reuse existing page

    return render(request, 'accounts/forgot_password.html')



def reset_password_view(request):
    user_id = request.session.get('otp_user_id')
    otp_verified = request.session.get('otp_verified') 

    if not user_id or not otp_verified:
        messages.error(request, "Unauthorized access")
        return redirect('forgot_password')
    
    
    user = User.objects.filter(id=user_id).first()
    
    if not user:
        messages.error(request, "User not found")
        return redirect('forgot_password')

    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # Validate password
        try:
            validate_password(password)
        except ValidationError as e:
            for error in e:
                messages.error(request, error)
            return redirect('reset_password')

        # Match passwords
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect('reset_password')
        
        
        user.set_password(password)
        user.save()
        
        request.session.flush()

        messages.success(request, "Password reset successful. Please login.")
        return redirect('login')

    return render(request, 'accounts/reset_password.html')

# @login_required
# def update_security_credentials(request):

#     if request.method == "POST":

#         new_email = request.POST.get("email")
        
#         try:
#             validate_email(new_email)
#         except ValidationError:
#             messages.error(request, "Invalid email format")
#             return redirect("update_security_credentials")
        
#         if new_email == request.user.email:
#             messages.error(request, "This is already your current email")
#             return redirect("update_security_credentials")

#         # prevent duplicate emails
#         if User.objects.filter(email=new_email).exists():
#             messages.error(request, "Email already in use")
#             return redirect("update_security_credentials")
        
        
#         request.session['otp_user_id'] = request.user.id
#         request.session['otp_purpose'] = 'email_change'
#         request.session["new_email"] = new_email

#         otp_obj = generate_otp(request.user, purpose="email_change")

#         send_otp_email(request.user, otp_obj, to_email=new_email)

#         return redirect("verify_otp")

#     return render(request, "accounts/update_security_credentials.html")
