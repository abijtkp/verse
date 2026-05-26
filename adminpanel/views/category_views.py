import logging
import re 

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q

from products.models import Category
from .core_views import admin_required

logger = logging.getLogger(__name__)

@never_cache
@admin_required
def category_list_view(request):
    search_query = request.GET.get('q', '').strip()

    all_categories = Category.objects.filter(is_deleted=False)
    categories = all_categories.order_by('-created_at')

    if search_query:
        
        logger.info(
            "Admin searched categories | admin_id=%s | admin_email=%s | query=%s",
            request.user.id,
            request.user.email,
            search_query,
        )

        
        categories = categories.filter(
            Q(category_name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    paginator = Paginator(categories, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    logger.info(
        "Admin viewed category list | admin_id=%s | admin_email=%s | page=%s",
        request.user.id,
        request.user.email,
        page_number or 1,
    )

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
        category_image = request.FILES.get('category_image')
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        errors = {}

        if not category_name:
            errors['category_name'] = 'Category name is required.'
            
        elif len(category_name) < 2:
            errors['category_name'] = 'Category name must be at least 2 characters.'
            
        elif Category.objects.filter(category_name__iexact=category_name, is_deleted=False).exists():
            
            logger.warning(
                "Admin attempted duplicate category create | admin_id=%s | admin_email=%s | category_name=%s",
                request.user.id,
                request.user.email,
                category_name,
            )
            
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

        category = Category.objects.create(
            category_name=category_name,
            description=description,
            category_image=category_image,
            is_active=is_active,
        )
        
        logger.info(
            "Admin created category | admin_id=%s | admin_email=%s | category_id=%s | category_name=%s | is_active=%s",
            request.user.id,
            request.user.email,
            category.id,
            category.category_name,
            category.is_active,
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
        category_image = request.FILES.get('category_image')
        remove_image = request.POST.get('remove_image') == 'on'
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
            
            logger.warning(
                "Admin attempted duplicate category update | admin_id=%s | admin_email=%s | category_id=%s | attempted_name=%s",
                request.user.id,
                request.user.email,
                category.id,
                category_name,
            )
            
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

        old_name = category.category_name
        old_description = category.description or ''
        old_status = category.is_active
        
        old_image = bool(category.category_image)
        image_removed = False
        image_uploaded = False

        category.category_name = category_name
        category.description = description
        category.is_active = is_active
        
        if remove_image and category.category_image:
            category.category_image.delete(save=False)
            category.category_image = None
            image_removed = True

        
        if category_image:
            category.category_image = category_image
            image_uploaded = True
            
        category.save()
        
        logger.info(
            "Admin updated category | admin_id=%s | admin_email=%s | category_id=%s | old_name=%s | new_name=%s | old_status=%s | new_status=%s | had_old_image=%s | image_removed=%s | image_uploaded=%s",
            request.user.id,
            request.user.email,
            category.id,
            old_name,
            category.category_name,
            old_status,
            category.is_active,
            old_image,
            image_removed,
            image_uploaded,
        )

        only_status_changed = (
            old_name == category_name and
            old_description == description and
            old_status != is_active
        )

        if only_status_changed:
            if is_active:
                messages.success(request, 'Category activated successfully.')
            else:
                messages.success(request, 'Category deactivated successfully.')
        else:
            messages.success(request, 'Category updated successfully.')
            
        return redirect('category_list')

    return render(request, 'adminpanel/edit_category.html', {
               'category': category
            })


@require_POST
@never_cache
@admin_required
def toggle_category_status_view(request, category_id):
    category = get_object_or_404(Category, id=category_id, is_deleted=False)
    
    old_status = category.is_active
    
    category.is_active = not category.is_active
    category.save(update_fields=['is_active', 'updated_at'])
    
    logger.warning(
        "Admin toggled category status | admin_id=%s | admin_email=%s | category_id=%s | category_name=%s | old_status=%s | new_status=%s",
        request.user.id,
        request.user.email,
        category.id,
        category.category_name,
        old_status,
        category.is_active,
    )
    
    if category.is_active:
        messages.success(request, 'Category activated successfully.')
    else:
        messages.success(request, 'Category deactivated successfully.')

    return redirect('category_list')