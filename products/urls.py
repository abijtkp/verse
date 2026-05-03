from django.urls import path
from . import views

urlpatterns = [
    path('collections/', views.product_listing_view, name='product_listing'),
]