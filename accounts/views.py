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
from products.models import Category
from django.views.decorators.cache import never_cache
import logging

logger = logging.getLogger(__name__)

@never_cache
def signup_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        terms = request.POST.get('terms')
        referral_code = request.POST.get('referral_code', '').strip().upper()

        form_data = {
            'email': email,
            'full_name': full_name,
            'terms':terms,
            'referral_code': referral_code,
            }
        
        field_errors = {}

        if not full_name or len(full_name.strip()) < 4:
            field_errors['full_name'] = "Full name must be at least 4 characters."

        if not email:
            field_errors['email'] = "Email is required."
        else:
            try:
                validate_email(email)
            except ValidationError:
                field_errors['email'] = "Enter a valid email address."


        if 'email' not in field_errors:
            existing_user = User.objects.filter(email=email).first()
            if existing_user and existing_user.is_verified:
                
                logger.warning(
                    "Signup blocked - verified email already exists | email=%s | ip=%s",
                    email,
                    request.META.get("REMOTE_ADDR"),
                )
                
                field_errors['email'] = "An account with this email already exists."
                
        referrer = None

        if referral_code:
            referrer = User.objects.filter(
                referral_code=referral_code,
                is_verified=True,
                is_blocked=False
            ).first()

            if not referrer:
                
                logger.warning(
                    "Signup attempted with invalid referral code | email=%s | referral_code=%s | ip=%s",
                    email,
                    referral_code,
                    request.META.get("REMOTE_ADDR"),
                )
                
                field_errors['referral_code'] = "Invalid referral code."        

        password_errors = []
        
        temp_user = User(email=email, full_name=full_name)
        
        try:
            validate_password(password, user=temp_user)
        except ValidationError as e:
            password_errors = e.messages

        if password_errors:
            field_errors['password'] = password_errors[0]  
        elif password != confirm_password:
            field_errors['confirm_password'] = "Passwords do not match."
            
        if not terms:
            field_errors['terms'] = "You must accept the terms and condition."    

        if field_errors:
            return render(request, 'accounts/signup.html', {
                'form_data': form_data,
                'field_errors': field_errors,
            })

        existing_user = User.objects.filter(email=email).first()
        
        if existing_user and not existing_user.is_verified:
            existing_user.full_name = full_name
            existing_user.set_password(password)

            if referrer and existing_user.referred_by is None:
                existing_user.referred_by = referrer

            existing_user.save()
            user = existing_user
            
            
            logger.info(
                "Existing unverified signup user updated | user_id=%s | email=%s",
                user.id,
                user.email
            )    
            
        else:
            user = User.objects.create_user(
                email=email,
                full_name=full_name,
                password=password,
                is_verified=False,
                referred_by=referrer,
            )
            
            logger.info(
                "New signup user created | user_id=%s | email=%s | referred_by=%s",
                user.id,
                user.email,
                referrer.id if referrer else None,
            )

        request.session['otp_user_id'] = user.id
        request.session['otp_purpose'] = 'signup'
        
        logger.info(
            "Signup OTP flow started | user_id=%s | email=%s | referral_code=%s",
            user.id,
            user.email,
            referral_code or None,
        )

        otp_obj = generate_otp(user, purpose='signup')
        send_otp_email(user, otp_obj)

        messages.success(request, "OTP sent to your email")
        return redirect('verify_otp')

    referral_code = request.GET.get('ref', '').strip().upper()

    return render(request, 'accounts/signup.html', {
        'form_data': {
            'referral_code': referral_code
        }
    })

