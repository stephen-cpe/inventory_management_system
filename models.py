from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from datetime import datetime, timezone

class Location(db.Model):
    """Represents different locations where inventory items are stored."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)

    # Relationships
    items = db.relationship('ItemLocation', back_populates='location', lazy='dynamic')
    outgoing_movements = db.relationship('Movement', foreign_keys='Movement.from_location_id', back_populates='from_location', lazy='dynamic')
    incoming_movements = db.relationship('Movement', foreign_keys='Movement.to_location_id', back_populates='to_location', lazy='dynamic')
    disposals = db.relationship('DisposedItem', back_populates='location', lazy='dynamic')

    def __repr__(self):
        return f'<Location {self.name}>'

class Inventory(db.Model):
    """Represents inventory items with their details."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.String(200))
    category = db.Column(db.String(50), index=True)
    condition = db.Column(db.String(50))

    # Relationships
    locations = db.relationship('ItemLocation', back_populates='item', lazy='joined', cascade="all, delete-orphan")
    movements = db.relationship('Movement', back_populates='item', lazy='joined', cascade="all, delete-orphan")
    disposals = db.relationship('DisposedItem', back_populates='item', cascade="all, delete-orphan", lazy='joined')

    def __repr__(self):
        return f'<Inventory {self.name}>'

    @property
    def total_quantity(self):
        """Calculates the total quantity across all locations."""
        return db.session.query(db.func.sum(ItemLocation.quantity))\
                         .filter(ItemLocation.item_id == self.id)\
                         .scalar() or 0

class ItemLocation(db.Model):
    """Represents the association between inventory items and locations, including quantity."""
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('inventory.id', ondelete='CASCADE'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    quantity = db.Column(db.Integer, default=0, nullable=False)

    # Relationships
    item = db.relationship('Inventory', back_populates='locations')
    location = db.relationship('Location', back_populates='items')

    # Constraints
    __table_args__ = (
        db.UniqueConstraint('item_id', 'location_id', name='_item_location_uc'),
        db.CheckConstraint('quantity >= 0', name='check_quantity_non_negative'),
    )

    def __repr__(self):
        return f'<ItemLocation Item:{self.item_id} Loc:{self.location_id} Qty:{self.quantity}>'

class Movement(db.Model):
    """Represents the movement of inventory items between locations."""
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('inventory.id', ondelete='CASCADE'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    from_location_id = db.Column(db.Integer, db.ForeignKey('location.id'))
    to_location_id = db.Column(db.Integer, db.ForeignKey('location.id'))
    movement_date = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    responsible_person = db.Column(db.String(100))
    notes = db.Column(db.Text)

    # Relationships
    item = db.relationship('Inventory', back_populates='movements')
    from_location = db.relationship('Location', foreign_keys=[from_location_id], back_populates='outgoing_movements')
    to_location = db.relationship('Location', foreign_keys=[to_location_id], back_populates='incoming_movements')

    # Constraints
    __table_args__ = (
        db.CheckConstraint('quantity > 0', name='check_movement_quantity_positive'),
        db.CheckConstraint('from_location_id IS NOT NULL OR to_location_id IS NOT NULL', name='check_location_presence'),
    )

    def __repr__(self):
        return f'<Movement {self.id}: {self.quantity} units of {self.item_id} on {self.movement_date}>'

class DisposedItem(db.Model):
    """Represents items that have been disposed of."""
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('inventory.id', ondelete='CASCADE'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    disposed_date = db.Column(db.Date, nullable=False)
    disposed_by = db.Column(db.String(100), nullable=False)
    notes = db.Column(db.String(200))

    # Relationships
    item = db.relationship('Inventory', back_populates='disposals')
    location = db.relationship('Location', back_populates='disposals')

    # Constraints
    __table_args__ = (
        db.CheckConstraint('quantity > 0', name='check_disposal_quantity_positive'),
    )

    def __repr__(self):
        return f'<DisposedItem Item:{self.item_id} Qty:{self.quantity} Date:{self.disposed_date}>'

class User(db.Model, UserMixin):
    """Represents users of the application with authentication details."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, password):
        """Sets the password hash for the user."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks if the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'