from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.cache import never_cache

from products.models import Product, Category
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

        errors = {}

        if not product_name:
            errors['product_name'] = 'Product name is required.'

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
            return render(request, 'adminpanel/add_product.html', {
                'categories': categories,
                'errors': errors,
                'form_data': request.POST,
            })

        product = Product.objects.create(
            product_name=product_name,
            description=description,
            category=category,
            is_active=is_active,
            is_deleted=False,
        )
        

        messages.success(request, 'Product added successfully.')
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
        product.is_deleted = not product.is_active
        product.save(update_fields=['is_active', 'updated_at'])
        
        if product.is_active:
            messages.success(request, "Product activated successfully.")
        else:
            messages.success(request, "Product deactivated succesfully.")
            
            return redirect('product_list')

    messages.error(request, 'Invalid request.')
    return redirect('product_list')