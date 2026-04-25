from django.shortcuts import render,redirect, get_object_or_404
from .models import Address, Profile
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from accounts.models import User, OTP
from accounts.utils import generate_otp, send_otp_email
from django.views.decorators.cache import never_cache
from django.db import transaction
from accounts.decorators import user_required
from django.views.decorators.http import require_POST
from django.core.files.images import get_image_dimensions

@never_cache
@user_required
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

@never_cache
@user_required
def edit_profile_view(request):
    user = request.user
    profile, created = Profile.objects.get_or_create(user=user)

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        bio = request.POST.get('bio', '').strip()
        dob = request.POST.get('date_of_birth', '').strip()

        form_data = {
            'full_name': full_name,
            'phone_number': phone_number,
            'bio': bio,
            'date_of_birth': dob,
        }

        field_errors = {}

        if not full_name or len(full_name) < 4:
            field_errors['full_name'] = "Full name must be at least 4 characters."

        if phone_number:
            if not phone_number.isdigit():
                field_errors['phone_number'] = "Phone number must contain only digits."
            elif len(phone_number) != 10:
                field_errors['phone_number'] = "Phone number must be exactly 10 digits."

        if field_errors:
            return render(request, 'userprofile/edit_profile.html', {
                'user': user,
                'profile': profile,
                'form_data': form_data,
                'field_errors': field_errors,
            })

        user.full_name = full_name
        user.phone_number = phone_number
        user.bio = bio

        if dob:
            user.date_of_birth = dob
        else:
            user.date_of_birth = None

        

        user.save()

        messages.success(request, "Profile updated successfully")
        return redirect('profile')

    return render(request, 'userprofile/edit_profile.html', {
        'user': user,
        'profile': profile
    })
    
    
