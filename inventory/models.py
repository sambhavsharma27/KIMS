from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# --- THE AUDIT TRACKER ---
class TimeStampedModel(models.Model):
    """
    An abstract base class that provides self-updating 
    'created_at' and 'updated_at' fields to any model that uses it.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True # This tells Django NOT to create a separate table for this


# --- SPATIAL TREE ---
class Location(TimeStampedModel):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self): 
        return self.name


class Building(TimeStampedModel):
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='building_photos/', blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.location.name})"


class Floor(TimeStampedModel):
    building = models.ForeignKey(Building, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='floor_photos/', blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.building.name}"


class Room(TimeStampedModel):
    floor = models.ForeignKey(Floor, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='room_photos/', blank=True, null=True)

    def __str__(self):
        return self.name


# --- CATEGORY TREE ---
class Category(TimeStampedModel):
    name = models.CharField(max_length=100)

    def __str__(self): 
        return self.name

# (SubCategory was safely removed from here)


# --- ITEM BLUEPRINT ---
class Item(TimeStampedModel):
    # Links directly to Category now
    category = models.ForeignKey(Category, on_delete=models.PROTECT, null=True, blank=True)
    
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100, blank=True, null=True)
    
    # NEW: Specific field for Colour
    colour = models.CharField(max_length=50, blank=True, null=True)
    
    catalog_image = models.ImageField(upload_to='catalog_photos/', blank=True, null=True)
    specifications = models.JSONField(default=dict, blank=True)

    quantity = models.IntegerField(default=0)

    remarks = models.CharField(blank=True, null=True)
    def __str__(self): 
        # Cleanly formats name e.g., "Samsung Television - Black"
        parts = filter(None, [self.brand, self.name])
        base_name = " ".join(parts)
        return f"{base_name} - {self.colour}" if self.colour else base_name


# --- THE LEDGER ---
class InventoryTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('RECEIPT', 'Received New (Introduction)'),
        ('DAMAGE', 'Damaged/Broken'),
        ('TRANSFER', 'Sent/Transferred'),
    )
    
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    room = models.ForeignKey(Room, on_delete=models.PROTECT)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField()
    incident_photo = models.ImageField(upload_to='incident_photos/', blank=True, null=True)
    
    date_recorded = models.DateField(default=timezone.now)
    remarks = models.CharField(blank=True, null=True)
    
    # NEW: Origin tracker for when items are introduced
    received_from = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. Solan, H6, Chandigarh")
    
    def __str__(self): 
        return f"{self.transaction_type}: {self.quantity} x {self.item.name} at {self.room.name}"


# --- SECURITY ---
class UserProfile(TimeStampedModel):
    ROLE_CHOICES = (
        ('HQ', 'Headquarters Admin'),
        ('LOCAL', 'Local Location Manager'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='LOCAL')
    assigned_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self): 
        return f"{self.user.username} - {self.role}"