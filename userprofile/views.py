from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Address, Profile
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from accounts.models import User, OTP
from accounts.utils import generate_otp, send_otp_email
from django.views.decorators.cache import never_cache
from django.db import transaction

@never_cache
@login_required
def profile_view(request):
    user = request.user
    profile, created = Profile.objects.get_or_create(user=request.user)
    addresses = user.addresses.all().order_by('-is_default', '-created_at')
    default_address = addresses.filter(is_default=True).first()
    return render(request, 'userprofile/profile.html', {
        'user': user,
        'profile':profile,
        'addresses': addresses,
        'default_address': default_address,
    })

@login_required
def edit_profile_view(request):
    user = request.user
    profile, created = Profile.objects.get_or_create(user=user)

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        bio = request.POST.get('bio', '').strip()
        dob = request.POST.get('date_of_birth', '').strip()
        
        
        if not full_name or len(full_name) < 4:
            messages.error(request, "Full name must be at least 4 characters")
            return redirect('edit_profile')
        
        user.full_name = full_name
        user.phone_number = phone_number
        user.bio = bio
        
        if dob:
            user.date_of_birth = dob  
        else:
            user.date_of_birth = None
        
        # PROFILE PHOTO (if stored in Profile model)
        if 'profile_photo' in request.FILES:
            profile.image = request.FILES['profile_photo']
            profile.save()
        
        
        user.save()
        
            
    #     if new_email and new_email != user.email:
    #         try:
    #             validate_email(new_email)
    #         except ValidationError:
    #             messages.error(request, "Invalid email format")
    #             return redirect('edit_profile')  
            
    #         if User.objects.filter(email=new_email).exists():
    #             messages.error(request, "Email already in use")
    #             return redirect('edit_profile')  

    #     user.save()
        
    #     request.session['new_email'] = new_email
    #     request.session['otp_user_id'] = user.id 
    #     request.session['otp_purpose'] = 'email_change'
        
    #     otp_obj = generate_otp(user, purpose='email_change')
    #     send_otp_email(user, otp_obj, to_email=new_email)
    #     messages.success(request, "OTP sent to your new email address")
    #     return redirect('verify_otp')
    
    # user.save()
        
        messages.success(request, "Profile updated successfully")
        return redirect('profile')

    return render(request, 'userprofile/edit_profile.html', {
        'user': user,
        'profile': profile
    }) 
 
@login_required
def add_address(request):
    if request.method == 'POST':
        
        existing_addresses = Address.objects.filter(user=request.user)
        is_default = request.POST.get('is_default') == 'on'
        
        
        # FIRST ADDRESS AUTO DEFAULT
        if not existing_addresses.exists():
            is_default = True
        
        
        if is_default:
            Address.objects.filter(user=request.user, is_default=True).update(is_default=False)
            
        Address.objects.create(
            user=request.user,
            full_name=request.POST.get('full_name'),
            phone_number=request.POST.get('phone_number'),
            address_line1=request.POST.get('address_line1'),
            address_line2=request.POST.get('address_line2'),
            city=request.POST.get('city'),
            state=request.POST.get('state'),
            pincode=request.POST.get('pincode'),
            country=request.POST.get('country'),
            type=request.POST.get('address_type', 'home'),
            is_default=is_default
        )

        return redirect('address_list')

    return render(request, 'userprofile/add_address.html') 
 
    
    
@login_required
def address_list(request):
    addresses = request.user.addresses.all().order_by('-is_default', '-created_at')
    return render(request, 'userprofile/address_list.html', {
        'addresses': addresses
    })    
 
@login_required
def edit_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)

    if request.method == 'POST':
        is_default = request.POST.get('is_default') == 'on'

        # Handle default switch
        if is_default:
            Address.objects.filter(user=request.user, is_default=True).update(is_default=False)

        address.full_name = request.POST.get('full_name')
        address.phone_number = request.POST.get('phone_number')
        address.address_line1 = request.POST.get('address_line1')
        address.address_line2 = request.POST.get('address_line2')
        address.city = request.POST.get('city')
        address.state = request.POST.get('state')
        address.pincode = request.POST.get('pincode')
        address.country = request.POST.get('country')
        address.type = request.POST.get('address_type', 'home')
        address.is_default = is_default

        address.save()

        return redirect('address_list')

    return render(request, 'userprofile/edit_address.html', {
        'address': address
    })
    
    
    
@login_required
def delete_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    
    if request.method == 'POST':
        with transaction.atomic():
            if address.is_default:
                next_address = Address.objects.filter(
                    user=request.user
                ).exclude(id=address.id).order_by('-created_at').first()
            
                if next_address:
                    Address.objects.filter(user=request.user, is_default=True).update(is_default=False)
                    next_address.is_default = True
                    next_address.save()
                
            address.delete()

    return redirect('address_list')    

@login_required
def set_default_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    
    if request.method == 'POST':
        Address.objects.filter(user=request.user, is_default=True).update(is_default=False)
        
        address.is_default = True
        address.save()

    return redirect('address_list')

@login_required
def change_email_view(request):
    if request.method == 'POST':
        new_email = request.POST.get('new_email')
        
        if not new_email:
            messages.error(request, "Email is required")
            return redirect('change_email')

        # Validate email
        try:
            validate_email(new_email)
        except ValidationError:
            messages.error(request, "Invalid email format")
            return redirect('change_email')

        # Check if already exists
        if User.objects.filter(email=new_email).exists():
            messages.error(request, "Email already in use")
            return redirect('change_email')

        # Store in session
        request.session['new_email'] = new_email
        request.session['otp_user_id'] = request.user.id
        request.session['otp_purpose'] = 'email_change'

        # Generate OTP
        otp_obj = generate_otp(request.user, purpose='email_change')

        # send to NEW email (not old)
        send_otp_email(request.user, otp_obj, to_email=new_email)

        messages.success(request, "OTP sent to new email")
        return redirect('verify_otp')

    return render(request, 'userprofile/change_email.html')

