from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.db import transaction

from products.models import Product, Variant, VariantImage
from .core_views import admin_required


@never_cache
@admin_required
def variant_management_view(request, product_id):
    product = get_object_or_404(
        Product.objects.select_related('category'),
        id=product_id,
        is_deleted=False
    )

    variants = product.variants.filter(
        is_deleted=False
    ).prefetch_related('images').order_by('-created_at')

    if request.method == 'POST':
        color = request.POST.get('variant_name', '').strip()
        sku_suffix = request.POST.get('sku_suffix', '').strip()
        size = request.POST.get('size', '').strip()
        stock = request.POST.get('stock', '').strip()
        price = request.POST.get('price', '').strip()
        is_active = request.POST.get('stock_status') == 'active'
        images = request.FILES.getlist('variant_images')

        errors = {}

        if not color:
            errors['variant_name'] = 'Color / variant name is required.'

        if not sku_suffix:
            errors['sku_suffix'] = 'SKU suffix is required.'

        if not size:
            errors['size'] = 'Size is required.'

        if not stock:
            errors['stock'] = 'Stock is required.'
        elif not stock.isdigit():
            errors['stock'] = 'Stock must be a valid number.'

        if not price:
            errors['price'] = 'Price is required.'
        else:
            try:
                price = float(price)
                if price <= 0:
                    errors['price'] = 'Price must be greater than zero.'
            except ValueError:
                errors['price'] = 'Enter a valid price.'

        if len(images) < 3:
            errors['variant_images'] = 'Please upload at least 3 variant images.'

        sku = f"{product.product_name[:3]}-{color[:3]}-{size}-{sku_suffix}".upper().replace(" ", "")

        if Variant.objects.filter(sku__iexact=sku).exists():
            errors['sku_suffix'] = 'This SKU already exists.'

        if Variant.objects.filter(
            product=product,
            color__iexact=color,
            size__iexact=size,
            is_deleted=False
        ).exists():
            errors['size'] = 'This size already exists for this color.'

        if errors:
            return render(request, 'adminpanel/variant_management.html', {
                'product': product,
                'variants': variants,
                'errors': errors,
                'form_data': request.POST,
            })

        with transaction.atomic():
            variant = Variant.objects.create(
                product=product,
                sku=sku,
                color=color,
                size=size,
                price=price,
                stock=int(stock),
                is_active=is_active,
                is_deleted=False,
                is_default=False,
            )

            for index, image in enumerate(images):
                VariantImage.objects.create(
                    variant=variant,
                    image_url=image,
                    is_primary=(index == 0)
                )

        messages.success(request, 'Variant added successfully.')
        return redirect('variant_management', product_id=product.id)

    return render(request, 'adminpanel/variant_management.html', {
        'product': product,
        'variants': variants,
    })
    
    
@never_cache
@admin_required
def delete_variant_view(request, variant_id):
    variant = get_object_or_404(
        Variant,
        id=variant_id,
        is_deleted=False
    )

    product_id = variant.product.id

    if request.method == 'POST':
        variant.is_deleted = True
        variant.is_active = False
        variant.save(update_fields=['is_deleted', 'is_active', 'updated_at'])

        messages.success(request, 'Variant deleted successfully.')
        return redirect('variant_management', product_id=product_id)

    messages.error(request, 'Invalid request.')
    return redirect('variant_management', product_id=product_id)   