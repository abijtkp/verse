from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from adminpanel.views.core_views import admin_required
from coupons.models import Coupon
from decimal import Decimal
from django.utils import timezone
from datetime import datetime, time 

@admin_required
def coupon_list_view(request):

    search_query = request.GET.get('q', '').strip()

    coupons = Coupon.objects.all().order_by('-created_at')

    if search_query:
        coupons = coupons.filter(
            Q(code__icontains=search_query)
        )

    paginator = Paginator(coupons, 10)

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }

    return render(
        request,
        'adminpanel/coupons/coupon_list.html',
        context
    )


@admin_required
def add_coupon_view(request):

    field_errors = {}
    form_data = {}

    if request.method == 'POST':

        form_data = {
            'code': request.POST.get('code', '').strip().upper(),
            'discount_type': request.POST.get('discount_type', '').strip(),
            'discount_value': request.POST.get('discount_value', '').strip(),
            'minimum_order_amount': request.POST.get('minimum_order_amount', '').strip(),
            'maximum_discount_amount': request.POST.get('maximum_discount_amount', '').strip(),
            'valid_from': request.POST.get('valid_from', '').strip(),
            'valid_to': request.POST.get('valid_to', '').strip(),
            'usage_limit': request.POST.get('usage_limit', '').strip(),
            'is_active': request.POST.get('is_active') == 'on',
        }

        code = form_data['code']
        discount_type = form_data['discount_type']
        discount_value = form_data['discount_value']
        minimum_order_amount = form_data['minimum_order_amount']
        maximum_discount_amount = form_data['maximum_discount_amount']
        valid_from = form_data['valid_from']
        valid_to = form_data['valid_to']
        usage_limit = form_data['usage_limit']
        is_active = form_data['is_active']


        if not code:
            field_errors['code'] = 'Coupon code is required.'

        elif Coupon.objects.filter(code__iexact=code).exists():
            field_errors['code'] = 'Coupon code already exists.'

        elif len(code) < 3:
            field_errors['code'] = 'Coupon code must contain at least 3 characters.'


        if discount_type not in ['percentage', 'fixed']:
            field_errors['discount_type'] = 'Select a valid discount type.'


        try:
            discount_value = Decimal(discount_value)

            if discount_value <= 0:
                field_errors['discount_value'] = 'Discount value must be greater than 0.'

            if discount_type == 'percentage' and discount_value > 90:
                field_errors['discount_value'] = 'Percentage discount cannot exceed 90%.'

        except:
            field_errors['discount_value'] = 'Enter a valid discount value.'


        try:
            minimum_order_amount = Decimal(
                minimum_order_amount or '0'
            )

            if minimum_order_amount < 0:
                field_errors['minimum_order_amount'] = 'Minimum order amount cannot be negative.'

        except:
            field_errors['minimum_order_amount'] = 'Enter a valid amount.'


        try:

            if maximum_discount_amount:

                maximum_discount_amount = Decimal(maximum_discount_amount)

                if maximum_discount_amount <= 0:
                    field_errors['maximum_discount_amount'] = 'Maximum discount must be greater than 0.'

            else:
                maximum_discount_amount = None

        except:
            field_errors['maximum_discount_amount'] = 'Enter a valid amount.'
            
            
        if discount_type == 'percentage' and maximum_discount_amount is None:
            field_errors['maximum_discount_amount'] = 'Maximum discount amount is required for percentage coupons.'
            
        if (
            discount_type == 'fixed'
            and 'discount_value' not in field_errors
            and 'minimum_order_amount' not in field_errors
            and discount_value > minimum_order_amount
        ):
            field_errors['discount_value'] = 'Fixed discount cannot be greater than minimum order amount.'        


        try:
            valid_from_obj = timezone.make_aware(
                datetime.strptime(valid_from, "%Y-%m-%dT%H:%M")
            )
        except:
            field_errors['valid_from'] = 'Enter a valid start date and time.'

        try:
            valid_to_obj = timezone.make_aware(
                datetime.strptime(valid_to, "%Y-%m-%dT%H:%M")
            )
        except:
            field_errors['valid_to'] = 'Enter a valid expiry date and time.'

        if 'valid_from' not in field_errors and 'valid_to' not in field_errors:

            now = timezone.now()

            if valid_from_obj < now:
                field_errors['valid_from'] = 'Start date and time cannot be in the past.'

            if valid_to_obj <= valid_from_obj:
                field_errors['valid_to'] = 'Expiry date must be after start date.'


        try:

            usage_limit = int(usage_limit)

            if usage_limit <= 0:
                field_errors['usage_limit'] = 'Usage limit must be greater than 0.'

        except:
            field_errors['usage_limit'] = 'Enter a valid usage limit.'


        if not field_errors:

            Coupon.objects.create(
                code=code,
                discount_type=discount_type,
                discount_value=discount_value,
                minimum_order_amount=minimum_order_amount,
                maximum_discount_amount=maximum_discount_amount,
                valid_from=valid_from_obj,
                valid_to=valid_to_obj,
                usage_limit=usage_limit,
                is_active=is_active,
            )

            messages.success(
                request,
                f'Coupon "{code}" created successfully.'
            )

            return redirect('coupon_list')

        messages.error(
            request,
            'Please correct the errors below.'
        )

    context = {
        'field_errors': field_errors,
        'form_data': form_data,
    }

    return render(
        request,
        'adminpanel/coupons/add_coupon.html',
        context
    )


