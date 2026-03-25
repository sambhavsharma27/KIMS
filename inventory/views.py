import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Location, Building, Floor, Room, Category, SubCategory, Item, InventoryTransaction
from django.db.models import Sum, Q, F, Max
from django.db.models.functions import Coalesce


# ==========================================
# 1. THE MASTER DASHBOARD (WITH FILTERS & LIVE MATH)
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
        transactions = InventoryTransaction.objects.filter(room__floor__building__location=location)
        buildings = Building.objects.filter(location=location)
        floors = Floor.objects.filter(building__location=location)
        rooms = Room.objects.filter(floor__building__location=location)
    else:
        transactions = InventoryTransaction.objects.none()
        buildings = floors = rooms = []

    # Catch the filters from the form
    b_id = request.GET.get('building')
    f_id = request.GET.get('floor')
    r_id = request.GET.get('room')
    c_id = request.GET.get('category')
    sc_id = request.GET.get('sub_category')
    search_name = request.GET.get('search_name')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # 1. Build dynamic spatial/date filters for the Math Engine
    math_filters = Q()
    if location: math_filters &= Q(inventorytransaction__room__floor__building__location=location)
    if b_id: math_filters &= Q(inventorytransaction__room__floor__building_id=b_id)
    if f_id: math_filters &= Q(inventorytransaction__room__floor_id=f_id)
    if r_id: math_filters &= Q(inventorytransaction__room_id=r_id)
    if start_date: math_filters &= Q(inventorytransaction__date_recorded__gte=start_date)
    if end_date: math_filters &= Q(inventorytransaction__date_recorded__lte=end_date)

    # 2. Apply existing filters to the raw transactions (Your original code!)
    if b_id: transactions = transactions.filter(room__floor__building_id=b_id)
    if f_id: transactions = transactions.filter(room__floor_id=f_id)
    if r_id: transactions = transactions.filter(room_id=r_id)
    if c_id: transactions = transactions.filter(item__sub_category__category_id=c_id)
    if sc_id: transactions = transactions.filter(item__sub_category_id=sc_id)
    if search_name: transactions = transactions.filter(item__name__icontains=search_name)
    if start_date: transactions = transactions.filter(date_recorded__gte=start_date)
    if end_date: transactions = transactions.filter(date_recorded__lte=end_date)

    # 3. Apply item-specific filters (Category, Search) to the Item query itself
    item_base_filters = Q()
    if c_id: item_base_filters &= Q(sub_category__category_id=c_id)
    if sc_id: item_base_filters &= Q(sub_category_id=sc_id)
    if search_name: item_base_filters &= Q(name__icontains=search_name)

    # 4. THE LIVE MATH ENGINE (Now respecting all your dropdown filters!)
    master_inventory = Item.objects.filter(item_base_filters).distinct().annotate(
        total_received=Coalesce(Sum('inventorytransaction__quantity', filter=math_filters & Q(inventorytransaction__transaction_type='RECEIPT')), 0),
        total_damaged=Coalesce(Sum('inventorytransaction__quantity', filter=math_filters & Q(inventorytransaction__transaction_type='DAMAGE')), 0),
        total_transferred=Coalesce(Sum('inventorytransaction__quantity', filter=math_filters & Q(inventorytransaction__transaction_type='TRANSFER')), 0),
    ).annotate(
        current_stock=F('total_received') - F('total_damaged') - F('total_transferred')
    ).filter(
        # Hide items that have 0 history in the selected building/room
        Q(total_received__gt=0) | Q(total_damaged__gt=0) | Q(total_transferred__gt=0)
    ).order_by('-current_stock')

    context = {
        'locations': locations,
        'current_location': location,
        'buildings': buildings,
        'floors': floors,
        'rooms': rooms,
        'categories': Category.objects.all(),
        'sub_categories': SubCategory.objects.all(),
        'transactions': transactions.order_by('-date_recorded')[:50], # Keep a feed of the last 50 actions
        'master_inventory': master_inventory, # NEW: Passing the math to HTML!
    }
    return render(request, 'inventory/dashboard.html', context)

