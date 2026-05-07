from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.cache import never_cache

from django.db import transaction
from products.models import Product, Category, Variant, VariantImage
from products.utils import optimize_variant_image
from .core_views import admin_required




@never_cache
@admin_required
def product_list_view(request):
    search_query = request.GET.get('q', '').strip()
    selected_category = request.GET.get('category', '').strip()
    sort_by = request.GET.get('sort', 'latest').strip()

    products = Product.objects.filter(is_deleted=False).select_related('category').prefetch_related('variants__images')

    if search_query:
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
                errors['category'] = 'Selected category is invalid.'

        if errors:
            return render(request, 'adminpanel/add_product.html', {
                'categories': categories,
                'errors': errors,
                'form_data': request.POST,
            })

        sku = f"{product_name[:3]}-{color[:3]}-{size}-{sku_suffix}".upper().replace(" ", "")

        if Variant.objects.filter(sku__iexact=sku).exists():
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
            errors['variant_images'] = str(e)

            return render(request, 'adminpanel/add_product.html', {
                'categories': categories,
                'errors': errors,
                'form_data': request.POST,
            })

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
        ).exists():
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
                errors['category'] = 'Selected category is invalid.'

        if errors:
            return render(request, 'adminpanel/edit_product.html', {
                'product': product,
                'categories': categories,
                'errors': errors,
                'form_data': request.POST,
            })

        product.product_name = product_name
        product.description = description
        product.category = category
        product.is_active = is_active
        product.save()
        
        
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
        product.is_active = not product.is_active
        product.save(update_fields=['is_active', 'updated_at'])
        
        if product.is_active:
            messages.success(request, "Product activated successfully.")
        else:
            messages.success(request, "Product deactivated successfully.")
            
        return redirect('product_list')

    messages.error(request, 'Invalid request.')
    return redirect('product_list')