# tests/test_routes.py
# Functional tests for routes (auth, inventory CRUD, transfer, disposal,
# CSV import/export) via the Flask test client.
from io import BytesIO
from datetime import date, datetime, timezone
import pytest
from extensions import db
from models import User, Location, Inventory, ItemLocation, Movement, DisposedItem


# ---------- Auth ----------

def test_login_page_renders(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert b"Login" in r.data or b"login" in r.data


def test_login_requires_credentials(app, client, admin_user):
    r = client.post("/login", data={"username": "admin", "password": "wrong"})
    assert r.status_code == 200  # re-renders login with flash
    # Should not be authenticated
    r2 = client.get("/")
    assert r2.status_code == 302  # redirected to login
    assert "/login" in r2.headers["Location"]


def test_login_success_redirects(app, client, admin_user):
    r = client.post("/login", data={"username": "admin", "password": "adminpass"},
                     follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/")


def test_logout_requires_login(client):
    r = client.get("/logout", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_logout_clears_session(app, client, admin_user):
    client.post("/login", data={"username": "admin", "password": "adminpass"})
    r = client.get("/logout", follow_redirects=False)
    assert r.status_code == 302
    # After logout, accessing protected route redirects to login
    r2 = client.get("/", follow_redirects=False)
    assert "/login" in r2.headers["Location"]


def test_protected_routes_require_login(client):
    for path in ["/", "/add_item", "/edit_items", "/delete_items", "/movements",
                 "/disposed", "/transfer", "/export_csv", "/download_template"]:
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 302, f"{path} did not redirect"
        assert "/login" in r.headers["Location"], f"{path} not redirecting to login"


def test_register_requires_admin(app, client, regular_user):
    # Log in as regular user
    client.post("/login", data={"username": "user1", "password": "userpass"})
    r = client.get("/register", follow_redirects=False)
    # Non-admin is flashed and redirected to index
    assert r.status_code == 302


def test_register_creates_user_as_admin(app, client, admin_user):
    client.post("/login", data={"username": "admin", "password": "adminpass"})
    r = client.post("/register", data={
        "username": "newperson", "password": "pw12345678",
        "confirm_password": "pw12345678",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert User.query.filter_by(username="newperson").first() is not None


def test_register_rejects_duplicate_username(app, client, admin_user):
    client.post("/login", data={"username": "admin", "password": "adminpass"})
    r = client.post("/register", data={
        "username": "admin", "password": "pw12345678",
        "confirm_password": "pw12345678",
    }, follow_redirects=True)
    assert User.query.filter_by(username="admin").count() == 1


# ---------- Lockout ----------

def test_lockout_after_five_failed_attempts(app, client, admin_user):
    for _ in range(5):
        client.post("/login", data={"username": "admin", "password": "wrong"})
    # 6th attempt should be locked
    r = client.post("/login", data={"username": "admin", "password": "adminpass"})
    assert r.status_code == 200
    assert b"locked" in r.data.lower()


def test_successful_login_clears_failed_attempts(app, client, admin_user):
    for _ in range(3):
        client.post("/login", data={"username": "admin", "password": "wrong"})
    from models import LoginAttempt
    assert LoginAttempt.query.filter_by(username="admin", successful=False).count() == 3
    client.post("/login", data={"username": "admin", "password": "adminpass"})
    assert LoginAttempt.query.filter_by(username="admin", successful=False).count() == 0


# ---------- Inventory / Add item ----------

def test_add_item_creates_new_item(logged_in_client, app):
    r = logged_in_client.post("/add_item", data={
        "name": "Chalice", "location": "Sanctuary", "quantity": "5",
        "description": "Silver", "category": "Vessel", "condition": "Good",
        "date_acquired": "2024-01-01", "price_per_item": "10.50",
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        item = Inventory.query.filter_by(name="Chalice").first()
        assert item is not None
        assert item.total_quantity == 5
        assert item.category == "Vessel"


def test_add_item_validates_positive_quantity(logged_in_client, app):
    r = logged_in_client.post("/add_item", data={
        "name": "Bad", "location": "L", "quantity": "0",
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert Inventory.query.filter_by(name="Bad").first() is None


def test_add_item_validates_required_fields(logged_in_client):
    # Missing name
    r = logged_in_client.post("/add_item", data={
        "name": "", "location": "L", "quantity": "5",
    }, follow_redirects=True)
    assert r.status_code == 200


def test_add_stock_to_existing_item_merges(logged_in_client, app):
    with app.app_context():
        item = Inventory(name="Chalice", description="")
        db.session.add(item); db.session.flush()
        loc = Location(name="Sanctuary")
        db.session.add(loc); db.session.flush()
        db.session.add(ItemLocation(item_id=item.id, location_id=loc.id, quantity=3))
        db.session.commit()

    logged_in_client.post("/add_item", data={
        "name": "Chalice", "location": "Sanctuary", "quantity": "2",
        "description": "",
    }, follow_redirects=True)

    with app.app_context():
        il = ItemLocation.query.first()
        assert il.quantity == 5


# ---------- Inventory views ----------

def test_index_only_shows_items_with_stock(logged_in_client, app):
    with app.app_context():
        item1 = Inventory(name="Has", description="")
        item2 = Inventory(name="Empty", description="")
        db.session.add_all([item1, item2]); db.session.flush()
        loc = Location(name="L")
        db.session.add(loc); db.session.flush()
        db.session.add(ItemLocation(item_id=item1.id, location_id=loc.id, quantity=2))
        db.session.commit()

    r = logged_in_client.get("/")
    assert b"Has" in r.data
    assert b"Empty" not in r.data


def test_edit_items_admin_only(app, client, regular_user):
    client.post("/login", data={"username": "user1", "password": "userpass"})
    r = client.get("/edit_items", follow_redirects=False)
    assert r.status_code == 302


def test_delete_items_admin_only(app, client, regular_user):
    client.post("/login", data={"username": "user1", "password": "userpass"})
    r = client.get("/delete_items", follow_redirects=False)
    assert r.status_code == 302


def test_search_filters_results(logged_in_client, app):
    with app.app_context():
        db.session.add_all([
            Inventory(name="Chalice", description="silver"),
            Inventory(name="Hymnal", description="red"),
        ])
        loc = Location(name="L")
        db.session.add(loc); db.session.flush()
        chalice = Inventory.query.filter_by(name="Chalice").first()
        db.session.add(ItemLocation(item_id=chalice.id, location_id=loc.id, quantity=1))
        db.session.commit()

    r = logged_in_client.get("/search?q=chal")
    assert b"Chalice" in r.data
    assert b"Hymnal" not in r.data


def test_search_empty_redirects_to_index(logged_in_client):
    r = logged_in_client.get("/search?q=", follow_redirects=False)
    assert r.status_code == 302


# ---------- Transfer ----------

def _setup_transferable_item(app):
    with app.app_context():
        item = Inventory(name="Chalice", description="")
        db.session.add(item); db.session.flush()
        loc_from = Location(name="Storage")
        loc_to = Location(name="Sanctuary")
        db.session.add_all([loc_from, loc_to]); db.session.flush()
        db.session.add(ItemLocation(item_id=item.id, location_id=loc_from.id, quantity=5))
        db.session.commit()
        return item.id, loc_from.id, loc_to.id


def test_transfer_moves_stock(logged_in_client, app):
    item_id, from_id, to_id = _setup_transferable_item(app)
    r = logged_in_client.post("/transfer", data={
        "item_id": str(item_id),
        "from_location": str(from_id),
        "to_location": "Sanctuary",
        "quantity": "2",
        "responsible": "admin",
    }, follow_redirects=True)
    assert r.status_code == 200

    with app.app_context():
        from_il = ItemLocation.query.filter_by(item_id=item_id, location_id=from_id).first()
        to_il = ItemLocation.query.filter_by(item_id=item_id, location_id=to_id).first()
        assert from_il.quantity == 3
        assert to_il.quantity == 2
        assert Movement.query.count() == 1


def test_transfer_rejects_insufficient_stock(logged_in_client, app):
    item_id, from_id, _ = _setup_transferable_item(app)
    r = logged_in_client.post("/transfer", data={
        "item_id": str(item_id),
        "from_location": str(from_id),
        "to_location": "NewLoc",
        "quantity": "999",
        "responsible": "admin",
    }, follow_redirects=True)
    # Insufficient stock -> flash + redirect to transfer
    with app.app_context():
        assert Movement.query.count() == 0


def test_transfer_rejects_same_source_destination(logged_in_client, app):
    item_id, from_id, _ = _setup_transferable_item(app)
    loc = Location.query.filter_by(id=from_id).first()
    r = logged_in_client.post("/transfer", data={
        "item_id": str(item_id),
        "from_location": str(from_id),
        "to_location": loc.name,
        "quantity": "1",
        "responsible": "admin",
    }, follow_redirects=True)
    with app.app_context():
        assert Movement.query.count() == 0


# ---------- Disposal ----------

def test_dispose_item_records_disposal(logged_in_client, app):
    with app.app_context():
        item = Inventory(name="Chair", description="")
        db.session.add(item); db.session.flush()
        loc = Location(name="Hall")
        db.session.add(loc); db.session.flush()
        db.session.add(ItemLocation(item_id=item.id, location_id=loc.id, quantity=4))
        db.session.commit()
        item_id = item.id
        loc_id = loc.id

    r = logged_in_client.post(f"/dispose_item/{item_id}", data={
        "location": str(loc_id),
        "quantity": "2",
        "reason": "Damaged",
        "date": "2025-01-01",
        "notes": "broken legs",
    }, follow_redirects=True)
    assert r.status_code == 200

    with app.app_context():
        d = DisposedItem.query.first()
        assert d.quantity == 2
        assert d.reason == "Damaged"
        assert d.disposed_by == "admin"
        il = ItemLocation.query.filter_by(item_id=item_id, location_id=loc_id).first()
        assert il.quantity == 2


def test_dispose_item_deletes_zero_stock_location(logged_in_client, app):
    with app.app_context():
        item = Inventory(name="Chair", description="")
        db.session.add(item); db.session.flush()
        loc = Location(name="Hall")
        db.session.add(loc); db.session.flush()
        db.session.add(ItemLocation(item_id=item.id, location_id=loc.id, quantity=1))
        db.session.commit()
        item_id = item.id
        loc_id = loc.id

    logged_in_client.post(f"/dispose_item/{item_id}", data={
        "location": str(loc_id), "quantity": "1",
        "reason": "Lost", "date": "2025-01-01",
    }, follow_redirects=True)

    with app.app_context():
        assert ItemLocation.query.filter_by(item_id=item_id, location_id=loc_id).first() is None


def test_dispose_item_rejects_insufficient_stock(logged_in_client, app):
    with app.app_context():
        item = Inventory(name="Chair", description="")
        db.session.add(item); db.session.flush()
        loc = Location(name="Hall")
        db.session.add(loc); db.session.flush()
        db.session.add(ItemLocation(item_id=item.id, location_id=loc.id, quantity=1))
        db.session.commit()
        item_id = item.id
        loc_id = loc.id

    logged_in_client.post(f"/dispose_item/{item_id}", data={
        "location": str(loc_id), "quantity": "5",
        "reason": "Lost", "date": "2025-01-01",
    }, follow_redirects=True)

    with app.app_context():
        assert DisposedItem.query.count() == 0


# ---------- Delete item ----------

def test_delete_item_requires_confirmation(logged_in_client, app):
    with app.app_context():
        item = Inventory(name="X", description="")
        db.session.add(item); db.session.commit()
        item_id = item.id

    r = logged_in_client.post(f"/delete_item/{item_id}", data={},
                              follow_redirects=True)
    # Without confirmation -> flash, redirected back
    with app.app_context():
        assert Inventory.query.get(item_id) is not None


def test_delete_item_with_confirmation_cascades(logged_in_client, app):
    with app.app_context():
        item = Inventory(name="X", description="")
        db.session.add(item); db.session.flush()
        loc = Location(name="L")
        db.session.add(loc); db.session.flush()
        il = ItemLocation(item_id=item.id, location_id=loc.id, quantity=3)
        db.session.add(il); db.session.commit()
        item_id = item.id
        il_id = il.id

    r = logged_in_client.post(f"/delete_item/{item_id}", data={
        "confirmation": "on",
    }, follow_redirects=True)
    assert r.status_code == 200

    with app.app_context():
        assert db.session.get(Inventory, item_id) is None
        assert db.session.get(ItemLocation, il_id) is None


# ---------- CSV import/export ----------

def test_export_csv_inventory(logged_in_client, app):
    with app.app_context():
        item = Inventory(name="Chalice", description="")
        db.session.add(item); db.session.flush()
        loc = Location(name="Sanctuary")
        db.session.add(loc); db.session.flush()
        db.session.add(ItemLocation(item_id=item.id, location_id=loc.id, quantity=2))
        db.session.commit()

    r = logged_in_client.get("/export_csv?type=inventory")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")
    assert b"Chalice" in r.data


def test_export_csv_all_returns_zip(logged_in_client):
    r = logged_in_client.get("/export_csv?type=all")
    assert r.status_code == 200
    assert r.headers.get("Content-Type") == "application/zip"
    assert r.headers.get("Content-Disposition", "").endswith(".zip")


def test_download_template_inventory(logged_in_client):
    r = logged_in_client.get("/download_template?type=inventory")
    assert r.status_code == 200
    assert b"Name" in r.data
    assert b"Quantity" in r.data


def test_download_template_all_returns_zip(logged_in_client):
    r = logged_in_client.get("/download_template?type=all")
    assert r.status_code == 200
    assert r.headers.get("Content-Type") == "application/zip"


def test_import_csv_inventory(logged_in_client, app):
    csv_content = "Name,Description,Category,Condition,Location,Quantity\nChalice,Silver,Vessel,Good,Sanctuary,3\n"
    data = {
        "context": "current_inventory",
        "csv_file": (BytesIO(csv_content.encode("utf-8-sig")), "test.csv"),
    }
    r = logged_in_client.post("/import_csv", data=data,
                              content_type="multipart/form-data",
                              follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        item = Inventory.query.filter_by(name="Chalice").first()
        assert item is not None
        assert item.total_quantity == 3


def test_import_csv_invalid_context(logged_in_client):
    data = {
        "context": "bogus",
        "csv_file": (BytesIO(b"a,b\n1,2"), "test.csv"),
    }
    r = logged_in_client.post("/import_csv", data=data,
                              content_type="multipart/form-data",
                              follow_redirects=False)
    assert r.status_code == 302  # redirected back


def test_import_csv_no_file(logged_in_client):
    data = {"context": "current_inventory"}
    r = logged_in_client.post("/import_csv", data=data,
                              content_type="multipart/form-data",
                              follow_redirects=False)
    assert r.status_code == 302


# ---------- Error pages ----------

def test_404_page(client):
    r = client.get("/nonexistent-route")
    assert r.status_code == 404