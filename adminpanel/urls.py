from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard_view, name='admin_dashboard'),
    path('login/', views.admin_login_view, name='admin_login'),
    path('logout/', views.admin_logout_view, name='admin_logout'),
    
    path('users/', views.user_management_view, name='user_management'),
    path('users/block/<int:user_id>/', views.block_user_view, name='block_user'),
    path('users/unblock/<int:user_id>/', views.unblock_user_view, name='unblock_user'),
    
    path('categories/', views.category_list_view, name='category_list'),
    path('categories/add/', views.add_category_view, name='add_category'),
    path('categories/edit/<int:category_id>/', views.edit_category_view, name='edit_category'),
    path('categories/delete/<int:category_id>/', views.delete_category_view, name='delete_category'),
    
    path('products/', views.product_list_view, name='product_list'),
    path('products/add/', views.add_product_view, name='add_product'),
    path('products/edit/<int:product_id>/', views.edit_product_view, name='edit_product'),
    path('products/delete/<int:product_id>/', views.delete_product_view, name='delete_product'),
    
    path('products/<int:product_id>/variants/', views.color_variant_list_view, name='color_variant_list'),
    path('products/<int:product_id>/variants/add/', views.add_color_variant_view, name='add_color_variant'),
]