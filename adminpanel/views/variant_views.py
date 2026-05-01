from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.cache import never_cache

from products.models import Product, ColorVariant
from .core_views import admin_required


@never_cache
@admin_required
def color_variant_list_view(request, product_id):
    product = get_object_or_404(
        Product,
        id=product_id,
        is_deleted=False
    )

    color_variants = product.color_variants.filter(
        is_deleted=False
    ).order_by('-created_at')

    return render(request, 'adminpanel/color_variant_list.html', {
        'product': product,
        'color_variants': color_variants,
    })


@never_cache
@admin_required
def add_color_variant_view(request, product_id):
    product = get_object_or_404(
        Product,
        id=product_id,
        is_deleted=False
    )

    if request.method == 'POST':
        color_name = request.POST.get('color_name', '').strip()
        color_code = request.POST.get('color_code', '').strip()

        errors = {}

        if not color_name:
            errors['color_name'] = 'Color name is required.'

        existing_variant = ColorVariant.objects.filter(
            product=product,
            color_name__iexact=color_name,
            is_deleted=False
        ).exists()

        if existing_variant:
            errors['color_name'] = 'This color variant already exists.'

        if errors:
            return render(request, 'adminpanel/add_color_variant.html', {
                'product': product,
                'errors': errors,
                'form_data': request.POST,
            })

        ColorVariant.objects.create(
            product=product,
            color_name=color_name,
            color_code=color_code,
            is_active=True,
            is_deleted=False,
        )

        messages.success(request, 'Color variant added successfully.')
        return redirect('color_variant_list', product_id=product.id)

    return render(request, 'adminpanel/add_color_variant.html', {
        'product': product,
    })