@never_cache
def verify_otp_view(request):
    if request.method == 'POST':
        otp_input = request.POST.get('otp')
        user_id = request.session.get('otp_user_id')
        purpose = request.session.get('otp_purpose', 'signup')

        if not user_id:
            
            logger.warning(
                "OTP verification failed - session expired | purpose=%s | ip=%s",
                purpose,
                request.META.get("REMOTE_ADDR"),
            )
            
            messages.error(request, "Session expired. Try again.")
            return redirect('signup')

        
        user = User.objects.filter(id=user_id).first()
        
        if not user:
            
            logger.warning(
                "OTP verification failed - user not found | user_id=%s, | purpose=%s | ip=%s",
                user_id,
                purpose,
                request.META.get("REMOTE_ADDR"),
            )
            
            messages.error(request, "User not found")
            return redirect('signup')
        
        otp_obj = OTP.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False
        ).order_by('-created_at').first()


        if not otp_obj:
            
            logger.warning(
                "OTP verification failed - no active OTP | user_id=%s | email=%s | purpose=%s | ip=%s",
                user.id,
                user.email,
                purpose,
                request.META.get("REMOTE_ADDR"),
            )
            
            messages.error(request, "No OTP found")
            return redirect('verify_otp')


        if otp_obj.code != otp_input:
            
            logger.warning(
                "Invalid OTP attempt | user_id=%s | email=%s | purpose=%s | ip=%s",
                user.id,
                user.email,
                purpose,
                request.META.get("REMOTE_ADDR"),
            )
            
            messages.error(request, "Invalid OTP")
            return redirect('verify_otp')

  
        if otp_obj.expired_at < timezone.now():
            
            logger.warning(
                "Expired OTP attempt | user_id=%s | email=%s | purpose=%s | ip=%s",
                user.id,
                user.email,
                purpose,
                request.META.get("REMOTE_ADDR"),
            )
            
            messages.error(request, "OTP expired")
            return redirect('verify_otp')

        otp_obj.is_used = True
        otp_obj.save(update_fields=['is_used'])
        
        logger.info(
            "OTP verified successfully | user_id=%s | email=%s | purpose=%s",
            user.id,
            user.email,
            purpose,
        )
        
       
        if purpose == 'reset_password':
            request.session['otp_verified'] = True
            request.session.pop('otp_purpose', None) 
            messages.success(request, "OTP verified successfully")
            return redirect('reset_password')
        
      
        if purpose == 'email_change':
            if not request.user.is_authenticated:
                
                logger.warning(
                    "Email change OTP verified but user not authenticated | user_id=%s | email=%s | ip=%s",
                    user.id,
                    user.email,
                    request.META.get("REMOTE_ADDR"),
                )

                
                messages.error(request, "Authentication required")
                return redirect('login')
            
            old_email = request.user.email
            
            new_email = request.session.get('new_email')

            if not new_email:
                
                logger.warning(
                    "Email change failed - new email missing in session | user_id=%s | email=%s",
                    request.user.id,
                    request.user.email,
                )
                
                messages.error(request, "Session expired")
                return redirect('profile')
            
            if User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
                
                logger.warning(
                    "Email change failed - email already exists | user_id=%s | current_email=%s | attempted_email=%s",
                    request.user.id,
                    request.user.email,
                    new_email,
                )

                
                messages.error(request, "Email already in use")
                return redirect('profile')

            request.user.email = new_email
            request.user.is_verified = True
            request.user.save(update_fields=['email', 'is_verified'])
            
            
            logger.info(
                "User email changed successfully | user_id=%s | old_email=%s | new_email=%s",
                request.user.id,
                old_email,
                new_email,
            )

           
            request.session.pop('otp_user_id', None)
            request.session.pop('otp_purpose', None)
            request.session.pop('new_email', None)
            request.session.pop('otp_verified', None)

            messages.success(request, "Email updated successfully")
            return redirect('profile')

    
        user.is_verified = True
        user.save(update_fields=['is_verified'])
        
        logger.info(
            "Account verified successfully | user_id=%s | email=%s",
            user.id,
            user.email,
        )
            
            
    
        request.session.pop('otp_user_id', None)
        request.session.pop('otp_purpose', None)

        messages.success(request, "Account verified successfully")
        return redirect('login')
    
    return render(request, 'accounts/verify_otp.html')




