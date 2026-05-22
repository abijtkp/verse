from django.urls import path
from . import views
from .views import (
    order_views, 
    coupon_views, 
    offer_views,
    report_views
)

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
    path('categories/toggle-status/<int:category_id>/', views.toggle_category_status_view, name='toggle_category_status'),
    
    path('products/', views.product_list_view, name='product_list'),
    path('products/add/', views.add_product_view, name='add_product'),
    path('products/edit/<int:product_id>/', views.edit_product_view, name='edit_product'),
    path('products/delete/<int:product_id>/', views.delete_product_view, name='delete_product'),
    
    path('products/<int:product_id>/variants/', views.variant_management_view, name='variant_management'),
    path('products/<int:product_id>/variants/<int:variant_id>/edit/', views.edit_variant_view, name='edit_variant'),

    path('variants/<int:variant_id>/images/add/', views.add_variant_image_view, name='add_variant_image'),
    path('variant-images/<int:image_id>/delete/', views.delete_variant_image_view, name='delete_variant_image'),
    path('variant-images/<int:image_id>/set-primary/', views.set_primary_variant_image_view, name='set_primary_variant_image'),

    path('variants/delete/<int:variant_id>/', views.delete_variant_view, name='delete_variant'),
    
    path('orders/', order_views.admin_order_list_view, name='admin_order_list'),
    path('orders/<str:order_id>/update-status/', order_views.update_order_status_view, name='update_order_status'),
    path('orders/<str:order_id>/', order_views.admin_order_detail_view, name='admin_order_detail'),
    
    path('returns/', order_views.admin_return_list_view, name='admin_return_list'),
    path('returns/<int:item_id>/approve/', order_views.approve_return_request_view, name='approve_return_request'),
    path('returns/<int:item_id>/reject/', order_views.reject_return_request_view, name='reject_return_request'),
    
    path('coupons/', coupon_views.coupon_list_view, name='coupon_list'),
    path('coupons/add/', coupon_views.add_coupon_view, name='add_coupon'),
    path('coupons/edit/<int:coupon_id>/', coupon_views.edit_coupon_view, name='edit_coupon'),
    path('coupons/toggle-status/<int:coupon_id>/', coupon_views.toggle_coupon_status_view, name='toggle_coupon_status'),
    
    path('offers/', offer_views.offer_list_view, name='offer_list'),
    path('offers/add/', offer_views.add_offer_view, name='add_offer'),
    path('offers/edit/<str:offer_type>/<int:offer_id>/', offer_views.edit_offer_view, name='edit_offer'),
    path('offers/toggle-status/<str:offer_type>/<int:offer_id>/', offer_views.toggle_offer_status_view, name='toggle_offer_status'),
    
    path('sales-report/', report_views.sales_report_view, name='sales_report'),
    path('sales-report/export/excel/', report_views.export_sales_report_excel, name='sales_report_excel'),
    path('sales-report/export/pdf/',report_views.export_sales_report_pdf, name='sales_report_pdf'),

]