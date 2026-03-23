from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# --- THE AUDIT TRACKER (New) ---
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
# Notice how we change (models.Model) to (TimeStampedModel)
class Location(TimeStampedModel):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name

class Building(TimeStampedModel):
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    def __str__(self): return f"{self.name} ({self.location.name})"

class Floor(TimeStampedModel):
    building = models.ForeignKey(Building, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    def __str__(self): return f"{self.name} - {self.building.name}"

class Room(TimeStampedModel):
    floor = models.ForeignKey(Floor, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    def __str__(self): return self.name

# --- CATEGORY TREE ---
class Category(TimeStampedModel):
    name = models.CharField(max_length=100)
    def __str__(self): return self.name

class SubCategory(TimeStampedModel):
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    def __str__(self): return f"{self.category.name} -> {self.name}"

# --- ITEM BLUEPRINT ---
class Item(TimeStampedModel):
    sub_category = models.ForeignKey(SubCategory, on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100, blank=True, null=True)
    catalog_image = models.ImageField(upload_to='catalog_photos/', blank=True, null=True)
    specifications = models.JSONField(default=dict, blank=True) 
    def __str__(self): return f"{self.brand} {self.name}" if self.brand else self.name

# --- THE LEDGER ---
# We keep this as models.Model because transactions shouldn't be "updated", only created.
class InventoryTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('RECEIPT', 'Received New'),
        ('DAMAGE', 'Damaged/Broken'),
        ('TRANSFER', 'Sent/Transferred'),
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    room = models.ForeignKey(Room, on_delete=models.PROTECT)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField()
    incident_photo = models.ImageField(upload_to='incident_photos/', blank=True, null=True)
    
    # This is the crucial timestamp for inventory movements!
    date_recorded = models.DateField(default=timezone.now)
    remarks = models.TextField(blank=True, null=True)
    
    def __str__(self): return f"{self.transaction_type}: {self.quantity} x {self.item.name} at {self.room.name}"

# --- SECURITY ---
class UserProfile(TimeStampedModel):
    ROLE_CHOICES = (
        ('HQ', 'Headquarters Admin'),
        ('LOCAL', 'Local Location Manager'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='LOCAL')
    assigned_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    def __str__(self): return f"{self.user.username} - {self.role}"