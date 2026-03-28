from django.contrib import admin
from .models import Location, Building, Floor, Room, Category, Item, InventoryTransaction, UserProfile

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
    list_display = ('name', 'location', 'image', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ('location',)
    search_fields = ('name',)

# --- CATALOG ADMIN ---
@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    # CHANGED: Swapped sub_category for category
    list_display = ('name', 'brand', 'category', 'updated_at','quantity','remarks')
    readonly_fields = ('created_at', 'updated_at')
    # CHANGED: Added your new 'colour' field to the search bar!
    search_fields = ('name', 'brand', 'colour','remarks')
    # CHANGED: Filter directly by category now
    list_filter = ('category',) 

# --- LEDGER ADMIN (The most important one for auditing) ---
@admin.register(InventoryTransaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('item', 'transaction_type', 'quantity', 'room', 'date_recorded','remarks')
    readonly_fields = ('date_recorded',)
    # This creates an awesome sidebar where HQ can filter by Damage, Receipt, etc.
    list_filter = ('transaction_type', 'date_recorded') 
    search_fields = ('item__name', 'remarks')

# --- SPATIAL ADMIN (Floors & Rooms with image support) ---
@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'image', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ('building',)
    search_fields = ('name',)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'floor', 'image', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ('floor',)
    search_fields = ('name',)

# --- BASIC REGISTRATIONS ---
admin.site.register(Category)
admin.site.register(UserProfile)