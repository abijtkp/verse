"""
URL configuration for verse_shoes project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin

urlpatterns = [
    
    path('', include('accounts.urls')),
    path('', include('products.urls')),
    
    path('admin/', admin.site.urls), 
    path('social/', include('allauth.urls')),
    path('profile/', include('userprofile.urls')),
    path('cart/', include('cart.urls')),
    path('orders/', include('orders.urls')),
    path('adminpanel/', include('adminpanel.urls')),
    path('wallet/', include('payments.urls')),

    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)