from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.cache import never_cache

from django.db import transaction
from products.models import Product, Category, Variant, VariantImage
from products.utils import optimize_variant_image
from .core_views import admin_required

import logging

logger = logging.getLogger(__name__)


@never_cache
@admin_required
def product_list_view(request):
    search_query = request.GET.get('q', '').strip()
    selected_category = request.GET.get('category', '').strip()
    sort_by = request.GET.get('sort', 'latest').strip()

    products = Product.objects.filter(is_deleted=False).select_related('category').prefetch_related('variants__images')

    if search_query:
        
        logger.info(
            "Admin searched products | admin_id=%s | admin_email=%s | query=%s",
            request.user.id,
            request.user.email,
            search_query,
        )
        
        products = products.filter(
            Q(product_name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(category__category_name__icontains=search_query) 
        )
    
    if selected_category:
        products = products.filter(category_id=selected_category)    
    
    if sort_by == 'oldest':
        products = products.order_by('created_at')
        
    elif sort_by == 'name_az':
        products = products.order_by('product_name')
        
    elif sort_by == 'name_za':
        products = products.order_by('-product_name')
        
    else:
        products = products.order_by('-created_at')
        sort_by = 'latest'  
    
    categories = Category.objects.filter(
        is_deleted=False,
        is_active=True,
    ).order_by('category_name')
          
        
    paginator = Paginator(products, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    logger.info(
        "Admin viewed product list | admin_id=%s | admin_email=%s | search=%s | category=%s | sort=%s | page=%s",
        request.user.id,
        request.user.email,
        search_query or None,
        selected_category or None,
        sort_by,
        page_number or 1,
    )

    return render(request, 'adminpanel/product_list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'categories':categories,
        'selected_category':selected_category,
        'sort_by':sort_by,
    })


@never_cache
@admin_required
def add_product_view(request):
    categories = Category.objects.filter(is_deleted=False, is_active=True).order_by('-created_at')

    if request.method == 'POST':
        product_name = request.POST.get('product_name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        color = request.POST.get('variant_name', '').strip()
        sku_suffix = request.POST.get('sku_suffix', '').strip()
        size = request.POST.get('size', '').strip()
        stock = request.POST.get('stock', '').strip()
        price = request.POST.get('price', '').strip()
        variant_is_active = request.POST.get('stock_status') == 'active'
        images = request.FILES.getlist('variant_images')
        

        errors = {}

        if not product_name:
            errors['product_name'] = 'Product name is required.'
        
        elif Product.objects.filter(
            product_name__iexact=product_name,
            is_deleted=False
        ).exists():
            logger.warning(
                "Admin attempted duplicate product create | admin_id=%s | admin_email=%s | product_name=%s",
                request.user.id,
                request.user.email,
                product_name,
            )
            
            errors['product_name'] = "This product already exists."       

        if not category_id:
            errors['category'] = 'Category is required.'
        
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
              

        category = None
        if category_id:
            category = Category.objects.filter(
                id=category_id,
                is_deleted=False,
                is_active=True
            ).first()

            if not category:
                logger.warning(
                    "Admin attempted product create with invalid category | admin_id=%s | admin_email=%s | category_id=%s",
                    request.user.id,
                    request.user.email,
                    category_id,
                )

                errors['category'] = 'Selected category is invalid.'

        if errors:
            return render(request, 'adminpanel/add_product.html', {
                'categories': categories,
                'errors': errors,
                'form_data': request.POST,
            })

        sku = f"{product_name[:3]}-{color[:3]}-{size}-{sku_suffix}".upper().replace(" ", "")

        if Variant.objects.filter(sku__iexact=sku).exists():
            logger.warning(
                "Admin attempted duplicate SKU create | admin_id=%s | admin_email=%s | sku=%s | product_name=%s",
                request.user.id,
                request.user.email,
                sku,
                product_name,
            )
            errors['sku_suffix'] = 'This SKU already exists.'

        if errors:
            return render(request, 'adminpanel/add_product.html', {
                'categories': categories,
                'errors': errors,
                'form_data': request.POST,
            })

        try:
            with transaction.atomic():
                product = Product.objects.create(
                    product_name=product_name,
                    description=description,
                    category=category,
                    is_active=is_active,
                    is_deleted=False,
                )

                variant = Variant.objects.create(
                    product=product,
                    sku=sku,
                    color=color,
                    size=size,
                    price=price,
                    stock=int(stock),
                    is_active=variant_is_active,
                    is_deleted=False,
                    is_default=True,
                )

                for index, image in enumerate(images):
                    VariantImage.objects.create(
                        variant=variant,
                        image_url=optimize_variant_image(image),
                        is_primary=(index == 0)
                    )

        except ValueError as e:
            logger.exception(
                "Product image optimization failed during product create | admin_id=%s | admin_email=%s | product_name=%s",
                request.user.id,
                request.user.email,
                product_name,
            )
            
            errors['variant_images'] = str(e)

            return render(request, 'adminpanel/add_product.html', {
                'categories': categories,
                'errors': errors,
                'form_data': request.POST,
            })
        
        logger.info(
            "Admin created product | admin_id=%s | admin_email=%s | product_id=%s | product_name=%s | variant_id=%s | sku=%s",
            request.user.id,
            request.user.email,
            product.id,
            product.product_name,
            variant.id,
            variant.sku,
        )    

        messages.success(request, 'Product and first variant added successfully.')
        return redirect('product_list')

    return render(request, 'adminpanel/add_product.html', {
        'categories': categories,
    })


@never_cache
@admin_required
def edit_product_view(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_deleted=False)
    categories = Category.objects.filter(is_deleted=False, is_active=True).order_by('-created_at')

    if request.method == 'POST':
        product_name = request.POST.get('product_name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category', '').strip()
        is_active = request.POST.get('is_active') == 'on'
 
        errors = {}

        if not product_name:
            errors['product_name'] = 'Product name is required.'
        
        elif Product.objects.filter(
            product_name__iexact=product_name,
            is_deleted=False
        ).exclude(id=product.id).exists():
            logger.warning(
                "Admin attempted duplicate product update | admin_id=%s | admin_email=%s | product_id=%s | attempted_name=%s",
                request.user.id,
                request.user.email,
                product.id,
                product_name,
            )
            
            errors['product_name'] = "Another product with this name already exists."   

        if not category_id:
            errors['category'] = 'Category is required.'

        category = None
        if category_id:
            category = Category.objects.filter(
                id=category_id,
                is_deleted=False,
                is_active=True
            ).first()

            if not category:
                logger.warning(
                    "Admin attempted product update with invalid category | admin_id=%s | admin_email=%s | product_id=%s | category_id=%s",
                    request.user.id,
                    request.user.email,
                    product.id,
                    category_id,
                )

                errors['category'] = 'Selected category is invalid.'

        if errors:
            return render(request, 'adminpanel/edit_product.html', {
                'product': product,
                'categories': categories,
                'errors': errors,
                'form_data': request.POST,
            })
        
        old_name = product.product_name
        old_category_id = product.category_id
        old_status = product.is_active    

        product.product_name = product_name
        product.description = description
        product.category = category
        product.is_active = is_active
        product.save()
        
        logger.info(
            "Admin updated product | admin_id=%s | admin_email=%s | product_id=%s | old_name=%s | new_name=%s | old_category_id=%s | new_category_id=%s | old_status=%s | new_status=%s",
            request.user.id,
            request.user.email,
            product.id,
            old_name,
            product.product_name,
            old_category_id,
            product.category_id,
            old_status,
            product.is_active,
        )
        
        
        messages.success(request, 'Product updated successfully.')
        return redirect('product_list')

    return render(request, 'adminpanel/edit_product.html', {
        'product': product,
        'categories': categories,
    })


@never_cache
@admin_required
def delete_product_view(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_deleted=False)

    if request.method == 'POST':
        old_status = product.is_active
        product.is_active = not product.is_active
        product.save(update_fields=['is_active', 'updated_at'])
        
        logger.warning(
            "Admin toggled product status | admin_id=%s | admin_email=%s | product_id=%s | product_name=%s | old_status=%s | new_status=%s",
            request.user.id,
            request.user.email,
            product.id,
            product.product_name,
            old_status,
            product.is_active,
        )
        
        if product.is_active:
            messages.success(request, "Product activated successfully.")
        else:
            messages.success(request, "Product deactivated successfully.")
            
        return redirect('product_list')
    
    logger.warning(
        "Invalid product status toggle request | admin_id=%s | admin_email=%s | product_id=%s | method=%s",
        request.user.id,
        request.user.email,
        product.id,
        request.method,
    )


    messages.error(request, 'Invalid request.')
    return redirect('product_list')