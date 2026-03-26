from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views # Added for login/logout
from inventory import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- AUTHENTICATION URLS (Restored!) ---
    path('login/', auth_views.LoginView.as_view(template_name='inventory/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # --- MAIN APP URLS ---
    path('', views.dashboard_view, name='dashboard'),
    
    path('location/<int:location_id>/buildings/', views.select_building, name='select_building'),
    path('building/<int:building_id>/floors/', views.select_floor, name='select_floor'),
    path('floor/<int:floor_id>/rooms/', views.select_room, name='select_room'),
    
    path('room/<int:room_id>/ledger/', views.room_ledger, name='room_ledger'),
    path('room/<int:room_id>/item/<int:item_id>/quick-update/', views.quick_update_stock, name='quick_update_stock'),
    path('room/<int:room_id>/add-new-item-modal/', views.add_new_item_from_modal_view, name='add_new_item_modal_submit'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)