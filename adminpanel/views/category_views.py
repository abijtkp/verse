from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q
from products.models import Category
from .core_views import admin_required
import re 


@never_cache
@admin_required
def category_list_view(request):
    search_query = request.GET.get('q', '').strip()

    all_categories = Category.objects.filter(is_deleted=False)
    categories = all_categories.order_by('-created_at')

    if search_query:
        categories = categories.filter(
            Q(category_name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    paginator = Paginator(categories, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'total_count':all_categories.count(),
        'active_count':all_categories.filter(is_active=True).count(),
        'inactive_count':all_categories.filter(is_active=False).count(),
    }
    return render(request, 'adminpanel/category_list.html', context)


@never_cache
@admin_required
def add_category_view(request):
    if request.method == 'POST':
        
        category_name = request.POST.get('category_name', '').strip()
        category_name = re.sub(r'\s+', ' ', category_name).strip()
        
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        errors = {}

        if not category_name:
            errors['category_name'] = 'Category name is required.'
            
        elif len(category_name) < 2:
            errors['category_name'] = 'Category name must be at least 2 characters.'
            
        elif Category.objects.filter(category_name__iexact=category_name, is_deleted=False).exists():
            errors['category_name'] = 'This category already exists.'
            
        if description and len(description) < 10:
            errors['description'] = 'Description must be at least 10 characters.'    

        if errors:
            return render(request, 'adminpanel/add_category.html', {
                'errors': errors,
                'form_data': {
                    'category_name': category_name,
                    'description': description,
                    'is_active': is_active,
                }
            })

        Category.objects.create(
            category_name=category_name,
            description=description,
            is_active=is_active,
        )

        messages.success(request, 'Category added successfully.')
        return redirect('category_list')

    return render(request, 'adminpanel/add_category.html')


@never_cache
@admin_required
def edit_category_view(request, category_id):
    category = get_object_or_404(Category, id=category_id, is_deleted=False)

    if request.method == 'POST':
        category_name = request.POST.get('category_name', '').strip()
        category_name = re.sub(r'\s+', ' ', category_name).strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        errors = {}

        if not category_name:
            errors['category_name'] = 'Category name is required.'
            
        elif len(category_name) < 2:
            errors['category_name'] = 'Category name must be at least 2 characters.'
            
        elif Category.objects.filter(
            category_name__iexact=category_name,
            is_deleted=False
        ).exclude(id=category.id).exists():
            errors['category_name'] = 'Another category with this name already exists.'
            
        if description and len(description) < 10:
            errors['description'] = 'Description must be at least 10 characters.'    

        if errors:
            return render(request, 'adminpanel/edit_category.html', {
                'category': category,
                'errors': errors,
                'form_data': {
                    'category_name': category_name,
                    'description': description,
                    'is_active': is_active,
                }
            })

        category.category_name = category_name
        category.description = description
        category.is_active = is_active
        category.save()

        messages.success(request, 'Category updated successfully.')
        return redirect('category_list')

    return render(request, 'adminpanel/edit_category.html', {
        'category': category
    })


@require_POST
@never_cache
@admin_required
def delete_category_view(request, category_id):
    category = get_object_or_404(Category, id=category_id, is_deleted=False)

    category.is_deleted = True
    category.is_active = False
    category.save()

    messages.success(request, 'Category deleted successfully.')
    return redirect('category_list')