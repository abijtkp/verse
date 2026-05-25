from django.urls import path
from . import views

urlpatterns = [
    path('collections/', views.product_listing_view, name='product_listing'),
    path('collections/product/<int:variant_id>/', views.product_detail_view, name='product_detail'),
    path('review/<int:variant_id>/', views.submit_review, name='submit_review'),
]