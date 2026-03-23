"""
URL configuration for KIMS project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.contrib import admin
from django.urls import path
from inventory import views 
from django.contrib.auth import views as auth_views
from django.conf import settings             
from django.conf.urls.static import static   

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard_view, name='dashboard'), 
    path('login/', auth_views.LoginView.as_view(template_name='inventory/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    
    # THE SPATIAL DRILL-DOWN URLs
    path('location/<int:location_id>/buildings/', views.select_building, name='select_building'),
    path('building/<int:building_id>/floors/', views.select_floor, name='select_floor'),
    path('floor/<int:floor_id>/rooms/', views.select_room, name='select_room'),
    
    # THE FINAL DESTINATION (The Room Ledger)
    path('room/<int:room_id>/ledger/', views.room_ledger, name='room_ledger'),

    # THE SMART FORM (Locked to the specific room!)
    path('room/<int:room_id>/add-stock/', views.update_stock_view, name='update_stock'),
]

# NEW: This tells Django to show images in the browser
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)