# ==========================================
# 2. SMART FORM (WITH IMAGE UPLOADS & SANITIZER)
# ==========================================
@login_required
def update_stock_view(request, room_id):
    room = get_object_or_404(Room, id=room_id)

    if request.method == 'POST':
        category_id = request.POST.get('category')
        
        # THE SANITIZER: .strip() removes accidental spaces, .title() capitalizes the first letters!
        sub_category_name = request.POST.get('sub_category_name').strip().title()
        item_name = request.POST.get('item_name').strip().title()
        
        item_brand = request.POST.get('item_brand')
        if item_brand:
            item_brand = item_brand.strip().title()

        transaction_type = request.POST.get('transaction_type')
        quantity = request.POST.get('quantity')
        remarks = request.POST.get('remarks')
        date_recorded_input = request.POST.get('date_recorded') 
        catalog_image = request.FILES.get('catalog_image')

        spec_keys = request.POST.getlist('spec_keys[]')
        spec_values = request.POST.getlist('spec_values[]')
        
        specifications_dict = {}
        for key, value in zip(spec_keys, spec_values):
            if key and value:
                # Sanitize the custom specifications too!
                specifications_dict[key.strip().title()] = value.strip().title()

        category = Category.objects.get(id=category_id)

        # Because we sanitized it, Django will easily recognize if it already exists
        sub_category, _ = SubCategory.objects.get_or_create(category=category, name=sub_category_name)
        
        item, _ = Item.objects.get_or_create(
            name=item_name,
            sub_category=sub_category,
            defaults={'brand': item_brand, 'specifications': specifications_dict}
        )
        
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

    # FOR GET REQUESTS: Send all existing data to feed the "Search-As-You-Type" lists!
    # Check if we are editing an existing item (coming from ledger Edit button)
    edit_item = None
    item_id = request.GET.get('item_id')
    if item_id:
        edit_item = Item.objects.filter(id=item_id).first()

    context = {
        'room': room,
        'categories': Category.objects.all(),
        'sub_categories': SubCategory.objects.all(),
        'items': Item.objects.all(),
        'edit_item': edit_item,
    }
    return render(request, 'inventory/update_stock.html', context)


# ==========================================
# 3. PROGRESSIVE DISCLOSURE (DRILL-DOWN & LEDGER)
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
    
    # THE LIVE MATH ENGINE: 
    # 1. Grab items that belong to this room
    # 2. Calculate the exact sums for Receipts, Damages, and Transfers
    # 3. Coalesce ensures if there are 0 damages, Python uses the number 0 instead of "None"
    live_items = Item.objects.filter(inventorytransaction__room=room).distinct().annotate(
        total_received=Coalesce(Sum('inventorytransaction__quantity', filter=Q(inventorytransaction__room=room, inventorytransaction__transaction_type='RECEIPT')), 0),
        total_damaged=Coalesce(Sum('inventorytransaction__quantity', filter=Q(inventorytransaction__room=room, inventorytransaction__transaction_type='DAMAGE')), 0),
        total_transferred=Coalesce(Sum('inventorytransaction__quantity', filter=Q(inventorytransaction__room=room, inventorytransaction__transaction_type='TRANSFER')), 0),
        # Latest transaction date for this item in this room
        latest_transaction_date=Max('inventorytransaction__date_recorded', filter=Q(inventorytransaction__room=room)),
    ).annotate(
        # Usable stock = Received - Damaged - Transferred
        current_stock=F('total_received') - F('total_damaged') - F('total_transferred'),
    ).order_by('-latest_transaction_date')

    context = {
        'room': room,
        'location': room.floor.building.location,
        'building': room.floor.building,
        'floor': room.floor,
        'live_items': live_items,
    }
    return render(request, 'inventory/room_ledger.html', context)


# ==========================================
# 4. LIGHTNING-FAST QUICK UPDATES
# ==========================================
@login_required
def quick_update_stock(request, room_id, item_id):
    room = get_object_or_404(Room, id=room_id)
    item = get_object_or_404(Item, id=item_id)

    if request.method == 'POST':
        transaction_type = request.POST.get('transaction_type')
        quantity = request.POST.get('quantity')
        remarks = request.POST.get('remarks')

        # Create the new transaction instantly
        InventoryTransaction.objects.create(
            item=item,
            room=room,
            transaction_type=transaction_type,
            quantity=quantity,
            remarks=remarks
        )
        
        messages.success(request, f"Quick Update: {quantity}x {item.name} marked as {transaction_type}.")
        return redirect('room_ledger', room_id=room.id)

    # If someone tries to just visit this URL directly, kick them back to the ledger
    return redirect('room_ledger', room_id=room.id)