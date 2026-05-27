from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy


urlpatterns = [
    path('', views.profile_view, name='profile'),
    path('edit/', views.edit_profile_view, name='edit_profile'),
    path('update-profile-photo/', views.update_profile_photo, name='update_profile_photo'),
    path('remove-profile-photo/', views.remove_profile_photo, name='remove_profile_photo'),

    path('addresses/', views.address_list, name='address_list'),
    path('addresses/add/', views.add_address, name='add_address'),
    path('addresses/<int:pk>/edit/', views.edit_address, name='edit_address'),
    path('addresses/<int:pk>/delete/', views.delete_address, name='delete_address'),
    path('addresses/<int:pk>/set-default/', views.set_default_address, name='set_default_address'),

    path('change-email/', views.change_email_view, name='change_email'),
    path('change-password/', views.change_password_view, name='change_password'),
    
    path(
        'change-password/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='userprofile/change_password_done.html'
        ),
        name='password_change_done'
    ),
]