def resend_otp_view(request):
    if request.method != 'POST':
        return redirect('verify_otp')
    
    user_id = request.session.get('otp_user_id')
    purpose = request.session.get('otp_purpose', 'signup')

    if not user_id:
        
        logger.warning(
            "OTP resend failed - session expired | purpose=%s | ip=%s",
            purpose,
            request.META.get("REMOTE_ADDR"),
        )
        
        messages.error(request, "Session expired. Try again.")
        return redirect('signup')
    
    user = User.objects.filter(id=user_id).first()

    if not user:
        
        logger.warning(
            "OTP resend failed - user not found | user_id=%s | purpose=%s | ip=%s",
            user_id,
            purpose,
            request.META.get("REMOTE_ADDR"),
        )
        
        messages.error(request, "User not found")
        return redirect('signup')

    
    last_otp = OTP.objects.filter(
        user=user, 
        purpose=purpose, 
        is_used = False
        ).order_by('-created_at').first()

 
    if last_otp:
        time_diff = (timezone.now() - last_otp.created_at).total_seconds()

        if time_diff < 30:
            wait_seconds = int(30 - time_diff)
            
            logger.warning(
                "OTP resend throttled | user_id=%s | email=%s | purpose=%s | wait_seconds=%s | ip=%s",
                user.id,
                user.email,
                purpose,
                wait_seconds,
                request.META.get("REMOTE_ADDR"),
            )
            
            messages.error(request, f"Please wait {wait_seconds} seconds before requesting new OTP")
            return redirect('verify_otp')

  
    otp_obj = generate_otp(user, purpose=purpose)
    
    if purpose == 'email_change':
        new_email = request.session.get('new_email')
        send_otp_email(user, otp_obj, to_email=new_email)
    else:
       
        send_otp_email(user, otp_obj)
        
    logger.info(
        "OTP resent successfully | user_id=%s | email=%s | purpose=%s",
        user.id,
        user.email,
        purpose,
    )
        

    messages.success(request, "New OTP sent successfully")

    return redirect('verify_otp')


@never_cache
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        
        form_data = {
            'email' : email,
        }
        
        field_errors = {}
        
        if not email:
            field_errors['email'] = "Email is required."
        else:
            try:
                validate_email(email)
            except ValidationError:
                field_errors['email'] = "Enter a valid email address."
                
        if not password:
            field_errors['password'] = "Password is required."
            
        if field_errors:
            return render(request, 'accounts/login.html',{
                'form_data':form_data,
                'field_errors':field_errors,
            })                 

        user = authenticate(request, email=email, password=password)

        if user is None:
            
            logger.warning(
                "Failed login attempt | email=%s | ip=%s",
                email,
                request.META.get("REMOTE_ADDR"),
            )
            
            field_errors['general'] = "Invalid email or password."
            
            return render(request, 'accounts/login.html', {
                'form_data':form_data,
                'field_errors': field_errors,
            })
       

        if user.is_blocked:
            
            logger.warning(
                "Blocked user login attempt | user_id=%s | email=%s | ip=%s",
                user.id,
                user.email,
                request.META.get("REMOTE_ADDR"),
            ) 
            
            
            
            field_errors['general'] = "Your account has been blocked."
            
            return render(request, 'accounts/login.html', {
                'form_data': form_data,
                'field_errors': field_errors,
                })

        if not user.is_verified:
            
            logger.info(
                "Unverified user attempted login | user_id=%s | email=%s",
                user.id,
                user.email,
            )
            
            request.session['otp_user_id'] = user.id
            request.session['otp_purpose'] = 'signup'
            messages.error(request, "Please verify your account first")
            return redirect('verify_otp')

        login(request, user)
        
        logger.info(
            "User logged in successfully | user_id=%s | email=%s",
            user.id,
            user.email,
        )
        
        messages.success(request, "Logged in successfully,")
        return redirect('home')


    return render(request, 'accounts/login.html')

