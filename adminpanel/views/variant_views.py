from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.db import transaction
from django.core.files.images import get_image_dimensions
from products.models import Product, Variant, VariantImage
from .core_views import admin_required
from products.utils import optimize_variant_image
from offers.utils import calculate_best_offer


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
    
    for variant in variants:
        variant.offer_data = calculate_best_offer(variant)

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
        elif color.isdigit():
            errors['variant_name'] = 'Color name cannot be only numbers.'

        if not sku_suffix:
            errors['sku_suffix'] = 'SKU suffix is required.'

        if not size:
            errors['size'] = 'Size is required.'
        elif not size.isdigit():
            errors['size'] = 'Size must be a number.'
        elif int(size) < 3 or int(size) > 15:
            errors['size'] = 'Size must be between 3 and 15.'    

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

        allowed_content_types = ['image/jpeg', 'image/png', 'image/webp']

        if len(images) < 3:
            errors['variant_images'] = 'Please upload at least 3 variant images.'
        else:
            for image in images:
                if image.content_type not in allowed_content_types:
                    errors['variant_images'] = 'Only JPG, PNG, or WEBP images are allowed.'
                    break

                if image.size > 2 * 1024 * 1024:
                    errors['variant_images'] = 'Each image must be less than 2MB.'
                    break

                try:
                    get_image_dimensions(image)
                except Exception:
                    errors['variant_images'] = 'Invalid image file.'
                    break

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
            }, status=400)
            
        try:    
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
                        image_url=optimize_variant_image(image),
                        is_primary=(index == 0)
                    )
        except ValueError as e:
            errors['variant_images'] = str(e)
            
            return render(request, 'adminpanel/variant_management.html', {
                'product':product,
                'variants':variants,
                'errors':errors,
                'form_data':request.POST,
            }, status=400)
            
        messages.success(request, 'Variant added successfully.')
        return redirect('variant_management', product_id=product.id)

    return render(request, 'adminpanel/variant_management.html', {
        'product': product,
        'variants': variants,
    })
    
    
@never_cache
@admin_required
def edit_variant_view(request, product_id, variant_id):
    product = get_object_or_404(Product, id=product_id, is_deleted=False)

    variant = get_object_or_404(
        Variant,
        id=variant_id,
        product=product,
        is_deleted=False
    )

    if request.method == 'POST':
        color = request.POST.get('variant_name', '').strip()
        size = request.POST.get('size', '').strip()
        stock = request.POST.get('stock', '').strip()
        price = request.POST.get('price', '').strip()
        is_active = request.POST.get('stock_status') == 'active'

        errors = {}

        if not color:
            errors['variant_name'] = 'Color / variant name is required.'
        elif color.isdigit():
            errors['variant_name'] = 'Color name cannot be only numbers.'

        if not size:
            errors['size'] = 'Size is required.'
        elif not size.isdigit():
            errors['size'] = 'Size must be a number.'
        elif int(size) < 3 or int(size) > 15:
            errors['size'] = 'Size must be between 3 and 15.'
            

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

        duplicate_exists = Variant.objects.filter(
            product=product,
            color__iexact=color,
            size__iexact=size,
            is_deleted=False
        ).exclude(id=variant.id).exists()

        if duplicate_exists:
            errors['size'] = 'This size already exists for this color.'

        if errors:
            variants = product.variants.filter(
                is_deleted=False
            ).prefetch_related('images').order_by('-created_at')

            for item in variants:
                item.offer_data = calculate_best_offer(item)

            return render(request, 'adminpanel/variant_management.html', {
                'product': product,
                'variants': variants,
                'edit_errors': errors,
                'edit_form_data': request.POST,
                'edit_variant_id': variant.id,
            }, status=400)

        variant.color = color
        variant.size = size
        variant.stock = int(stock)
        variant.price = price
        variant.is_active = is_active

        variant.save(update_fields=[
            'color',
            'size',
            'stock',
            'price',
            'is_active',
            'updated_at'
        ])

        messages.success(request, 'Variant updated successfully.')

        return redirect('variant_management', product_id=product.id)

    return redirect('variant_management', product_id=product.id)



@never_cache
@admin_required
def add_variant_image_view(request, variant_id):
    variant = get_object_or_404(
        Variant.objects.select_related('product'),
        id=variant_id,
        is_deleted=False
    )

    product_id = variant.product.id

    if request.method == 'POST':
        images = request.FILES.getlist('variant_images')

        if not images:
            messages.error(request, 'Please select at least one image to upload.')
            return redirect('variant_management', product_id=product_id)
        
        allowed_content_types = ['image/jpeg', 'image/png', 'image/webp']

        for image in images:
            if image.content_type not in allowed_content_types:
                messages.error(request, 'Only JPG, PNG, or WEBP images are allowed.')
                return redirect('variant_management', product_id=product_id)

            if image.size > 2 * 1024 * 1024:
                messages.error(request, 'Each image must be less than 2MB.')
                return redirect('variant_management', product_id=product_id)

            try:
                get_image_dimensions(image)
            except Exception:
                messages.error(request, 'Invalid image file.')
                return redirect('variant_management', product_id=product_id)

        has_primary = variant.images.filter(is_primary=True).exists()

        try:
            with transaction.atomic():
                for index, image in enumerate(images):
                    VariantImage.objects.create(
                        variant=variant,
                        image_url=optimize_variant_image(image),
                        is_primary=(not has_primary and index == 0)
                    )
        except ValueError as e:
            messages.error(request,str(e))
            return redirect('variant_management', product_id=product_id)
            
        messages.success(request, 'Variant image added successfully.')
        return redirect('variant_management', product_id=product_id)

    messages.error(request, 'Invalid request.')
    return redirect('variant_management', product_id=product_id)


@never_cache
@admin_required
def delete_variant_image_view(request, image_id):
    image = get_object_or_404(
        VariantImage.objects.select_related('variant__product'),
        id=image_id
    )

    variant = image.variant
    product_id = variant.product.id

    if request.method == 'POST':
        image_count = variant.images.count()

        if image_count <= 3:
            product = variant.product

            variants = product.variants.filter(
                is_deleted=False
            ).prefetch_related('images').order_by('-created_at')

            for item in variants:
                item.offer_data = calculate_best_offer(item)

            return render(request, 'adminpanel/variant_management.html', {
                'product': product,
                'variants': variants,
                'edit_image_error': 'Each variant must keep at least 3 images. Upload another image before deleting this one.',
                'edit_variant_id': variant.id,
            }, status=400)

        was_primary = image.is_primary

        with transaction.atomic():
            image.delete()

            if was_primary:
                next_image = variant.images.order_by('-created_at').first()

                if next_image:
                    next_image.is_primary = True
                    next_image.save(update_fields=['is_primary'])

        messages.success(request, 'Variant image deleted successfully.')
        return redirect('variant_management', product_id=product_id)

    messages.error(request, 'Invalid request.')
    return redirect('variant_management', product_id=product_id)


@never_cache
@admin_required
def set_primary_variant_image_view(request, image_id):
    image = get_object_or_404(
        VariantImage.objects.select_related('variant__product'),
        id=image_id
    )

    variant = image.variant
    product_id = variant.product.id

    if request.method == 'POST':
        with transaction.atomic():
            VariantImage.objects.filter(variant=variant).update(is_primary=False)

            image.is_primary = True
            image.save(update_fields=['is_primary'])

        messages.success(request, 'Primary image updated successfully.')
        return redirect('variant_management', product_id=product_id)

    messages.error(request, 'Invalid request.')
    return redirect('variant_management', product_id=product_id)   
    
    
    
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