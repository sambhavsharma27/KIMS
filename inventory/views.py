import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Q, F
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Location, Building, Floor, Room, Category, Item, InventoryTransaction

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

    # Catch the filters from the form (Removed sub_category)
    b_id = request.GET.get('building')
    f_id = request.GET.get('floor')
    r_id = request.GET.get('room')
    c_id = request.GET.get('category')
    search_name = request.GET.get('search_name')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Math filters
    math_filters = Q()
    if location: math_filters &= Q(inventorytransaction__room__floor__building__location=location)
    if b_id: math_filters &= Q(inventorytransaction__room__floor__building_id=b_id)
    if f_id: math_filters &= Q(inventorytransaction__room__floor_id=f_id)
    if r_id: math_filters &= Q(inventorytransaction__room_id=r_id)
    if start_date: math_filters &= Q(inventorytransaction__date_recorded__gte=start_date)
    if end_date: math_filters &= Q(inventorytransaction__date_recorded__lte=end_date)

    # Apply filters to transactions
    if b_id: transactions = transactions.filter(room__floor__building_id=b_id)
    if f_id: transactions = transactions.filter(room__floor_id=f_id)
    if r_id: transactions = transactions.filter(room_id=r_id)
    if c_id: transactions = transactions.filter(item__category_id=c_id) # UPDATED
    if search_name: transactions = transactions.filter(item__name__icontains=search_name)
    if start_date: transactions = transactions.filter(date_recorded__gte=start_date)
    if end_date: transactions = transactions.filter(date_recorded__lte=end_date)

    # Apply filters to base items
    item_base_filters = Q()
    if c_id: item_base_filters &= Q(category_id=c_id) # UPDATED
    if search_name: item_base_filters &= Q(name__icontains=search_name)

    # The Math Engine
    master_inventory = Item.objects.filter(item_base_filters).distinct().annotate(
        total_received=Coalesce(Sum('inventorytransaction__quantity', filter=math_filters & Q(inventorytransaction__transaction_type='RECEIPT')), 0),
        total_damaged=Coalesce(Sum('inventorytransaction__quantity', filter=math_filters & Q(inventorytransaction__transaction_type='DAMAGE')), 0),
        total_transferred=Coalesce(Sum('inventorytransaction__quantity', filter=math_filters & Q(inventorytransaction__transaction_type='TRANSFER')), 0),
    ).annotate(
        current_stock=F('total_received') - F('total_damaged') - F('total_transferred')
    ).filter(
        Q(total_received__gt=0) | Q(total_damaged__gt=0) | Q(total_transferred__gt=0)
    ).order_by('-current_stock')

    context = {
        'locations': locations,
        'current_location': location,
        'buildings': buildings,
        'floors': floors,
        'rooms': rooms,
        'categories': Category.objects.all(), # Passed directly to template
        'transactions': transactions[:50], # Keep last 50 to save memory
        'master_inventory': master_inventory,
    }
    return render(request, 'inventory/dashboard.html', context)


# ==========================================
# 2. ATOMIC 'ADD NEW ITEM'
# ==========================================
@login_required
@transaction.atomic
def add_new_item_from_modal_view(request, room_id):
    room = get_object_or_404(Room, id=room_id)

    if request.method == 'POST':
        category_id = request.POST.get('category')
        item_name = request.POST.get('item_name').strip().title()
        item_brand = request.POST.get('item_brand', '').strip().title()
        item_colour = request.POST.get('item_colour', '').strip().title()

        quantity = request.POST.get('quantity', 1)
        date_recorded_input = request.POST.get('date_recorded')
        received_from = request.POST.get('received_from', '').strip().title()
        catalog_image = request.FILES.get('catalog_image')

        spec_keys = request.POST.getlist('spec_keys[]')
        spec_values = request.POST.getlist('spec_values[]')

        specifications_dict = {}
        for key, value in zip(spec_keys, spec_values):
            if key and value:
                specifications_dict[key.strip().title()] = value.strip().title()

        category = Category.objects.get(id=category_id)

        new_item = Item.objects.create(
            name=item_name,
            category=category,
            brand=item_brand,
            colour=item_colour,
            specifications=specifications_dict,
            catalog_image=catalog_image if catalog_image else None
        )

        transaction_record = InventoryTransaction(
            item=new_item,
            room=room,
            transaction_type='RECEIPT',
            quantity=quantity,
            received_from=received_from,
            remarks="Initial stock added during item creation."
        )

        if date_recorded_input:
            transaction_record.date_recorded = date_recorded_input

        transaction_record.save()

        messages.success(request, f"Successfully created {new_item.name} and logged {quantity} as received!")
        return redirect('room_ledger', room_id=room.id)

    return redirect('room_ledger', room_id=room_id)


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
    
    live_items = Item.objects.filter(inventorytransaction__room=room).distinct().annotate(
        total_received=Coalesce(Sum('inventorytransaction__quantity', filter=Q(inventorytransaction__room=room, inventorytransaction__transaction_type='RECEIPT')), 0),
        total_damaged=Coalesce(Sum('inventorytransaction__quantity', filter=Q(inventorytransaction__room=room, inventorytransaction__transaction_type='DAMAGE')), 0),
        total_transferred=Coalesce(Sum('inventorytransaction__quantity', filter=Q(inventorytransaction__room=room, inventorytransaction__transaction_type='TRANSFER')), 0),
    ).annotate(
        current_stock=F('total_received') - F('total_damaged') - F('total_transferred')
    ).order_by('-current_stock')
    
    recent_activity = InventoryTransaction.objects.filter(room=room).order_by('-date_recorded')[:5]
    
    context = {
        'room': room,
        'location': room.floor.building.location,
        'building': room.floor.building,
        'floor': room.floor,
        'live_items': live_items,
        'recent_activity': recent_activity,
        'categories': Category.objects.all(), # Sent over to feed the Add New Item modal!
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

        InventoryTransaction.objects.create(
            item=item,
            room=room,
            transaction_type=transaction_type,
            quantity=quantity,
            remarks=remarks
        )
        
        messages.success(request, f"Quick Update: {quantity}x {item.name} marked as {transaction_type}.")
        return redirect('room_ledger', room_id=room.id)

    return redirect('room_ledger', room_id=room.id)


# ==========================================
# 5. SPATIAL IMAGE UPLOAD (AJAX)
# ==========================================
@login_required
@require_POST
def upload_spatial_image(request, model_type, object_id):
    """Handle image uploads for Building, Floor, and Room cards."""
    MODEL_MAP = {
        'building': Building,
        'floor': Floor,
        'room': Room,
    }

    model_class = MODEL_MAP.get(model_type)
    if not model_class:
        return JsonResponse({'success': False, 'error': 'Invalid type.'}, status=400)

    obj = get_object_or_404(model_class, id=object_id)
    image_file = request.FILES.get('image')

    if not image_file:
        return JsonResponse({'success': False, 'error': 'No image provided.'}, status=400)

    # Delete old image file if replacing
    if obj.image:
        obj.image.delete(save=False)

    obj.image = image_file
    obj.save()

    return JsonResponse({'success': True, 'image_url': obj.image.url})