# -*- coding: utf-8 -*-
# Third-party Imports
from flask import (
    render_template, request, send_file, redirect, url_for, flash, abort,
    current_app
)
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
from sqlalchemy import cast, String
from io import StringIO, BytesIO
import csv
import zipfile
from datetime import datetime, timezone, timedelta
from forms import ChangePasswordForm

# Local Imports
from extensions import db
from models import User, Inventory, Location, ItemLocation, Movement, DisposedItem, LoginAttempt
from utils import (
    get_or_create_location, process_inventory_row, process_movement_row,
    process_disposed_item_row, generate_inventory_csv, generate_movements_csv,
    generate_disposals_csv, generate_inventory_template, generate_movements_template,
    generate_disposals_template, get_inventory_query_with_search
)
from config import PAGINATION_SETTINGS
from app import app, login_manager

# ---------- AUTHENTICATION ROUTES ---------- #

@login_manager.user_loader
def load_user(user_id):
    """Loads user for Flask-Login."""
    return db.session.get(User, int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login with attempt limitation."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        # Check if user is locked out
        twelve_hours_ago = datetime.now(timezone.utc) - timedelta(hours=12)
        recent_failed_attempts = LoginAttempt.query.filter(
            LoginAttempt.username == username,
            LoginAttempt.successful == False,
            LoginAttempt.attempt_time >= twelve_hours_ago
        ).count()
        
        if recent_failed_attempts >= 5:
            flash('Account locked due to too many failed login attempts. Please try again later.', 'danger')
            current_app.logger.warning(f"Login attempt for locked account: '{username}' from {request.remote_addr}")
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        successful_login = False

        if user and user.check_password(password):
            login_user(user, remember=remember)
            successful_login = True
            current_app.logger.info(f"User '{username}' logged in successfully.")
            
            # Clear any previous failed attempts
            LoginAttempt.query.filter_by(username=username, successful=False).delete()
            db.session.commit()
            
            next_page = request.args.get('next')
            if next_page and not next_page.startswith('/'):
                next_page = url_for('index')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
            current_app.logger.warning(f"Failed login attempt for username: '{username}' from {request.remote_addr}")
        
        # Record the login attempt
        login_attempt = LoginAttempt(
            username=username,
            ip_address=request.remote_addr,
            successful=successful_login
        )
        db.session.add(login_attempt)
        db.session.commit()

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logs the current user out."""
    user_name = current_user.username
    logout_user()
    flash('You have been logged out.', 'success')
    current_app.logger.info(f"User '{user_name}' logged out.")
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    """Handles new user registration (Admin only)."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    # Rest of the function remains the same
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        is_admin = 'is_admin' in request.form

        if not username:
            flash('Username cannot be empty.', 'danger')
        elif not password:
            flash('Password cannot be empty.', 'danger')
        elif password != confirm_password:
            flash('Passwords do not match.', 'danger')
        elif User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose another.', 'danger')
        else:
            new_user = User(username=username, is_admin=is_admin)
            new_user.set_password(password)
            db.session.add(new_user)
            try:
                db.session.commit()
                flash(f'User "{username}" created successfully.', 'success')
                current_app.logger.info(f"Admin '{current_user.username}' created user '{username}' (admin={is_admin}).")
                return redirect(url_for('index'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating user: {str(e)}', 'danger')
                current_app.logger.error(f"DB error creating user '{username}': {e}", exc_info=True)

        return render_template('register.html', username=username, is_admin=is_admin)

    return render_template('register.html')

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Allows a user to change their password."""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        current_password = form.current_password.data
        new_password = form.new_password.data
        
        # Verify current password
        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'danger')
            return render_template('change_password.html', form=form)
        
        try:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password changed successfully.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error changing password: {str(e)}', 'danger')
            current_app.logger.error(f"Error changing password for user '{current_user.username}': {e}", exc_info=True)
            return render_template('change_password.html', form=form)
    
    return render_template('change_password.html', form=form)

# ---------- INVENTORY ROUTES ---------- #

@app.route('/')
@login_required
def index():
    """Displays the main inventory list (items with stock > 0)."""
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '').strip()
    
    # Subquery to efficiently find items with stock > 0
    items_with_stock_subq = (
        db.session.query(ItemLocation.item_id)
        .filter(ItemLocation.quantity > 0)
        .distinct()
        .subquery()
    )
    
    # Main query with pagination
    query = Inventory.query.join(
        items_with_stock_subq,
        Inventory.id == items_with_stock_subq.c.item_id
    )
    
    if search_query:
        search_term = f'%{search_query}%'
        query = query.filter(
            db.or_(
                Inventory.name.ilike(search_term),
                Inventory.description.ilike(search_term)
            )
        )
    
    # Subquery to calculate total quantities efficiently
    total_quantity_subq = (
        db.session.query(
            ItemLocation.item_id,
            db.func.sum(ItemLocation.quantity).label('total_qty')
        )
        .group_by(ItemLocation.item_id)
        .subquery()
    )
    
    # Join with the subquery to get total quantity efficiently
    query = query.outerjoin(
        total_quantity_subq,
        Inventory.id == total_quantity_subq.c.item_id
    ).add_columns(total_quantity_subq.c.total_qty)
    
    # Paginate the results
    inventory_paginated = query.order_by(Inventory.name).paginate(
        page=page,
        per_page=PAGINATION_SETTINGS['INVENTORY_PER_PAGE'],
        error_out=False
    )
    
    # Transform to include total_quantity in the item objects
    inventory_items = []
    for item, total_qty in inventory_paginated.items:
        item.total_quantity_cached = total_qty or 0
        inventory_items.append(item)
    
    # Create a paginated result object similar to the one we defined in the model
    paginated_result = type('PaginatedResult', (), {
        'items': inventory_items,
        'page': inventory_paginated.page,
        'pages': inventory_paginated.pages,
        'total': inventory_paginated.total,
        'has_next': inventory_paginated.has_next,
        'has_prev': inventory_paginated.has_prev
    })()
    
    return render_template('index.html', 
                          inventory=paginated_result.items,
                          pagination=paginated_result,
                          search_query=search_query)

@app.route('/add_item', methods=['GET', 'POST'])
@login_required
def add_item():
    """Adds a new item or adds stock to an existing item/location."""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            location_name = request.form.get('location', '').strip()
            quantity_str = request.form.get('quantity', '').strip()
            description = request.form.get('description', '').strip()
            category = request.form.get('category', 'Uncategorized').strip()
            condition = request.form.get('condition', 'Unknown').strip()
            date_acquired_str = request.form.get('date_acquired', '').strip()  # New field
            price_per_item_str = request.form.get('price_per_item', '0.00').strip()  # New field

            if not name:
                raise ValueError("Item name is required.")
            if not location_name:
                raise ValueError("Location is required.")
            if not quantity_str:
                raise ValueError("Quantity is required.")

            quantity = int(quantity_str)
            if quantity <= 0:
                raise ValueError("Quantity must be a positive number.")
            
            # Process date_acquired
            date_acquired = None
            if date_acquired_str:
                try:
                    date_acquired = datetime.strptime(date_acquired_str, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError("Invalid date format. Use YYYY-MM-DD.")
            
            # Process price_per_item
            try:
                price_per_item = float(price_per_item_str) if price_per_item_str else 0.00
            except ValueError:
                raise ValueError("Invalid price format. Use a number like 10.50.")

            location = get_or_create_location(location_name)
            item = Inventory.query.filter_by(name=name, description=description).first()

            if not item:
                item = Inventory(
                    name=name, description=description,
                    category=category, condition=condition,
                    date_acquired=date_acquired, price_per_item=price_per_item  # New fields
                )
                db.session.add(item)
                db.session.flush()
                item_loc = ItemLocation(item_id=item.id, location_id=location.id, quantity=quantity)
                db.session.add(item_loc)
                flash('New item added successfully!', 'success')
            else:
                item_loc = ItemLocation.query.filter_by(item_id=item.id, location_id=location.id).first()
                if item_loc:
                    item_loc.quantity += quantity
                    flash('Stock quantity updated successfully.', 'success')
                else:
                    item_loc = ItemLocation(item_id=item.id, location_id=location.id, quantity=quantity)
                    db.session.add(item_loc)
                    flash('Existing item added to new location.', 'success')

            db.session.commit()
            return redirect(url_for('index'))

        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An unexpected error occurred: {str(e)}', 'danger')
            current_app.logger.error(f'Error adding/updating item: {e}', exc_info=True)

        categories = [c[0] for c in db.session.query(Inventory.category.distinct()).all() if c[0]]
        conditions = [c[0] for c in db.session.query(Inventory.condition.distinct()).all() if c[0]]
        locations = Location.query.order_by(Location.name).all()
        return render_template('add_item.html',
                               categories=categories, conditions=conditions, locations=locations,
                               form_data=request.form)

    categories = [c[0] for c in db.session.query(Inventory.category.distinct()).all() if c[0]]
    conditions = [c[0] for c in db.session.query(Inventory.condition.distinct()).all() if c[0]]
    locations = Location.query.order_by(Location.name).all()
    return render_template('add_item.html',
                           categories=categories,
                           conditions=conditions,
                           locations=locations,
                           active_page='add_item')


@app.route('/edit_items')
@login_required
def edit_items():
    """Displays all inventory items for editing, including items with zero stock."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '').strip()
    
    # Use the new method for paginated results with total quantity calculation
    paginated_result = Inventory.get_paginated_with_total_quantity(
        page=page,
        per_page=PAGINATION_SETTINGS['EDIT_ITEMS_PER_PAGE'],
        search_query=search_query
    )
    
    return render_template('edit_items.html',
                         inventory=paginated_result.items,
                         pagination=paginated_result,
                         search_query=search_query,
                         active_page='edit_items')
                         

@app.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    """Edits inventory item details including all stock locations and quantities."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
        
    item = Inventory.query.options(
        db.joinedload(Inventory.locations).joinedload(ItemLocation.location)
    ).get_or_404(item_id)
    
    locations = Location.query.order_by(Location.name).all()
    categories = db.session.query(Inventory.category.distinct()).all()
    conditions = db.session.query(Inventory.condition.distinct()).all()

    if request.method == 'POST':
        try:
            # Process core item data
            item.name = request.form.get('name', '').strip()
            item.description = request.form.get('description', '').strip()
            item.category = request.form.get('category', 'Uncategorized').strip()
            item.condition = request.form.get('condition', 'Unknown').strip()
            
            # Process date_acquired
            date_acquired_str = request.form.get('date_acquired', '').strip()
            if date_acquired_str:
                try:
                    item.date_acquired = datetime.strptime(date_acquired_str, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError("Invalid date format. Use YYYY-MM-DD.")
            else:
                item.date_acquired = None
            
            # Process price_per_item
            price_per_item_str = request.form.get('price_per_item', '0.00').strip()
            try:
                item.price_per_item = float(price_per_item_str) if price_per_item_str else 0.00
            except ValueError:
                raise ValueError("Invalid price format. Use a number like 10.50.")

            if not item.name:
                raise ValueError("Item name cannot be empty.")

            # Process updates for existing locations
            item_loc_ids = request.form.getlist('item_location_id')
            quantities = request.form.getlist('quantity')
            location_names = request.form.getlist('location_name')
            
            for i, loc_id in enumerate(item_loc_ids):
                item_loc = db.session.get(ItemLocation, int(loc_id))
                if not (item_loc and item_loc.item_id == item.id):
                    continue

                new_quantity = int(quantities[i])
                new_location_name = location_names[i].strip()

                if not new_location_name:
                    raise ValueError("Location name cannot be empty.")

                # If quantity is 0, delete the record
                if new_quantity <= 0:
                    db.session.delete(item_loc)
                    continue
                
                # Update quantity
                item_loc.quantity = new_quantity
                
                # Check if location name has changed
                if item_loc.location.name != new_location_name:
                    new_location_obj = get_or_create_location(new_location_name)
                    
                    # Check if item already has stock at the new location
                    target_loc = ItemLocation.query.filter_by(
                        item_id=item.id,
                        location_id=new_location_obj.id
                    ).first()

                    if target_loc:
                        # Merge quantities and delete old record
                        target_loc.quantity += new_quantity
                        db.session.delete(item_loc)
                    else:
                        # Re-assign the location
                        item_loc.location_id = new_location_obj.id

            # Handle adding to a new location
            new_location_name = request.form.get('new_location', '').strip()
            new_quantity_str = request.form.get('new_quantity', '').strip()

            if new_location_name and new_quantity_str:
                new_quantity = int(new_quantity_str)
                if new_quantity > 0:
                    location = get_or_create_location(new_location_name)
                    existing_loc = ItemLocation.query.filter_by(item_id=item.id, location_id=location.id).first()
                    if existing_loc:
                        existing_loc.quantity += new_quantity
                    else:
                        new_item_loc = ItemLocation(item_id=item.id, location_id=location.id, quantity=new_quantity)
                        db.session.add(new_item_loc)
                else:
                    raise ValueError("New quantity must be a positive number.")

            db.session.commit()
            flash('Item updated successfully!', 'success')
            return redirect(url_for('edit_items'))

        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
            current_app.logger.error(f'Error editing item {item_id}: {e}', exc_info=True)
    
    return render_template('edit_item.html',
                         item=item,
                         locations=locations,
                         categories=[c[0] for c in categories if c[0]],
                         conditions=[c[0] for c in conditions if c[0]])

@app.route('/delete_items')
@login_required
def delete_items():
    """Displays all inventory items for deletion."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '').strip()
    
    # Use the new method for paginated results with total quantity calculation
    paginated_result = Inventory.get_paginated_with_total_quantity(
        page=page,
        per_page=PAGINATION_SETTINGS['DELETE_ITEMS_PER_PAGE'],
        search_query=search_query
    )
    
    categories = [c[0] for c in db.session.query(Inventory.category.distinct()).all() if c[0]]
    conditions = [c[0] for c in db.session.query(Inventory.condition.distinct()).all() if c[0]]
    locations = [l.name for l in Location.query.order_by(Location.name).all()]

    return render_template('delete_items.html',
                         inventory=paginated_result.items,
                         pagination=paginated_result,
                         search_query=search_query,
                         categories=categories,
                         conditions=conditions,
                         locations=locations,
                         active_page="delete_items")

@app.route('/delete_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def delete_item(item_id):
    """Handles item deletion with confirmation."""
    item = Inventory.query.get_or_404(item_id)
    
    if request.method == 'POST':
        # Server-side confirmation check
        if not request.form.get('confirmation'):
            flash('Deletion confirmation required', 'danger')
            return redirect(url_for('delete_item', item_id=item_id))
            
        try:
            # Delete related records first to avoid foreign key constraint issues
            # This is needed because SQLite doesn't support ON DELETE CASCADE properly
            DisposedItem.query.filter_by(item_id=item.id).delete(synchronize_session=False)
            Movement.query.filter_by(item_id=item.id).delete(synchronize_session=False)
            ItemLocation.query.filter_by(item_id=item.id).delete(synchronize_session=False)
            
            # Now delete the item
            db.session.delete(item)
            db.session.commit()
            flash(f'Item "{item.name}" deleted successfully!', 'success')
            return redirect(url_for('delete_items'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting item: {str(e)}', 'danger')
            current_app.logger.error(f'Error deleting item {item_id}: {e}', exc_info=True)
            return redirect(url_for('delete_items'))

    return render_template('delete_item.html', item=item)


@app.route('/dispose_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def dispose_item(item_id):
    """Records the disposal of a certain quantity of an item from a location."""
    item = Inventory.query.options(
        db.joinedload(Inventory.locations).joinedload(ItemLocation.location)
    ).get_or_404(item_id)
    
    # Cache the total quantity to avoid N+1 issues in templates
    item.total_quantity_cached = item.total_quantity
    
    locations_data = db.session.query(Location, ItemLocation.quantity).join(ItemLocation, Location.id == ItemLocation.location_id).filter(ItemLocation.item_id == item.id, ItemLocation.quantity > 0).order_by(Location.name).all()

    if request.method == 'POST':
        try:
            location_id = int(request.form.get('location'))
            quantity = int(request.form.get('quantity'))
            if quantity <= 0:
                raise ValueError("Quantity must be positive.")
            item_location = ItemLocation.query.filter_by(item_id=item.id, location_id=location_id).first()
            if not item_location or item_location.quantity < quantity:
                raise ValueError("Insufficient stock at the selected location.")
            disposal_record = DisposedItem(
                item_id=item.id, location_id=location_id, quantity=quantity,
                reason=request.form.get('reason', '').strip(),
                disposed_date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date(),
                disposed_by=current_user.username,
                notes=request.form.get('notes', '').strip()
            )
            db.session.add(disposal_record)
            item_location.quantity -= quantity
            if item_location.quantity == 0:
                db.session.delete(item_location)
            db.session.commit()
            flash('Disposal recorded successfully!', 'success')
            return redirect(url_for('disposed_inventory'))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An unexpected error occurred during disposal: {str(e)}', 'danger')
            current_app.logger.error(f'Error processing disposal for item {item_id}: {e}', exc_info=True)

    if not locations_data and request.method == 'GET':
        flash('This item has no stock available for disposal.', 'warning')
        return redirect(url_for('index'))

    return render_template('dispose_form.html',
                           item=item,
                           locations_data=locations_data,
                           date_today=datetime.now().date().isoformat())

@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    """Handle stock transfers between locations"""
    items = Inventory.query.options(
        db.joinedload(Inventory.locations).joinedload(ItemLocation.location)
        ).filter(Inventory.locations.any(ItemLocation.quantity > 0)
        ).order_by(Inventory.name).all()
    
    # Preload total quantities to avoid N+1 issues when rendering templates
    items = Inventory.preload_total_quantities(items)
    
    all_locations = Location.query.order_by(Location.name).all()
    
    if request.method == 'POST':
        try:
            # Validate required fields
            item_id = int(request.form.get('item_id', 0))
            from_location_id = int(request.form.get('from_location', 0))
            to_location_name = request.form.get('to_location', '').strip()  # Changed from ID to name
            quantity = int(request.form.get('quantity', 0))
            responsible = request.form.get('responsible', current_user.username).strip()
            
            if not all([item_id, from_location_id, to_location_name, quantity]):
                raise ValueError("All fields are required")
            
            if quantity <= 0:
                raise ValueError("Quantity must be positive")

            # Find source stock
            source = ItemLocation.query.filter_by(
                item_id=item_id,
                location_id=from_location_id
            ).first()
            
            if not source or source.quantity < quantity:
                raise ValueError("Insufficient stock in source location")

            # Get or create destination location
            to_location = get_or_create_location(to_location_name)
            
            # Check if source and destination are the same
            if from_location_id == to_location.id:
                raise ValueError("Source and destination locations must be different")

            # Find/Create destination stock
            destination = ItemLocation.query.filter_by(
                item_id=item_id,
                location_id=to_location.id
            ).first()
            
            if not destination:
                destination = ItemLocation(
                    item_id=item_id,
                    location_id=to_location.id,
                    quantity=0
                )
                db.session.add(destination)

            # Perform transfer
            source.quantity -= quantity
            destination.quantity += quantity

            # Record movement
            movement = Movement(
                item_id=item_id,
                quantity=quantity,
                from_location_id=from_location_id,
                to_location_id=to_location.id,
                movement_date=datetime.now(timezone.utc),
                responsible_person=responsible
            )
            db.session.add(movement)
            
            db.session.commit()
            flash("Transfer completed successfully", "success")
            return redirect(url_for('movements'))

        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
            return redirect(url_for('transfer'))
        except Exception as e:
            db.session.rollback()
            flash("An error occurred during transfer", "danger")
            current_app.logger.error(f"Transfer error: {str(e)}", exc_info=True)
            return redirect(url_for('transfer'))

    # GET request handling
    item_id = request.args.get('item_id', type=int)
    selected_item = next((i for i in items if i.id == item_id), None)
    
    available_locations = []
    if selected_item:
        available_locations = [
            (il.location, il.quantity)
            for il in selected_item.locations
            if il.quantity > 0
        ]

    return render_template('transfer.html',
        items=items,
        all_locations=all_locations,
        selected_item=selected_item,
        available_locations=available_locations,
        date_today=datetime.now(timezone.utc).date().isoformat())

# ---------- CSV HANDLING ---------- #

@app.route('/import_csv', methods=['POST'])
@login_required
def import_csv():
    """Handles CSV imports for different inventory contexts."""
    context = request.form.get('context', '').lower()
    if context not in ['current_inventory', 'movement_tracker', 'disposed_items']:
        flash('Invalid import context specified', 'danger')
        return redirect(request.referrer)

    if 'csv_file' not in request.files or not request.files['csv_file'].filename:
        flash('No file uploaded', 'warning')
        return redirect(request.referrer)

    file = request.files['csv_file']
    try:
        stream = StringIO(file.read().decode('utf-8-sig'))
        csv_reader = csv.DictReader(stream)
        for row in csv_reader:
            if context == 'current_inventory':
                process_inventory_row(row)
            elif context == 'movement_tracker':
                process_movement_row(row)
            elif context == 'disposed_items':
                process_disposed_item_row(row, current_user)
        db.session.commit()
        flash('CSV imported successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Import failed: {str(e)}', 'danger')
        current_app.logger.error(f'CSV Import Failure: {str(e)}', exc_info=True)
    return redirect(url_for('index'))

@app.route('/export_csv')
@login_required
def export_csv():
    """Handles both single CSV and combined ZIP exports."""
    export_type = request.args.get('type', 'inventory')
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if export_type == 'all':
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr(f'inventory_{timestamp}.csv', generate_inventory_csv())
            zip_file.writestr(f'movements_{timestamp}.csv', generate_movements_csv())
            zip_file.writestr(f'disposals_{timestamp}.csv', generate_disposals_csv())
        buffer.seek(0)
        return send_file(buffer, download_name=f'export_all_{timestamp}.zip', as_attachment=True, mimetype='application/zip')

    data = {
        'inventory': generate_inventory_csv,
        'movements': generate_movements_csv,
        'disposals': generate_disposals_csv
    }.get(export_type, lambda: abort(400))()
    buffer = BytesIO()
    buffer.write(data.encode('utf-8-sig'))
    buffer.seek(0)
    return send_file(buffer, download_name=f'{export_type}_{timestamp}.csv', as_attachment=True, mimetype='text/csv')

@app.route('/download_template')
@login_required
def download_template():
    template_type = request.args.get('type', 'inventory')
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    if template_type == 'all':
        # Create ZIP with all templates
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            inv_data = generate_inventory_template()
            zip_file.writestr(f'inventory_template_{timestamp}.csv', inv_data)
            mov_data = generate_movements_template()
            zip_file.writestr(f'movements_template_{timestamp}.csv', mov_data)
            dis_data = generate_disposals_template()
            zip_file.writestr(f'disposals_template_{timestamp}.csv', dis_data)
        buffer.seek(0)
        return send_file(
            buffer,
            download_name=f'all_templates_{timestamp}.zip',
            as_attachment=True,
            mimetype='application/zip'
        )
    elif template_type == 'inventory':
        data = generate_inventory_template()
        filename = f'inventory_template_{timestamp}.csv'
    elif template_type == 'movements':
        data = generate_movements_template()
        filename = f'movements_template_{timestamp}.csv'
    elif template_type == 'disposals':
        data = generate_disposals_template()
        filename = f'disposals_template_{timestamp}.csv'
    else:
        abort(400, "Invalid template type")

    buffer = BytesIO()
    buffer.write(data.encode('utf-8-sig'))
    buffer.seek(0)
    return send_file(
        buffer,
        download_name=filename,
        as_attachment=True,
        mimetype='text/csv'
    )

# ---------- REPORTING / VIEW ROUTES ---------- #

@app.route('/disposed')
@login_required
def disposed_inventory():
    """Displays a searchable list of disposed items."""
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '').strip()
    query = DisposedItem.query.options(
        db.joinedload(DisposedItem.item),
        db.joinedload(DisposedItem.location)
    ).order_by(DisposedItem.disposed_date.desc())
    
    if search_query:
        search_term = f'%{search_query}%'
        query = query.join(Inventory).join(Location).filter(
            db.or_(
                Inventory.name.ilike(search_term),
                Location.name.ilike(search_term),
                DisposedItem.reason.ilike(search_term)
            )
        )
    
    disposed_paginated = query.paginate(
        page=page,
        per_page=PAGINATION_SETTINGS['DISPOSALS_PER_PAGE'],
        error_out=False
    )
    
    return render_template('disposed.html', 
                          disposed_items=disposed_paginated.items, 
                          pagination=disposed_paginated,
                          search_query=search_query)

@app.route('/search')
@login_required
def search():
    """Searches active inventory."""
    query_str = request.args.get('q', '').strip()
    if not query_str:
        return redirect(url_for('index'))
    
    page = request.args.get('page', 1, type=int)

    # Subquery to efficiently find items with stock > 0
    items_with_stock_subq = (
        db.session.query(ItemLocation.item_id)
        .filter(ItemLocation.quantity > 0)
        .distinct()
        .subquery()
    )
    
    # Main query with pagination
    query = Inventory.query.join(
        items_with_stock_subq,
        Inventory.id == items_with_stock_subq.c.item_id
    )
    
    search_term = f'%{query_str}%'
    query = query.filter(
        db.or_(
            Inventory.name.ilike(search_term),
            Inventory.description.ilike(search_term)
        )
    ).order_by(Inventory.name)
    
    # Subquery to calculate total quantities efficiently
    total_quantity_subq = (
        db.session.query(
            ItemLocation.item_id,
            db.func.sum(ItemLocation.quantity).label('total_qty')
        )
        .group_by(ItemLocation.item_id)
        .subquery()
    )
    
    # Join with the subquery to get total quantity efficiently
    query = query.outerjoin(
        total_quantity_subq,
        Inventory.id == total_quantity_subq.c.item_id
    ).add_columns(total_quantity_subq.c.total_qty)
    
    inventory_paginated = query.paginate(
        page=page,
        per_page=PAGINATION_SETTINGS['INVENTORY_PER_PAGE'],
        error_out=False
    )
    
    # Transform to include total_quantity in the item objects
    inventory_items = []
    for item, total_qty in inventory_paginated.items:
        item.total_quantity_cached = total_qty or 0
        inventory_items.append(item)
    
    # Create a paginated result object similar to the one we defined in the model
    paginated_result = type('PaginatedResult', (), {
        'items': inventory_items,
        'page': inventory_paginated.page,
        'pages': inventory_paginated.pages,
        'total': inventory_paginated.total,
        'has_next': inventory_paginated.has_next,
        'has_prev': inventory_paginated.has_prev
    })()
    
    return render_template('index.html', 
                          inventory=paginated_result.items,
                          pagination=paginated_result,
                          search_query=query_str)

@app.route('/movements')
@login_required
def movements():
    """Displays movement history with search functionality."""
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '').strip()
    
    # Base query
    query = Movement.query.options(
        db.joinedload(Movement.item),
        db.joinedload(Movement.from_location),
        db.joinedload(Movement.to_location)
    ).order_by(Movement.movement_date.desc())
    
    if search_query:
        search_term = f'%{search_query}%'
        query = query.join(Inventory).outerjoin(Location,
            (Movement.from_location_id == Location.id) |
            (Movement.to_location_id == Location.id)
        ).filter(
            db.or_(
                Inventory.name.ilike(search_term),
                Movement.responsible_person.ilike(search_term),
                Location.name.ilike(search_term)
            )
        )

    movements_paginated = query.paginate(
        page=page,
        per_page=PAGINATION_SETTINGS['MOVEMENTS_PER_PAGE'],
        error_out=False
    )
    
    return render_template('movements.html', 
                         movements=movements_paginated.items,
                         pagination=movements_paginated,
                         search_query=search_query)

@app.route('/item/<int:item_id>')
@login_required
def item_detail(item_id):
    """Displays details for a specific item."""
    item = Inventory.query.options(
        db.joinedload(Inventory.locations).joinedload(ItemLocation.location)
    ).get_or_404(item_id)
    
    # Preload the total quantity to avoid N+1 issues in templates
    item.total_quantity_cached = item.total_quantity  # This will calculate it once and cache it
    
    return render_template('item_detail.html', item=item)

@app.route('/location/<int:location_id>')
@login_required
def location_detail(location_id):
    """Displays details for a specific location."""
    location = Location.query.get_or_404(location_id)
    items_at_location = ItemLocation.query.options(
        db.joinedload(ItemLocation.item)
    ).filter_by(location_id=location_id).all()
    
    # Preload total quantities for items to avoid N+1 issues
    item_ids = [il.item_id for il in items_at_location]
    items = Inventory.query.filter(Inventory.id.in_(item_ids)).all()
    Inventory.preload_total_quantities(items)
    
    # Create a mapping for quick lookup
    item_map = {item.id: item for item in items}
    
    # Update items in items_at_location with cached total quantities
    for item_loc in items_at_location:
        if item_loc.item_id in item_map:
            item_loc.item.total_quantity_cached = item_map[item_loc.item_id].total_quantity_cached
    
    return render_template('location_detail.html', location=location, items=items_at_location)