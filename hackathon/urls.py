from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_view, name='landing'),
    path('register/', views.register_view, name='register'),
    path('register/otp/', views.otp_view, name='otp'),
    path('register/form/', views.form_view, name='form'),
    path('profile/', views.profile_view, name='profile'),
    
    # Authentication URLs
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # AJAX endpoint
    path('api/schools/<int:region_id>/', views.get_schools_by_region, name='get_schools'),
]
