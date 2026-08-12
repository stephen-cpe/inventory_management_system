# tests/test_utils.py
# Tests for utils.py: location helpers, validators, and CSV row processors
# plus CSV generation/template functions.
from datetime import datetime, timezone
import pytest
from extensions import db
from models import Inventory, Location, ItemLocation, Movement, DisposedItem, User
from utils import (
    get_or_create_location, validate_positive_int, validate_date,
    process_inventory_row, process_movement_row, process_disposed_item_row,
    generate_inventory_csv, generate_movements_csv, generate_disposals_csv,
    generate_inventory_template, generate_movements_template,
    generate_disposals_template, get_inventory_query_with_search,
)


# ---------- get_or_create_location ----------

def test_get_or_create_location_creates_new(app):
    loc = get_or_create_location("sacred altar")
    db.session.commit()
    assert loc.id is not None
    assert loc.name == "Sacred Altar"  # title-cased


def test_get_or_create_location_retrieves_existing(app):
    db.session.add(Location(name="Storage"))
    db.session.commit()
    loc = get_or_create_location("storage")
    assert loc.name == "Storage"
    assert Location.query.count() == 1


def test_get_or_create_location_rejects_empty(app):
    with pytest.raises(ValueError):
        get_or_create_location("   ")


# ---------- validate_positive_int ----------

def test_validate_positive_int_accepts_positive():
    assert validate_positive_int("5") == 5
    assert validate_positive_int("1") == 1


@pytest.mark.parametrize("bad", ["0", "-1", "abc", "", "3.5"])
def test_validate_positive_int_rejects_invalid(bad):
    with pytest.raises(ValueError):
        validate_positive_int(bad)


# ---------- validate_date ----------

def test_validate_date_parses_valid():
    d = validate_date("2025-01-15")
    assert d.year == 2025 and d.month == 1 and d.day == 15
    assert d.tzinfo == timezone.utc


def test_validate_date_rejects_invalid():
    with pytest.raises(ValueError):
        validate_date("01/15/2025")
    with pytest.raises(ValueError):
        validate_date("not-a-date")


# ---------- process_inventory_row ----------

def test_process_inventory_row_creates_new_item_and_stock(app):
    row = {
        "Name": "Chalice", "Location": "Sanctuary", "Quantity": "3",
        "Description": "Silver", "Category": "Vessel", "Condition": "Good",
    }
    process_inventory_row(row)
    db.session.commit()

    item = Inventory.query.filter_by(name="Chalice").first()
    assert item is not None
    assert item.description == "Silver"
    il = ItemLocation.query.filter_by(item_id=item.id).first()
    assert il.quantity == 3


def test_process_inventory_row_adds_to_existing_stock(app):
    item = Inventory(name="Chalice", description="")
    db.session.add(item)
    db.session.flush()
    loc = Location(name="Sanctuary")
    db.session.add(loc)
    db.session.flush()
    db.session.add(ItemLocation(item_id=item.id, location_id=loc.id, quantity=2))
    db.session.commit()

    row = {"Name": "Chalice", "Location": "Sanctuary", "Quantity": "5"}
    process_inventory_row(row)
    db.session.commit()

    il = ItemLocation.query.filter_by(item_id=item.id, location_id=loc.id).first()
    assert il.quantity == 7


# ---------- process_movement_row ----------

def test_process_movement_row_auto_creates_item(app):
    row = {
        "Name": "Pew Bible", "Quantity": "2",
        "MovementDate": "2025-05-01",
        "ResponsiblePerson": "John",
        "FromLocation": "Storage",
        "ToLocation": "Sanctuary",
        "Notes": "Weekly service",
    }
    process_movement_row(row)
    db.session.commit()

    assert Inventory.query.filter_by(name="Pew Bible").first() is not None
    m = Movement.query.first()
    assert m.quantity == 2
    assert m.from_location.name == "Storage"
    assert m.to_location.name == "Sanctuary"
    assert m.responsible_person == "John"


def test_process_movement_row_requires_at_least_one_location(app):
    row = {
        "Name": "Item", "Quantity": "1",
        "MovementDate": "2025-05-01",
        "ResponsiblePerson": "X",
        "FromLocation": "", "ToLocation": "",
    }
    with pytest.raises(ValueError):
        process_movement_row(row)


# ---------- process_disposed_item_row ----------

def test_process_disposed_item_row_auto_creates_item(app):
    user = User(username="admin", is_admin=True)
    user.set_password("pw")
    db.session.add(user)
    db.session.commit()

    row = {
        "Name": "Broken Chair", "Location": "Hall",
        "Quantity": "1", "DisposalDate": "2025-06-01", "Reason": "Damaged",
    }
    process_disposed_item_row(row, user)
    db.session.commit()

    assert Inventory.query.filter_by(name="Broken Chair").first() is not None
    d = DisposedItem.query.first()
    assert d.reason == "Damaged"
    assert d.disposed_by == "admin"


# ---------- CSV generation / templates ----------

def test_generate_inventory_csv_includes_header(app):
    csv_text = generate_inventory_csv()
    assert "Item ID" in csv_text
    assert "Name" in csv_text
    assert "Location" in csv_text


def test_generate_inventory_csv_lists_positive_stock(app):
    item = Inventory(name="Chalice", description="")
    db.session.add(item); db.session.flush()
    loc = Location(name="Sanctuary")
    db.session.add(loc); db.session.flush()
    db.session.add(ItemLocation(item_id=item.id, location_id=loc.id, quantity=4))
    db.session.commit()

    out = generate_inventory_csv()
    assert "Chalice" in out
    assert "Sanctuary" in out


def test_generate_movements_csv_header_and_row(app):
    item = Inventory(name="X", description="")
    db.session.add(item); db.session.flush()
    loc = Location(name="L1")
    db.session.add(loc); db.session.flush()
    m = Movement(item_id=item.id, quantity=2, from_location_id=loc.id,
                 to_location_id=None, movement_date=datetime.now(timezone.utc),
                 responsible_person="John")
    db.session.add(m); db.session.commit()

    out = generate_movements_csv()
    assert "Movement ID" in out
    assert "X" in out
    assert "John" in out


def test_generate_disposals_csv(app):
    out = generate_disposals_csv()
    assert "Disposal ID" in out


def test_templates_have_headers_and_sample(app):
    inv = generate_inventory_template()
    assert "Name" in inv and "Quantity" in inv
    mov = generate_movements_template()
    assert "Name" in mov and "Quantity" in mov
    dis = generate_disposals_template()
    assert "Name" in dis and "Reason" in dis


# ---------- get_inventory_query_with_search ----------

def test_search_query_filters_by_name(app):
    db.session.add_all([
        Inventory(name="Chalice", description=""),
        Inventory(name="Hymnal", description=""),
    ])
    db.session.commit()

    results = get_inventory_query_with_search("chal").all()
    assert len(results) == 1
    assert results[0].name == "Chalice"


def test_search_query_filters_by_category_and_condition(app):
    db.session.add_all([
        Inventory(name="A", description="", category="Vessel", condition="Good"),
        Inventory(name="B", description="", category="Furniture", condition="Poor"),
    ])
    db.session.commit()

    assert len(get_inventory_query_with_search("Vessel").all()) == 1
    assert len(get_inventory_query_with_search("Poor").all()) == 1


def test_search_query_empty_returns_all(app):
    db.session.add_all([
        Inventory(name="A", description=""),
        Inventory(name="B", description=""),
    ])
    db.session.commit()

    assert get_inventory_query_with_search(None).count() == 2
    assert get_inventory_query_with_search("").count() == 2