@never_cache
@user_required
@require_POST
def update_profile_photo(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    uploaded_image = request.FILES.get('profile_photo')

    if not uploaded_image:
        messages.error(request, "Please select an image.")
        return redirect('edit_profile')

    allowed_content_types = ['image/jpeg', 'image/png', 'image/webp']

    if uploaded_image.content_type not in allowed_content_types:
        messages.error(request, "Only JPG, PNG, or WEBP images are allowed.")
        return redirect('edit_profile')

    max_size = 2 * 1024 * 1024  

    if uploaded_image.size > max_size:
        messages.error(request, "Image size must be less than 2MB.")
        return redirect('edit_profile')

    try:
        get_image_dimensions(uploaded_image)
    except Exception:
        messages.error(request, "Invalid image file.")
        return redirect('edit_profile')
    
    if profile.image:
        profile.image.delete(save=False)

    profile.image = uploaded_image
    profile.save(update_fields=['image'])

    messages.success(request, "Profile photo updated successfully.")
    return redirect('edit_profile')


@never_cache
@user_required
@require_POST
def remove_profile_photo(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if profile.image:
        profile.image.delete(save=False)
        profile.image = None
        profile.save(update_fields=['image'])

    messages.success(request, "Profile photo removed successfully.")
    return redirect('edit_profile')
    
    
    
    
    
    
    
    
    
     
 
@user_required
def add_address(request):
    if request.method == 'POST':
        full_name    = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        address_line1 = request.POST.get('address_line1', '').strip()
        address_line2 = request.POST.get('address_line2', '').strip()  
        city         = request.POST.get('city', '').strip()
        state        = request.POST.get('state', '').strip()
        pincode      = request.POST.get('pincode', '').strip()
        country      = "India"
        address_type = request.POST.get('address_type', 'home').strip()
        is_default   = request.POST.get('is_default') == 'on'
        
        
        form_data = {
            'full_name': full_name,
            'phone_number': phone_number,
            'address_line1': address_line1,
            'address_line2': address_line2,
            'city': city,
            'state': state,
            'pincode': pincode,
            'country': country,
            'address_type': address_type,
            'is_default': is_default,
        }
        
        field_errors = {}
        
        if not full_name:
            field_errors['full_name'] = "Full name is required."
        elif len(full_name) < 4:
            field_errors['full_name'] = "Full name must be at least 4 characters."

        if not phone_number:
            field_errors['phone_number'] = "Phone number is required."
        elif not phone_number.isdigit():
            field_errors['phone_number'] = "Phone number must contain only digits."
        elif len(phone_number) != 10:
            field_errors['phone_number'] = "Phone number must be exactly 10 digits."

        if not address_line1:
            field_errors['address_line1'] = "Address line 1 is required."
        elif len(address_line1) < 5:
            field_errors['address_line1'] = "Address must be at least 5 characters."

        if not city:
            field_errors['city'] = "City is required."
        elif len(city) < 3:
            field_errors['city'] = "City must be at least 3 characters."
        elif not city.replace(" ","").isalpha():
            field_errors['city'] = "City must contain only letters."

        if not state:
            field_errors['state'] = "State is required."
        elif len(state) < 3:
            field_errors['state'] = "State must be at least 3 characters."
        elif not state.replace(" ","").isalpha():
            field_errors['state'] = "State must contain only letters."

        if not pincode:
            field_errors['pincode'] = "Pincode is required."
        elif not pincode.isdigit():
            field_errors['pincode'] = "Pincode must contain only digits."
        elif len(pincode) != 6:
            field_errors['pincode'] = "Pincode must be exactly 6 digits."
        
        
        if field_errors:
            return render(request, 'userprofile/add_address.html', {
                'form_data': form_data,
                'field_errors': field_errors,
            })

    
        existing_addresses = Address.objects.filter(user=request.user)


        if not existing_addresses.exists():
            is_default = True

        if is_default:
            Address.objects.filter(user=request.user, is_default=True).update(is_default=False)

        Address.objects.create(
            user=request.user,
            full_name=full_name,
            phone_number=phone_number,
            address_line1=address_line1,
            address_line2=address_line2 or None,
            city=city,
            state=state,
            pincode=pincode,
            country=country,
            type=address_type,
            is_default=is_default
        )

        messages.success(request, "Address added successfully.")
        return redirect('address_list')

    return render(request, 'userprofile/add_address.html')
 
    
    

@user_required
def address_list(request):
    addresses = request.user.addresses.all().order_by('-is_default', '-created_at')
    return render(request, 'userprofile/address_list.html', {
        'addresses': addresses
    })    
 

@user_required
def edit_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)

    if request.method == 'POST':
        full_name     = request.POST.get('full_name', '').strip()
        phone_number  = request.POST.get('phone_number', '').strip()
        address_line1 = request.POST.get('address_line1', '').strip()
        address_line2 = request.POST.get('address_line2', '').strip()  
        city          = request.POST.get('city', '').strip()
        state         = request.POST.get('state', '').strip()
        pincode       = request.POST.get('pincode', '').strip()
        country       = "India"
        address_type  = request.POST.get('address_type', 'home').strip()
        is_default    = request.POST.get('is_default') == 'on'
        
        form_data = {
            'full_name': full_name,
            'phone_number': phone_number,
            'address_line1': address_line1,
            'address_line2': address_line2,
            'city': city,
            'state': state,
            'pincode': pincode,
            'country': country,
            'address_type': address_type,
            'is_default': is_default,
        }

        field_errors = {}
        
        if not full_name:
            field_errors['full_name'] = 'Full name is required.'
        elif len(full_name) < 4:
            field_errors['full_name'] = "Full name must be at least 4 characters."
            
            
        if not phone_number:
            field_errors['phone_number'] = "Phone number is required."
        elif not phone_number.isdigit():
            field_errors['phone_number'] = "Phone number must contain only digits." 
        elif len(phone_number) != 10:
            field_errors['phone_number'] = "Phone number must be exactly 10 digits."
            
            
        if not address_line1:
            field_errors['address_line1'] = "Address line 1 is required."
        elif len(address_line1) < 5:
            field_errors['address_line1'] = "Address must be at least 5 characters." 
        
        
        if not city:
            field_errors['city'] = "City is required."
        elif len(city) < 2:
            field_errors['city'] = "City must be at least 2 characters."
        elif not city.replace(" ", "").isalpha():
            field_errors['city'] = "City must contain only letters."    
            
            
        if not state:
            field_errors['state'] = "State is required."
        elif len(state) < 3:
            field_errors['state'] = "State must be at least 3 characters."
        elif not state.replace(" ","").isalpha():
            field_errors['state'] = "State must contain only letters."
            

        if not pincode:
            field_errors['pincode'] = "Pincode is required."
        elif not pincode.isdigit():
            field_errors['pincode'] = "Pincode must contain only digits."
        elif len(pincode) != 6:
            field_errors['pincode'] = "Pincode must be exactly 6 digits."
            
        
            
        if field_errors:
            return render(request, 'userprofile/edit_address.html',{
                'address':address,
                'form_data':form_data,
                'field_errors':field_errors,
            })  
            
        if address.is_default:
            final_is_default = True
        else:
            final_is_default = is_default           
            
                      

        if final_is_default:
            Address.objects.filter(user=request.user, is_default=True).exclude(id=address.id).update(is_default=False)

        address.full_name     = full_name
        address.phone_number  = phone_number
        address.address_line1 = address_line1
        address.address_line2 = address_line2 or None
        address.city          = city
        address.state         = state
        address.pincode       = pincode
        address.country       = country
        address.type          = address_type
        address.is_default    = final_is_default

        address.save()
        messages.success(request, "Address updated successfully.")
        return redirect('address_list')

    return render(request, 'userprofile/edit_address.html', {
        'address': address
    })
    
    
    

@user_required 
def delete_address(request, pk): 
    address = get_object_or_404(Address, pk=pk, user=request.user) 
    
    if request.method == 'POST':
        with transaction.atomic(): 
            if address.is_default: 
                next_address = Address.objects.filter( 
                    user=request.user
                    ).exclude(id=address.id).order_by('-created_at').first() 
                
                if next_address: 
                    Address.objects.filter(user=request.user, 
                        is_default=True).update(is_default=False) 
                    
                    next_address.is_default = True 
                    next_address.save() 
                    
            address.delete()
                    
        messages.success(request, "Address deleted successfully.")             
                    
    return redirect('address_list')   

@user_required
def set_default_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    
    if request.method == 'POST':
        Address.objects.filter(user=request.user, is_default=True).update(is_default=False)
        
        address.is_default = True
        address.save()

    return redirect('address_list')


@user_required
def change_email_view(request):
    if request.method == 'POST':
        new_email = request.POST.get('new_email')
        
        if not new_email:
            messages.error(request, "Email is required")
            return redirect('change_email')


        try:
            validate_email(new_email)
        except ValidationError:
            messages.error(request, "Invalid email format")
            return redirect('change_email')

        if User.objects.filter(email=new_email).exists():
            messages.error(request, "Email already in use")
            return redirect('change_email')

        request.session['new_email'] = new_email
        request.session['otp_user_id'] = request.user.id
        request.session['otp_purpose'] = 'email_change'


        otp_obj = generate_otp(request.user, purpose='email_change')

        send_otp_email(request.user, otp_obj, to_email=new_email)

        messages.success(request, "OTP sent to new email")
        return redirect('verify_otp')

    return render(request, 'userprofile/change_email.html')