@admin_required
def edit_coupon_view(request, coupon_id):

    coupon = get_object_or_404(
        Coupon,
        id=coupon_id
    )

    field_errors = {}
    form_data = {}

    if request.method == 'POST':

        form_data = {
            'code': request.POST.get('code', '').strip().upper(),
            'discount_type': request.POST.get('discount_type', '').strip(),
            'discount_value': request.POST.get('discount_value', '').strip(),
            'minimum_order_amount': request.POST.get('minimum_order_amount', '').strip(),
            'maximum_discount_amount': request.POST.get('maximum_discount_amount', '').strip(),
            'valid_from': coupon.valid_from.date().strftime("%Y-%m-%d"),
            'valid_to': request.POST.get('valid_to', '').strip(),
            'usage_limit': request.POST.get('usage_limit', '').strip(),
            'is_active': request.POST.get('is_active') == 'on',
        }

        code = form_data['code']
        discount_type = form_data['discount_type']
        discount_value = form_data['discount_value']
        minimum_order_amount = form_data['minimum_order_amount']
        maximum_discount_amount = form_data['maximum_discount_amount']
        valid_from = form_data['valid_from']
        valid_to = form_data['valid_to']
        usage_limit = form_data['usage_limit']
        is_active = form_data['is_active']



        if not code:
            field_errors['code'] = 'Coupon code is required.'

        elif Coupon.objects.filter(
            code__iexact=code
        ).exclude(id=coupon.id).exists():

            field_errors['code'] = 'Coupon code already exists.'

        elif len(code) < 3:
            field_errors['code'] = 'Coupon code must contain at least 3 characters.'



        if discount_type not in ['percentage', 'fixed']:
            field_errors['discount_type'] = 'Select a valid discount type.'



        try:

            discount_value = Decimal(discount_value)

            if discount_value <= 0:
                field_errors['discount_value'] = 'Discount value must be greater than 0.'

            if discount_type == 'percentage' and discount_value > 90:
                field_errors['discount_value'] = 'Percentage discount cannot exceed 90%.'

        except:
            field_errors['discount_value'] = 'Enter a valid discount value.'



        try:

            minimum_order_amount = Decimal(
                minimum_order_amount or '0'
            )

            if minimum_order_amount < 0:
                field_errors['minimum_order_amount'] = 'Minimum order amount cannot be negative.'

        except:
            field_errors['minimum_order_amount'] = 'Enter a valid amount.'



        try:

            if maximum_discount_amount:

                maximum_discount_amount = Decimal(
                    maximum_discount_amount
                )

                if maximum_discount_amount <= 0:
                    field_errors['maximum_discount_amount'] = 'Maximum discount must be greater than 0.'

            else:
                maximum_discount_amount = None

        except:
            field_errors['maximum_discount_amount'] = 'Enter a valid amount.'
        
        
        if discount_type == 'percentage' and maximum_discount_amount is None:
            field_errors['maximum_discount_amount'] = 'Maximum discount amount is required for percentage coupons.'  
            
        
        if (
            discount_type == 'fixed'
            and 'discount_value' not in field_errors
            and 'minimum_order_amount' not in field_errors
            and discount_value > minimum_order_amount
        ):
            field_errors['discount_value'] = 'Fixed discount cannot be greater than minimum order amount.'
              

        try:

            valid_from_date = datetime.strptime(
                valid_from,
                "%Y-%m-%d"
            ).date()

            valid_from_obj = timezone.make_aware(
                datetime.combine(valid_from_date, time.min)
            )

        except:
            field_errors['valid_from'] = 'Enter a valid start date.'

        try:
            valid_to_obj = timezone.make_aware(
                datetime.strptime(valid_to, "%Y-%m-%dT%H:%M")
            )
        except:
            field_errors['valid_to'] = 'Enter a valid expiry date and time.'

        if 'valid_from' not in field_errors and 'valid_to' not in field_errors:

            if valid_to_obj <= valid_from_obj:
                field_errors['valid_to'] = 'Expiry date must be after start date.'


        try:

            usage_limit = int(usage_limit)

            if usage_limit <= 0:
                field_errors['usage_limit'] = 'Usage limit must be greater than 0.'

        except:
            field_errors['usage_limit'] = 'Enter a valid usage limit.'
            
        
        if 'usage_limit' not in field_errors and usage_limit < coupon.used_count:
            field_errors['usage_limit'] = f'Usage limit cannot be less than already used count ({coupon.used_count}).'    



        if not field_errors:

            coupon.code = code
            coupon.discount_type = discount_type
            coupon.discount_value = discount_value
            coupon.minimum_order_amount = minimum_order_amount
            coupon.maximum_discount_amount = maximum_discount_amount
            coupon.valid_to = valid_to_obj
            coupon.usage_limit = usage_limit
            coupon.is_active = is_active

            coupon.save()

            messages.success(
                request,
                f'Coupon "{coupon.code}" updated successfully.'
            )

            return redirect('coupon_list')

        messages.error(
            request,
            'Please correct the errors below.'
        )

    context = {
        'coupon': coupon,
        'field_errors': field_errors,
        'form_data': form_data,
    }

    return render(
        request,
        'adminpanel/coupons/edit_coupon.html',
        context
    )
    
    
@admin_required
def toggle_coupon_status_view(request, coupon_id):
    
    if request.method != 'POST':
        return redirect('coupon_list')

    coupon = get_object_or_404(
        Coupon,
        id=coupon_id
    )

    coupon.is_active = not coupon.is_active

    coupon.save(
        update_fields=[
            'is_active',
            'updated_at'
        ]
    )

    messages.success(
        request,
        f'Coupon "{coupon.code}" status updated successfully.'
    )

    return redirect('coupon_list')