@never_cache
def logout_view(request):
    if request.user.is_authenticated:
        
        logger.info(
            "User logged out | user_id=%s | email=%s",
            request.user.id,
            request.user.email,
        )
        
    logout(request)
    
    messages.success(request, "Logged out successfully.")
    return redirect('login')

@never_cache
def home(request):
    profile = None

    if request.user.is_authenticated:
        profile, created = Profile.objects.get_or_create(user=request.user)

    categories_with_images = Category.objects.filter(
        is_active=True,
        is_deleted=False,
        category_image__isnull=False
    ).exclude(
        category_image=''
    ).order_by('-updated_at', '-created_at')

    show_category_cards = categories_with_images.count() >= 4

    home_categories = categories_with_images[:4] if show_category_cards else []
    

    return render(request, 'home.html', {
        'profile': profile,
        'home_categories': home_categories,
        'show_category_cards': show_category_cards,
    })
    
def profile_access_view(request):
    if request.user.is_authenticated:
        return redirect('profile')

    return redirect('login')
    

@never_cache
def forgot_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()

        field_errors = {}

        try:
            validate_email(email)
        except ValidationError:
            field_errors['email'] = "Enter a valid email address."

        if 'email' not in field_errors:
            user = User.objects.filter(email=email).first()
            if not user:
                
                logger.warning(
                    "Password reset requested for unknown email | email=%s | ip=%s",
                    email,
                    request.META.get("REMOTE_ADDR"),
                )
                
                field_errors['email'] = "No account found with this email."

        if field_errors:
            return render(request, 'accounts/forgot_password.html', {
                'form_data': {'email': email},
                'field_errors': field_errors,
            })

        request.session['otp_user_id'] = user.id
        request.session['otp_purpose'] = 'reset_password'
        
        logger.info(
            "Password reset OTP requested | user_id=%s | email=%s | ip=%s",
            user.id,
            user.email,
            request.META.get("REMOTE_ADDR"),
        )

        otp_obj = generate_otp(user, purpose='reset_password')
        send_otp_email(user, otp_obj)

        messages.success(request, "OTP sent to your email")
        return redirect('verify_otp')

    return render(request, 'accounts/forgot_password.html')


@never_cache
def reset_password_view(request):
    user_id = request.session.get('otp_user_id')
    otp_verified = request.session.get('otp_verified') 

    if not user_id or not otp_verified:
    
        logger.warning(
            "Unauthorized reset password access | session_user_id=%s | otp_verified=%s | ip=%s",
            user_id,
            otp_verified,
            request.META.get("REMOTE_ADDR"),
        )
        
        messages.error(request, "Unauthorized access")
        return redirect('forgot_password')
    
    user = User.objects.filter(id=user_id).first()
    
    if not user:
        
        logger.warning(
            "Reset password failed - user not found | user_id=%s | ip=%s",
            user_id,
            request.META.get("REMOTE_ADDR"),
        )
        
        messages.error(request, "User not found")
        return redirect('forgot_password')

    if request.method == 'POST':
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        field_errors = {}
        
        if not password.strip():
            field_errors['password'] = 'Password is required.'
        
        if not confirm_password.strip():
            field_errors['confirm_password'] = 'Please confirm your password.' 
            
        if 'password' not in field_errors:
            try:
                validate_password(password)
            except ValidationError as e:
                field_errors['password'] = list(e)[0]

        if (
            'password' not in field_errors and
            'confirm_password' not in field_errors and
            password != confirm_password
        ):
            field_errors['confirm_password'] = "Passwords do not match."

        if field_errors:
            return render(request, 'accounts/reset_password.html', {
                'field_errors': field_errors,
            })

        user.set_password(password)
        user.save()
        
        logger.info(
            "Password reset successful | user_id=%s | email=%s",
            user.id,
            user.email,
        )

        request.session.flush()

        messages.success(request, "Password reset successful. Please login.")
        return redirect('login')

    return render(request, 'accounts/reset_password.html')

