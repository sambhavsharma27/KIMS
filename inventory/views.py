import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Location, Building, Floor, Room, Category, SubCategory, Item, InventoryTransaction

# ==========================================
# 1. THE MASTER DASHBOARD (WITH FILTERS)
# ==========================================
@login_required
# ==========================================
# 1. THE MASTER DASHBOARD (WITH FILTERS)
# ==========================================
@login_required
def dashboard_view(request):
    user_profile = getattr(request.user, 'userprofile', None)
    
    if user_profile and user_profile.role == 'LOCAL':
        location = user_profile.assigned_location
        locations = Location.objects.filter(id=location.id)
    else:
        location = Location.objects.first()
        locations = Location.objects.filter(is_active=True)

    if location:
        transactions = InventoryTransaction.objects.filter(room__floor__building__location=location).order_by('-date_recorded')
        buildings = Building.objects.filter(location=location)
        floors = Floor.objects.filter(building__location=location)
        rooms = Room.objects.filter(floor__building__location=location)
    else:
        transactions = InventoryTransaction.objects.none()
        buildings = floors = rooms = []

    # NEW: Catch the Sub-Category and Search Name from the form
    b_id = request.GET.get('building')
    f_id = request.GET.get('floor')
    r_id = request.GET.get('room')
    c_id = request.GET.get('category')
    sc_id = request.GET.get('sub_category')
    search_name = request.GET.get('search_name')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Apply the filters
    if b_id: transactions = transactions.filter(room__floor__building_id=b_id)
    if f_id: transactions = transactions.filter(room__floor_id=f_id)
    if r_id: transactions = transactions.filter(room_id=r_id)
    if c_id: transactions = transactions.filter(item__sub_category__category_id=c_id)
    if sc_id: transactions = transactions.filter(item__sub_category_id=sc_id)
    if search_name: transactions = transactions.filter(item__name__icontains=search_name) # Searches for partial matches!
    if start_date: transactions = transactions.filter(date_recorded__gte=start_date)
    if end_date: transactions = transactions.filter(date_recorded__lte=end_date)

    context = {
        'locations': locations,
        'current_location': location,
        'buildings': buildings,
        'floors': floors,
        'rooms': rooms,
        'categories': Category.objects.all(),
        'sub_categories': SubCategory.objects.all(), # NEW: Sending Sub-Categories to HTML
        'transactions': transactions,
    }
    return render(request, 'inventory/dashboard.html', context)


# ==========================================
# 2. SMART FORM (WITH IMAGE UPLOADS)
# ==========================================
@login_required
def update_stock_view(request, room_id):
    room = get_object_or_404(Room, id=room_id)

    if request.method == 'POST':
        category_id = request.POST.get('category')
        sub_category_name = request.POST.get('sub_category_name')
        item_name = request.POST.get('item_name')
        item_brand = request.POST.get('item_brand')
        transaction_type = request.POST.get('transaction_type')
        quantity = request.POST.get('quantity')
        remarks = request.POST.get('remarks')
        date_recorded_input = request.POST.get('date_recorded') 
        
        # Catch the newly added image file!
        catalog_image = request.FILES.get('catalog_image')

        spec_keys = request.POST.getlist('spec_keys[]')
        spec_values = request.POST.getlist('spec_values[]')
        
        specifications_dict = {}
        for key, value in zip(spec_keys, spec_values):
            if key and value:
                specifications_dict[key] = value

        category = Category.objects.get(id=category_id)

        sub_category, _ = SubCategory.objects.get_or_create(category=category, name=sub_category_name)
        
        item, _ = Item.objects.get_or_create(
            name=item_name,
            sub_category=sub_category,
            defaults={'brand': item_brand, 'specifications': specifications_dict}
        )
        
        # If they uploaded a photo, attach it to the item
        if catalog_image:
            item.catalog_image = catalog_image
            item.save()

        transaction = InventoryTransaction(
            item=item,
            room=room,
            transaction_type=transaction_type,
            quantity=quantity,
            remarks=remarks
        )
        
        if date_recorded_input:
            transaction.date_recorded = date_recorded_input
            
        transaction.save()

        messages.success(request, f"Successfully logged {quantity} x {item_name} into {room.name}!")
        return redirect('room_ledger', room_id=room.id)

    categories = Category.objects.all()
    context = {
        'room': room,
        'categories': categories,
    }
    return render(request, 'inventory/update_stock.html', context)


# ==========================================
# 3. PROGRESSIVE DISCLOSURE (DRILL-DOWN)
# ==========================================
@login_required
def select_building(request, location_id):
    location = get_object_or_404(Location, id=location_id)
    buildings = Building.objects.filter(location=location)
    
    context = {
        'location': location,
        'options': buildings,
        'step_name': 'Select a Building',
        'next_url_name': 'select_floor' 
    }
    return render(request, 'inventory/spatial_selector.html', context)

@login_required
def select_floor(request, building_id):
    building = get_object_or_404(Building, id=building_id)
    floors = Floor.objects.filter(building=building)
    
    context = {
        'location': building.location,
        'building': building,
        'options': floors,
        'step_name': 'Select a Floor',
        'next_url_name': 'select_room'
    }
    return render(request, 'inventory/spatial_selector.html', context)

@login_required
def select_room(request, floor_id):
    floor = get_object_or_404(Floor, id=floor_id)
    rooms = Room.objects.filter(floor=floor)
    
    context = {
        'location': floor.building.location,
        'building': floor.building,
        'floor': floor,
        'options': rooms,
        'step_name': 'Select a Room',
        'next_url_name': 'room_ledger'
    }
    return render(request, 'inventory/spatial_selector.html', context)

@login_required
def room_ledger(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    transactions = InventoryTransaction.objects.filter(room=room).order_by('-date_recorded')
    
    context = {
        'room': room,
        'location': room.floor.building.location,
        'building': room.floor.building,
        'floor': room.floor,
        'transactions': transactions 
    }
    return render(request, 'inventory/room_ledger.html', context)