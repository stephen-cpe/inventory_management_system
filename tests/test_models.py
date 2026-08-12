# tests/test_models.py
# Unit tests for SQLAlchemy models: hashing, relationships, cascade behavior,
# total_quantity aggregation, and constraint enforcement.
from datetime import date, datetime, timezone
import pytest
from extensions import db
from models import (
    User, Location, Inventory, ItemLocation, Movement, DisposedItem, LoginAttempt
)


# ---------- User ----------

def test_user_password_hashing(app):
    user = User(username="alice", is_admin=False)
    user.set_password("secret123")
    db.session.add(user)
    db.session.commit()

    fetched = User.query.filter_by(username="alice").first()
    assert fetched is not None
    assert fetched.password_hash != "secret123"
    assert fetched.check_password("secret123") is True
    assert fetched.check_password("wrong") is False
    assert fetched.is_admin is False


def test_username_is_unique(app):
    u1 = User(username="bob", is_admin=False)
    u1.set_password("pw1")
    db.session.add(u1)
    db.session.commit()

    u2 = User(username="bob", is_admin=False)
    u2.set_password("pw2")
    db.session.add(u2)
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()


# ---------- Inventory + ItemLocation ----------

def _make_item(name="Chalice", description="", quantity=5, location_name="Sanctuary"):
    item = Inventory(name=name, description=description, category="Vessel",
                     condition="Good", date_acquired=date(2024, 1, 1),
                     price_per_item=10.50)
    db.session.add(item)
    db.session.flush()
    loc = Location(name=location_name)
    db.session.add(loc)
    db.session.flush()
    il = ItemLocation(item_id=item.id, location_id=loc.id, quantity=quantity)
    db.session.add(il)
    db.session.commit()
    return item, loc, il


def test_item_location_relationship_and_total_quantity(app):
    item, loc, il = _make_item(quantity=5)
    assert len(item.locations) == 1
    assert item.locations[0].quantity == 5
    assert item.total_quantity == 5


def test_total_quantity_sums_across_locations(app):
    item = Inventory(name="Hymnal", description="")
    db.session.add(item)
    db.session.flush()
    loc_a = Location(name="Choir")
    loc_b = Location(name="Storage")
    db.session.add_all([loc_a, loc_b])
    db.session.flush()
    db.session.add_all([
        ItemLocation(item_id=item.id, location_id=loc_a.id, quantity=10),
        ItemLocation(item_id=item.id, location_id=loc_b.id, quantity=4),
    ])
    db.session.commit()

    assert item.total_quantity == 14


def test_total_quantity_zero_when_no_stock(app):
    item = Inventory(name="Empty", description="")
    db.session.add(item)
    db.session.commit()
    assert item.total_quantity == 0


def test_preload_total_quantities_caches_value(app):
    item, _, _ = _make_item(name="X", quantity=3, location_name="L1")
    item2, _, _ = _make_item(name="Y", quantity=7, location_name="L2")
    items = Inventory.preload_total_quantities([item, item2])
    assert items[0].total_quantity_cached == 3
    assert items[1].total_quantity_cached == 7


def test_itemlocation_quantity_non_negative_constraint(app):
    item, loc, _ = _make_item(quantity=1)
    bad = ItemLocation(item_id=item.id, location_id=loc.id, quantity=-1)
    db.session.add(bad)
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()


def test_itemlocation_unique_item_location_pair(app):
    item, loc, _ = _make_item(quantity=1)
    dup = ItemLocation(item_id=item.id, location_id=loc.id, quantity=2)
    db.session.add(dup)
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()


# ---------- Movement ----------

def test_movement_requires_at_least_one_location(app):
    item, _, _ = _make_item(quantity=1)
    m = Movement(item_id=item.id, quantity=1, from_location_id=None,
                 to_location_id=None, movement_date=datetime.now(timezone.utc))
    db.session.add(m)
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()


def test_movement_quantity_must_be_positive(app):
    item, loc, _ = _make_item(quantity=2)
    m = Movement(item_id=item.id, quantity=0, from_location_id=loc.id,
                 to_location_id=None, movement_date=datetime.now(timezone.utc))
    db.session.add(m)
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()


def test_movement_cascade_delete_with_item(app):
    item, loc, _ = _make_item(quantity=2)
    m = Movement(item_id=item.id, quantity=1, from_location_id=loc.id,
                 to_location_id=None, movement_date=datetime.now(timezone.utc))
    db.session.add(m)
    db.session.commit()
    movement_id = m.id
    item_id = item.id

    db.session.delete(item)
    db.session.commit()

    assert db.session.get(Movement, movement_id) is None
    assert db.session.get(Inventory, item_id) is None


# ---------- DisposedItem ----------

def test_disposed_item_quantity_must_be_positive(app):
    item, loc, _ = _make_item(quantity=2)
    d = DisposedItem(item_id=item.id, location_id=loc.id, quantity=0,
                     reason="lost", disposed_date=date.today(),
                     disposed_by="admin")
    db.session.add(d)
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()


def test_disposed_item_cascade_delete_with_item(app):
    item, loc, _ = _make_item(quantity=2)
    d = DisposedItem(item_id=item.id, location_id=loc.id, quantity=1,
                     reason="damaged", disposed_date=date.today(),
                     disposed_by="admin")
    db.session.add(d)
    db.session.commit()
    disposal_id = d.id

    db.session.delete(item)
    db.session.commit()
    assert db.session.get(DisposedItem, disposal_id) is None


# ---------- Location ----------

def test_location_name_unique(app):
    db.session.add(Location(name="Altar"))
    db.session.commit()
    db.session.add(Location(name="Altar"))
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()


# ---------- LoginAttempt ----------

def test_login_attempt_recorded(app):
    a = LoginAttempt(username="someone", ip_address="127.0.0.1", successful=False)
    db.session.add(a)
    db.session.commit()
    assert LoginAttempt.query.filter_by(username="someone").count() == 1