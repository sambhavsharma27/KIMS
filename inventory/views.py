import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Q, F, Max, Min
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone  # Added for date handling
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
        transactions = InventoryTransaction.objects.filter(room__floor__building__location=location).order_by(
            '-date_recorded')
        buildings = Building.objects.filter(location=location)
        floors = Floor.objects.filter(building__location=location)
        rooms = Room.objects.filter(floor__building__location=location)
    else:
        transactions = InventoryTransaction.objects.none()
        buildings = floors = rooms = []

    # Filter logic
    b_id = request.GET.get('building')
    f_id = request.GET.get('floor')
    r_id = request.GET.get('room')
    c_id = request.GET.get('category')
    search_name = request.GET.get('search_name')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    math_filters = Q()
    if location: math_filters &= Q(inventorytransaction__room__floor__building__location=location)
    if b_id: math_filters &= Q(inventorytransaction__room__floor__building_id=b_id)
    if f_id: math_filters &= Q(inventorytransaction__room__floor_id=f_id)
    if r_id: math_filters &= Q(inventorytransaction__room_id=r_id)

    # Apply filters to transactions list
    if b_id: transactions = transactions.filter(room__floor__building_id=b_id)
    if f_id: transactions = transactions.filter(room__floor_id=f_id)
    if r_id: transactions = transactions.filter(room_id=r_id)
    if c_id: transactions = transactions.filter(item__category_id=c_id)
    if search_name: transactions = transactions.filter(item__name__icontains=search_name)

    master_inventory = Item.objects.filter(category_id=c_id) if c_id else Item.objects.all()
    if search_name: master_inventory = master_inventory.filter(name__icontains=search_name)

    master_inventory = master_inventory.distinct().annotate(
        total_received=Coalesce(Sum('inventorytransaction__quantity',
                                    filter=math_filters & Q(inventorytransaction__transaction_type='RECEIPT')), 0),
        total_damaged=Coalesce(Sum('inventorytransaction__quantity',
                                   filter=math_filters & Q(inventorytransaction__transaction_type='DAMAGE')), 0),
        total_transferred=Coalesce(Sum('inventorytransaction__quantity',
                                       filter=math_filters & Q(inventorytransaction__transaction_type='TRANSFER')), 0),
    ).annotate(
        current_stock=F('total_received') - F('total_damaged') - F('total_transferred')
    ).filter(Q(total_received__gt=0) | Q(total_damaged__gt=0) | Q(total_transferred__gt=0)).order_by('-current_stock')

    context = {
        'locations': locations, 'current_location': location, 'buildings': buildings,
        'floors': floors, 'rooms': rooms, 'categories': Category.objects.all(),
        'transactions': transactions[:50], 'master_inventory': master_inventory,
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

        # Capture the new quantity, date, remarks, and received_from from the form
        quantity = int(request.POST.get('quantity', 1))
        received_on = request.POST.get('received_on')
        remarks = request.POST.get('remarks', 'Initial stock entry.')
        received_from = request.POST.get('received_from', '').strip().title()
        catalog_image = request.FILES.get('catalog_image')

        # Handle Dynamic Specs (Brand & Colour now come as the first two spec rows)
        keys = request.POST.getlist('spec_keys[]')
        values = request.POST.getlist('spec_values[]')
        specs = {k.strip().title(): v.strip().title() for k, v in zip(keys, values) if k.strip()}

        # Extract Brand and Colour from specs to save in dedicated model fields
        item_brand = specs.pop('Brand', '')
        item_colour = specs.pop('Colour', '')

        new_item = Item.objects.create(
            name=item_name,
            category_id=category_id,
            brand=item_brand,
            colour=item_colour,
            specifications=specs,
            catalog_image=catalog_image
        )

        # Create the initial receipt transaction
        InventoryTransaction.objects.create(
            item=new_item,
            room=room,
            transaction_type='RECEIPT',
            quantity=quantity,
            remarks=remarks,
            received_from=received_from,
            date_recorded=received_on if received_on else timezone.now().date()
        )

        messages.success(request, f"Created {new_item.name} with {quantity} units.")
        return redirect('room_ledger', room_id=room.id)

    return redirect('room_ledger', room_id=room_id)


# ==========================================
# 3. ROOM LEDGER & DRILL DOWN
# ==========================================
@login_required
def room_ledger(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    live_items = Item.objects.filter(inventorytransaction__room=room).distinct().annotate(
        total_received=Coalesce(Sum('inventorytransaction__quantity', filter=Q(inventorytransaction__room=room,
                                                                               inventorytransaction__transaction_type='RECEIPT')),
                                0),
        total_damaged=Coalesce(Sum('inventorytransaction__quantity', filter=Q(inventorytransaction__room=room,
                                                                              inventorytransaction__transaction_type='DAMAGE')),
                               0),
        total_transferred=Coalesce(Sum('inventorytransaction__quantity', filter=Q(inventorytransaction__room=room,
                                                                                  inventorytransaction__transaction_type='TRANSFER')),
                                   0),
        latest_transaction_date=Max('inventorytransaction__date_recorded', filter=Q(inventorytransaction__room=room))
    ).annotate(current_stock=F('total_received') - F('total_damaged') - F('total_transferred')).order_by(
        '-current_stock')

    context = {
        'room': room, 'location': room.floor.building.location, 'building': room.floor.building,
        'floor': room.floor, 'live_items': live_items, 'categories': Category.objects.all(),
        'locations': Location.objects.filter(is_active=True),
    }
    return render(request, 'inventory/room_ledger.html', context)


# ==========================================
# 4. EDIT ITEM INFO
# ==========================================
@login_required
def update_item_info(request, room_id, item_id):
    """View to update item details (Image, Name, Brand, Specs) without stock change."""
    item = get_object_or_404(Item, id=item_id)

    if request.method == 'POST':
        item.name = request.POST.get('item_name').strip().title()
        item.brand = request.POST.get('item_brand', '').strip().title()
        item.model = request.POST.get('item_model', '').strip().title()
        item.colour = request.POST.get('item_colour', '').strip().title()

        # Handle Specifications
        keys = request.POST.getlist('spec_keys[]')
        values = request.POST.getlist('spec_values[]')
        item.specifications = {k.strip().title(): v.strip().title() for k, v in zip(keys, values) if k.strip()}

        # Handle Image Replacement
        if 'catalog_image' in request.FILES:
            item.catalog_image = request.FILES['catalog_image']

        item.save()
        messages.success(request, f"Updated details for {item.name} successfully.")
        return redirect('room_ledger', room_id=room_id)

    return redirect('room_ledger', room_id=room_id)


# ==========================================
# 5. SPATIAL SELECTORS & AJAX UPLOADS
# ==========================================
@login_required
def select_building(request, location_id):
    location = get_object_or_404(Location, id=location_id)
    buildings = Building.objects.filter(location=location)
    return render(request, 'inventory/spatial_selector.html',
                  {'location': location, 'options': buildings, 'step_name': 'Select Building',
                   'next_url_name': 'select_floor'})


@login_required
def select_floor(request, building_id):
    building = get_object_or_404(Building, id=building_id)
    floors = Floor.objects.filter(building=building)
    return render(request, 'inventory/spatial_selector.html',
                  {'location': building.location, 'building': building, 'options': floors, 'step_name': 'Select Floor',
                   'next_url_name': 'select_room'})


@login_required
def select_room(request, floor_id):
    floor = get_object_or_404(Floor, id=floor_id)
    rooms = Room.objects.filter(floor=floor)
    return render(request, 'inventory/spatial_selector.html',
                  {'location': floor.building.location, 'building': floor.building, 'floor': floor, 'options': rooms,
                   'step_name': 'Select Room', 'next_url_name': 'room_ledger'})


@login_required
@require_POST
def upload_spatial_image(request, model_type, object_id):
    MODEL_MAP = {'building': Building, 'floor': Floor, 'room': Room}
    model_class = MODEL_MAP.get(model_type)
    if not model_class: return JsonResponse({'success': False}, status=400)
    obj = get_object_or_404(model_class, id=object_id)
    if request.FILES.get('image'):
        if obj.image: obj.image.delete(save=False)
        obj.image = request.FILES.get('image')
        obj.save()
        return JsonResponse({'success': True, 'image_url': obj.image.url})
    return JsonResponse({'success': False}, status=400)


# ==========================================
# 6. ADD TRANSACTION (Increase/Decrease Stock)
# ==========================================
@login_required
def add_transaction(request, room_id, item_id):
    room = get_object_or_404(Room, id=room_id)
    item = get_object_or_404(Item, id=item_id)

    if request.method == 'POST':
        raw_tx_type = request.POST.get('transaction_type')
        tx_quantity = int(request.POST.get('transaction_quantity', 0))
        tx_date = request.POST.get('transaction_date')

        # 1. Grab the remarks from the mandatory HTML input
        tx_remarks = request.POST.get('remarks')

        # Map HTML form string values to Database choices
        type_mapping = {
            'received': 'RECEIPT',
            'transfer_out': 'TRANSFER',
            'damage_broken': 'DAMAGE'
        }
        db_tx_type = type_mapping.get(raw_tx_type, 'RECEIPT')

        # Create the transaction record. Because of your brilliant annotations
        # in the ledger view, this is all we need to do to update the balance!
        InventoryTransaction.objects.create(
            item=item,
            room=room,
            transaction_type=db_tx_type,
            quantity=tx_quantity,
            date_recorded=tx_date if tx_date else timezone.now().date(),
            remarks=tx_remarks  # 2. Save the captured remarks to the database
        )

        messages.success(request, f"Stock transaction recorded successfully for {item.name}.")

    return redirect('room_ledger', room_id=room_id)