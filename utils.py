from extensions import db
from models import User, Inventory, Location, ItemLocation, Movement, DisposedItem
from flask import current_app
from datetime import datetime, timezone
import csv
from io import StringIO

# --- Helper Functions ---

def get_or_create_location(name):
    """
    Retrieves a location by name or creates a new one if it doesn't exist.
    Adds the new location to the database session and flushes to assign an ID.
    """
    normalized_name = name.strip().title()
    if not normalized_name:
        raise ValueError("Location name cannot be empty.")
    location = Location.query.filter_by(name=normalized_name).first()
    if not location:
        current_app.logger.info(f"Creating new location: {normalized_name}")
        location = Location(name=normalized_name)
        db.session.add(location)
        db.session.flush()  # Assign ID
    return location

def validate_positive_int(value):
    """
    Validates that the input is a positive integer.
    Raises ValueError if the input is invalid or non-positive.
    """
    try:
        num = int(value)
        if num <= 0:
            raise ValueError
        return num
    except ValueError:
        raise ValueError(f"Invalid quantity value: {value}")

def validate_date(date_str):
    """
    Validates and parses a date string in 'YYYY-MM-DD' format.
    Returns a timezone-aware datetime object.
    """
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")

# --- CSV Processing Functions ---

def process_inventory_row(row):
    """
    Processes a single row from an inventory CSV import.
    Creates or updates inventory items and their locations.
    """
    item_name = row['Name'].strip()
    location_name = row['Location'].strip()
    quantity = validate_positive_int(row['Quantity'])
    item = Inventory.query.filter_by(name=item_name).first()
    if not item:
        item = Inventory(
            name=item_name,
            description=row.get('Description', '').strip(),
            category=row.get('Category', 'Uncategorized').strip(),
            condition=row.get('Condition', 'Unknown').strip()
        )
        db.session.add(item)
        db.session.flush()
    location = get_or_create_location(location_name)
    item_loc = ItemLocation.query.filter_by(item_id=item.id, location_id=location.id).first()
    if item_loc:
        item_loc.quantity += quantity
    else:
        item_loc = ItemLocation(item_id=item.id, location_id=location.id, quantity=quantity)
        db.session.add(item_loc)

def process_movement_row(row):
    """
    Processes a single row from a movement CSV import.
    Creates movement records and handles item creation if necessary.
    """
    item_name = row['Name'].strip()
    item = Inventory.query.filter_by(name=item_name).first()
    if not item:
        item = Inventory(name=item_name, description="Auto-created from movement import")
        db.session.add(item)
        db.session.flush()
        current_app.logger.info(f"Created new item during movement import: {item_name}")
    quantity = validate_positive_int(row['Quantity'])
    movement_date = validate_date(row['MovementDate'])
    from_loc_name = row.get('FromLocation', '').strip()
    to_loc_name = row.get('ToLocation', '').strip()
    from_loc = get_or_create_location(from_loc_name) if from_loc_name else None
    to_loc = get_or_create_location(to_loc_name) if to_loc_name else None
    if not from_loc and not to_loc:
        raise ValueError("Must specify at least one location (FromLocation or ToLocation)")
    movement = Movement(
        item_id=item.id,
        quantity=quantity,
        from_location_id=from_loc.id if from_loc else None,
        to_location_id=to_loc.id if to_loc else None,
        movement_date=movement_date,
        responsible_person=row['ResponsiblePerson'].strip(),
        notes=row.get('Notes', '').strip()
    )
    db.session.add(movement)

def process_disposed_item_row(row, current_user):
    """
    Processes a single row from a disposed items CSV import.
    Creates disposal records and handles item creation if necessary.
    """
    item_name = row['Name'].strip()
    item = Inventory.query.filter_by(name=item_name).first()
    if not item:
        item = Inventory(name=item_name)
        db.session.add(item)
        db.session.flush()
    location_name = row['Location'].strip()
    location = get_or_create_location(location_name)
    disposal = DisposedItem(
        item_id=item.id,
        location_id=location.id,
        quantity=validate_positive_int(row['Quantity']),
        disposed_date=validate_date(row['DisposalDate']),
        reason=row['Reason'].strip(),
        disposed_by=current_user.username,
        notes=row.get('Notes', '').strip()
    )
    db.session.add(disposal)

# --- CSV Generation Functions ---

def generate_inventory_csv():
    """
    Generates a CSV string of the current inventory with positive quantities.
    """
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Item ID', 'Name', 'Description', 'Category', 'Condition', 'Location', 'Quantity'])
    items = Inventory.query.options(
        db.joinedload(Inventory.locations).joinedload(ItemLocation.location)
    ).filter(
        Inventory.locations.any(ItemLocation.quantity > 0)
    ).all()
    for item in items:
        for loc in item.locations:
            if loc.quantity > 0:
                writer.writerow([
                    item.id,
                    item.name,
                    item.description,
                    item.category,
                    item.condition,
                    loc.location.name,
                    loc.quantity
                ])
    return output.getvalue()

def generate_movements_csv():
    """
    Generates a CSV string of the movement history.
    """
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Movement ID', 'Item', 'Quantity', 'From Location', 'To Location', 'Date', 'Responsible Person'])
    movements = Movement.query.options(
        db.joinedload(Movement.item),
        db.joinedload(Movement.from_location),
        db.joinedload(Movement.to_location)
    ).order_by(Movement.movement_date.desc()).all()
    for move in movements:
        writer.writerow([
            move.id,
            move.item.name,
            move.quantity,
            move.from_location.name if move.from_location else 'N/A',
            move.to_location.name if move.to_location else 'N/A',
            move.movement_date.strftime('%Y-%m-%d %H:%M'),
            move.responsible_person
        ])
    return output.getvalue()

def generate_disposals_csv():
    """
    Generates a CSV string of the disposed items.
    """
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Disposal ID', 'Item', 'Location', 'Quantity', 'Reason', 'Disposal Date', 'Disposed By', 'Notes'])
    disposals = DisposedItem.query.options(
        db.joinedload(DisposedItem.item),
        db.joinedload(DisposedItem.location)
    ).order_by(DisposedItem.disposed_date.desc()).all()
    for disposal in disposals:
        writer.writerow([
            disposal.id,
            disposal.item.name,
            disposal.location.name,
            disposal.quantity,
            disposal.reason,
            disposal.disposed_date.strftime('%Y-%m-%d'),
            disposal.disposed_by,
            disposal.notes
        ])
    return output.getvalue()

# --- Template Generation Functions ---

def generate_inventory_template():
    """
    Generates a CSV template for inventory import.
    """
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Location', 'Quantity', 'Description', 'Category', 'Condition'])
    writer.writerow(['Altar Candle', 'Sacristy', 10, 'Beeswax candles, 12" height', 'Liturgical', 'New'])
    return output.getvalue()

def generate_movements_template():
    """
    Generates a CSV template for movement import.
    """
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Quantity', 'MovementDate', 'ResponsiblePerson', 'FromLocation', 'ToLocation', 'Notes'])
    writer.writerow(['Communion Chalice', 2, '2025-05-01', 'John Doe', 'Storage Room', 'Main Church', 'Weekly service stock'])
    return output.getvalue()

def generate_disposals_template():
    """
    Generates a CSV template for disposed items import.
    """
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Location', 'Quantity', 'DisposalDate', 'Reason'])
    writer.writerow(['Damaged Chair', 'Sanctuary', 1, '2025-05-01', 'Broken legs'])
    return output.getvalue()