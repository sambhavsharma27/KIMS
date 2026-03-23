from django.contrib import admin
from .models import Location, Building, Floor, Room, Category, SubCategory, Item, InventoryTransaction, UserProfile

# --- SPATIAL ADMIN ---
@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    # This tells Django which columns to show in the master list
    list_display = ('name', 'is_active', 'created_at', 'updated_at')
    # This shows the dates inside the edit screen, but prevents altering them
    readonly_fields = ('created_at', 'updated_at')
    # Adds a search bar for locations
    search_fields = ('name',)

@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ('location',) # Adds a filter sidebar!

# --- CATALOG ADMIN ---
@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'sub_category', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    search_fields = ('name', 'brand')
    list_filter = ('sub_category__category',) 

# --- LEDGER ADMIN (The most important one for auditing) ---
@admin.register(InventoryTransaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('item', 'transaction_type', 'quantity', 'room', 'date_recorded')
    readonly_fields = ('date_recorded',)
    # This creates an awesome sidebar where HQ can filter by Damage, Receipt, etc.
    list_filter = ('transaction_type', 'date_recorded') 
    search_fields = ('item__name', 'remarks')

# --- BASIC REGISTRATIONS (For the simpler tables) ---
admin.site.register(Floor)
admin.site.register(Room)
admin.site.register(Category)
admin.site.register(SubCategory)
admin.site.register(UserProfile)