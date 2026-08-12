# Software Requirement Specification: Church Inventory System

## 1. Introduction

### 1.1 Purpose

This document provides a detailed specification of the requirements for the Church Inventory System. The system is a web-based Flask application designed to track inventory items, their locations, quantities, and movements. It provides functionality for managing items, users, and locations, tracking disposals, and importing/exporting data via CSV.

### 1.2 Scope

The system is a self-contained web application. Its scope includes:
* **User Authentication:** Secure user login, registration (admin-only), and password management.
* **Access Control:** Distinction between standard users and administrators, with specific permissions for each role.
* **Inventory Management:** Creating, editing, and deleting inventory items. This includes tracking item details such as name, description, category, condition, acquisition date, and price.
* **Stock Tracking:** Managing the quantity of items at various named locations.
* **Movement Tracking:** Recording the transfer of items between locations, including the responsible person and date.
* **Disposal Tracking:** Recording the disposal of items, including the reason, date, and responsible user.
* **Reporting:** Providing searchable, paginated views of the current inventory, movement history, and disposal records.
* **Data Portability:** Functionality to import and export all major data types (inventory, movements, disposals) using CSV files.
* **System Administration:** CLI commands for administrative tasks such as creating admin users and resetting login attempts.

### 1.3 Definitions, Acronyms, and Abbreviations

* **System:** The Church Inventory Flask Application.
* **User:** A standard user who can log in, view inventory, and perform basic operations like transfers and disposals.
* **Admin:** A user with elevated privileges who can manage users and all inventory items (including editing and deleting).
* **Item:** A unique inventory object (e.g., "Chalice").
* **Location:** A named storage area (e.g., "Sanctuary", "Storage Room").
* **Stock:** The quantity of a specific Item at a specific Location.
* **Movement:** A record of a transfer of an Item from one Location to another.
* **Disposal:** A record of an Item's quantity being permanently removed from inventory.
* **CLI:** Command Line Interface.
* **CSRF:** Cross-Site Request Forgery.
* **SQLAlchemy:** The SQL toolkit and Object-Relational Mapper (ORM) used.
* **Flask:** The web framework used to build the application.

### 1.4 References

* **Flask:** The web framework.
* **Flask-Login:** Handles user session management.
* **Flask-SQLAlchemy:** Manages database interaction.
* **Flask-WTF:** Provides web form handling and CSRF protection.
* **Flask-Migrate:** Handles database schema migrations.
* **Werkzeug:** Provides security functions for password hashing.
* **Bootstrap 5.3.8 + Bootstrap Icons 1.13.1:** Frontend CSS/JS framework, loaded from the jsDelivr CDN (`cdn.jsdelivr.net`).
* **gunicorn:** Production WSGI HTTP server used for non-PythonAnywhere deployments.
* **PostgreSQL:** Supported relational database for PaaS deployments (Render, Railway, Fly.io). MySQL remains the reference backend for PythonAnywhere / EC2 / DigitalOcean.

---

## 2. Overall Description

### 2.1 Product Perspective

The system is a standalone, self-hosted web application. It is not dependent on other systems, though it is designed to be deployed in a standard Python web environment (e.g., using a WSGI server) and connect to an SQL database.

### 2.2 Product Functions

The major functions of the system are:
1.  **Authentication:** Secure login/logout and password management.
2.  **User Management:** Admin-only registration of new users (both Users and Admins).
3.  **Inventory Viewing:** Separate, searchable views for active inventory, movement history, and disposal history.
4.  **Stock Management:** Adding new items, adding stock to existing items, transferring stock between locations, and disposing of stock.
5.  **Item Management (Admin):** Editing all item details, managing stock at all locations, and permanently deleting items.
6.  **Data I/O:** CSV import/export for inventory, movements, and disposals.
7.  **System Maintenance:** CLI commands for user creation and security resets.

### 2.3 User Characteristics

There are two primary user roles:

* **User (Standard):**
    * Can log in and log out.
    * Can change their own password.
    * Can view the main inventory list (items with stock > 0).
    * Can view the movement and disposal history.
    * Can add new items or add stock to existing items.
    * Can perform item transfers.
    * Can record item disposals.
    * Can export data and download templates.

* **Admin:**
    * Possesses all permissions of a standard User.
    * Can register new users and assign them admin status.
    * Can view and manage *all* items, including those with zero stock.
    * Can edit all properties of any inventory item.
    * Can manage the stock of any item at any location from a central edit page.
    * Can permanently delete inventory items and their related records.

### 2.4 Constraints

* **C-1 (Technology):** The system is built using Python 3 and the Flask web framework.
* **C-2 (Database):** The system is designed for a relational SQL database. The reference schema (`init_db.sql`) is written for MySQL (using InnoDB and utf8mb4). The SQLAlchemy models are database-agnostic (using generic column types and portable `ilike()` filters), so the application also runs against PostgreSQL by changing the `DATABASE_URL` environment variable — no code changes required. PostgreSQL is the recommended backend for PaaS free-tier deployments (Render, Railway, Fly.io) which offer free Postgres but not free MySQL. A `flask create-tables` CLI command is provided to initialize the schema via `db.create_all()` on platforms where `init_db.sql` cannot be run directly. `ON DELETE CASCADE` is explicitly defined in the MySQL schema and in the SQLAlchemy `ForeignKey(ondelete='CASCADE')` declarations, and is relied upon for data integrity.
* **C-3 (Deployment):** The system must be deployed in an environment where Python environment variables can be set (e.g., for `SECRET_KEY` and `DATABASE_URL`). Production deployments use the `gunicorn` WSGI server (configured via the `Procfile`) on PaaS platforms (Render, Railway, Fly.io) and a WSGI import (`from app import app as application`) on PythonAnywhere. A `create_app()` application factory supports both production and isolated testing instances.
* **C-4 (Security):** A strong, unique `SECRET_KEY` environment variable is required for production to secure sessions and CSRF tokens.
* **C-5 (Performance):** The system is optimized for the free tier of PythonAnywhere, utilizing specific database connection pool settings (`pool_size: 5`, `pool_recycle: 280`, `pool_timeout: 10`, `max_overflow: 2`, `pool_pre_ping: True`) to manage connection timeouts.

### 2.5 Assumptions and Dependencies

* **A-1:** The system assumes a persistent SQL database is available and configured via the `DATABASE_URL` environment variable.
* **A-2:** Users will access the system via a modern web browser that supports HTML5, CSS3, and JavaScript.
* **A-3:** For the `create-admin` CLI command, the system assumes it is being run in a secure shell environment where `getpass` can function or where environment variables (`ADMIN_PASSWORD`) are securely managed.

---

## 3. Specific Requirements

### 3.1 Functional Requirements

#### FR-1: Authentication

* **FR-1.1 (Login):** A user shall be able to log in using a unique username and a password. Username matching is case-insensitive under the default MySQL `utf8mb4_unicode_ci` collation.
* **FR-1.2 (Logout):** An authenticated user shall be able to log out, which must terminate their session.
* **FR-1.3 (Password Change):** An authenticated user shall be able to change their own password. This shall require them to provide their correct current password and a new password (min. 8 characters) with confirmation.
* **FR-1.4 (Login Lockout):** The system shall lock a user account if 5 or more failed login attempts are recorded for that username within a 12-hour period.
* **FR-1.5 (Login Attempt Logging):** Failed login attempts shall be recorded in the `login_attempt` table, capturing the username, IP address, and success status. Successful logins are not recorded; instead, upon success, any prior failed attempts for that user are cleared (see FR-1.7).
* **FR-1.6 (Session Persistence):** A user shall be able to select a "Remember me" option during login to maintain their session across browser restarts.
* **FR-1.7 (Failed Attempt Clearing):** Upon a successful login, all *previous* failed login attempt records for that user shall be deleted.

#### FR-2: User Management (Admin-Only)

* **FR-2.1 (User Registration):** A user with Admin privileges shall be able to register new users.
* **FR-2.2 (Registration Fields):** Registration shall require a unique username, a password, and a boolean flag to grant (or not grant) admin privileges.
* **FR-2.3 (Username Uniqueness):** The system shall enforce username uniqueness at the database level and prevent registration of a duplicate username.

#### FR-3: Inventory Management

* **FR-3.1 (Add Item/Stock):**
    * **FR-3.1.1:** Any authenticated user can add a new item or add stock to an existing item.
    * **FR-3.1.2:** This action requires an item name, location name, and a positive quantity.
    * **FR-3.1.3:** Optional fields include description, category, condition, date acquired, and price per item.
    * **FR-3.1.4:** If an item with the same name and description does not exist, a new `Inventory` record shall be created.
    * **FR-3.1.5:** If the specified location does not exist, a new `Location` record shall be created.
    * **FR-3.1.6:** If stock for that item *already* exists at that location, the new quantity shall be added to the existing quantity. Otherwise, a new `ItemLocation` record shall be created.
* **FR-3.2 (Edit Item - Admin-Only):**
    * **FR-3.2.1:** An Admin shall be able to edit all metadata for an `Inventory` item (name, description, category, etc.).
    * **FR-3.2.2:** An Admin shall be able to update the quantity of an item at any of its existing locations.
    * **FR-3.2.3:** If an Admin updates a quantity to 0 (or any non-positive value), the corresponding `ItemLocation` record shall be deleted.
    * **FR-3.2.4:** An Admin shall be able to change the location of a stock record. If the new location *already* has stock of that item, the quantities shall be merged, and the old `ItemLocation` record shall be deleted.
    * **FR-3.2.5:** An Admin shall be able to add stock to a new, previously unassociated location for that item.
* **FR-3.3 (Delete Item - Admin-Only):**
    * **FR-3.3.1:** An Admin shall be able to permanently delete an `Inventory` item.
    * **FR-3.3.2:** Deletion shall require an explicit confirmation from the user (via a checkbox).
    * **FR-3.3.3:** Deleting an `Inventory` item shall trigger a cascading delete of all associated `ItemLocation`, `Movement`, and `DisposedItem` records.
* **FR-3.4 (Item Transfer):**
    * **FR-3.4.1:** An authenticated user shall be able to transfer a specified quantity of an item from a source location to a destination location.
    * **FR-3.4.2:** The system shall validate that the quantity being transferred is positive and does not exceed the available stock at the source `ItemLocation`.
    * **FR-3.4.3:** The source and destination locations must be different.
    * **FR-3.4.4:** The destination location may be an existing location or a new location name, which the system will create.
    * **FR-3.4.5:** A successful transfer shall decrement the `source.quantity` and increment the `destination.quantity`.
    * **FR-3.4.6:** A successful transfer shall create a `Movement` record capturing the item, quantity, from/to locations, responsible person, and timestamp.
* **FR-3.5 (Item Disposal):**
    * **FR-3.5.1:** An authenticated user shall be able to dispose of a specified quantity of an item from a specific location.
    * **FR-3.5.2:** The system shall validate that the quantity being disposed is positive and does not exceed the available stock at that `ItemLocation`.
    * **FR-3.5.3:** Disposal shall require a reason (e.g., "damaged", "lost") and a disposal date.
    * **FR-3.5.4:** A successful disposal shall create a `DisposedItem` record capturing all details, with `disposed_by` set to the current user's username.
    * **FR-3.5.5:** A successful disposal shall decrement the `ItemLocation.quantity`.
    * **FR-3.5.6:** If a disposal results in an `ItemLocation.quantity` of 0, that `ItemLocation` record shall be deleted.

#### FR-4: Views and Reporting

* **FR-4.1 (Current Inventory View):** The main (`/`) view shall display a paginated list of all inventory items where the `total_quantity` (sum across all locations) is greater than 0.
* **FR-4.2 (Movement Tracker View):** The (`/movements`) view shall display a paginated list of all `Movement` records, sorted by date descending.
* **FR-4.3 (Disposed Items View):** The (`/disposed`) view shall display a paginated list of all `DisposedItem` records, sorted by date descending.
* **FR-4.4 (Edit Items View - Admin):** The (`/edit_items`) view shall display a paginated list of *all* inventory items, including those with 0 stock.
* **FR-4.5 (Delete Items View - Admin):** The (`/delete_items`) view shall display a paginated list of *all* inventory items, providing a link to the delete confirmation page for each.
* **FR-4.6 (Pagination):** All main list views (FR-4.1 to FR-4.5) shall be paginated and must persist any active search query across pages.
* **FR-4.7 (Item Detail View):** The (`/item/<item_id>`) view shall display the details of a specific `Inventory` item, including its stock across all locations (eager-loaded).
* **FR-4.8 (Location Detail View):** The (`/location/<location_id>`) view shall display the items present at a specific `Location`, with each item's total quantity across all locations preloaded.
* **FR-4.9 (Inventory Search View):** The (`/search`) view shall display a paginated list of inventory items where `total_quantity` > 0, filtered by the search query, and rendered using the Current Inventory template.

#### FR-5: Search

* **FR-5.1 (Inventory Search):** The Current Inventory and Inventory Search views shall filter by `Inventory.name` and `Inventory.description`. The Edit Items and Delete Items views shall filter by `Inventory.name`, `Inventory.description`, `Inventory.category`, and `Inventory.condition`.
* **FR-5.2 (Movement Search):** The Movement Tracker view shall be searchable. The search shall filter by `Inventory.name`, `Movement.responsible_person`, and `Location.name` (for both `from_location` and `to_location`).
* **FR-5.3 (Disposal Search):** The Disposed Items view shall be searchable. The search shall filter by `Inventory.name`, `Location.name`, and `DisposedItem.reason`.

#### FR-6: CSV Data Management

* **FR-6.1 (CSV Import):**
    * **FR-6.1.1:** The system shall provide a CSV import function for Inventory, Movements, and Disposals, each via a modal on its respective page.
    * **FR-6.1.2:** The import function must read files encoded with `utf-8-sig` (to handle potential BOM).
    * **FR-6.1.3 (Inventory Import):** Importing an inventory CSV shall find items by name. If an item exists, it finds the `ItemLocation` and adds to the quantity. If not, it creates the new `Inventory` item and/or `ItemLocation` record.
    * **FR-6.1.4 (Movement/Disposal Import):** Importing a movement or disposal CSV shall find the item by name. If the item does not exist, a new, minimal `Inventory` record shall be auto-created.
    * **FR-6.1.5:** All CSV imports shall create new locations if the specified location name does not exist.
* **FR-6.2 (CSV Export):**
    * **FR-6.2.1:** The system shall provide a CSV export function for the complete list of Inventory (with locations), Movements, and Disposals.
    * **FR-6.2.2:** The system shall provide a single "Export All" function that generates a ZIP archive containing all three CSV files.
    * **FR-6.2.3:** All exported filenames shall include a timestamp.
* **FR-6.3 (CSV Templates):**
    * **FR-6.3.1:** The system shall provide a downloadable, blank CSV template (with headers and one sample row) for each import type.
    * **FR-6.3.2:** The system shall provide a single "Download All Templates" function that generates a ZIP archive of all three templates.

#### FR-7: Command Line Interface (CLI)

* **FR-7.1 (Create Admin):** A CLI command (`flask create-admin`) shall be provided to create a new user with admin privileges. It shall prompt interactively for the username (defaulting to the `ADMIN_USERNAME` environment variable, or `'admin'`) and password. If the `ADMIN_PASSWORD` environment variable is set, the user shall be offered the option to use it non-interactively; otherwise the password is entered via `getpass` with confirmation.
* **FR-7.2 (Reset Login Attempts):** A CLI command (`flask reset-login-attempts`) shall be provided to clear all failed login attempt records, either for a specific user or for all users.
* **FR-7.3 (Create Tables):** A CLI command (`flask create-tables`) shall be provided to create all database tables defined by the SQLAlchemy models via `db.create_all()`. This is intended for PaaS deployments where the MySQL `init_db.sql` script cannot be run directly. The operation is idempotent (existing tables are skipped). On platforms with Alembic migrations enabled, `flask db upgrade` is preferred.
* **FR-7.4 (Auto-Create Admin on Boot):** The `wsgi.py` production entry point shall optionally auto-create a default admin user on process startup when the `AUTO_CREATE_ADMIN` environment variable is set to a truthy value (`1`, `true`, `yes`). The username defaults to the `ADMIN_USERNAME` env var (or `'admin'`), and the password defaults to the `ADMIN_PASSWORD` env var (or an insecure built-in default `Ch@ng3meA$@P`). This is intended for free-tier PaaS deployments (e.g. Render) that offer no shell/SSH access to run `flask create-admin`. The operation is idempotent (an existing user is not overwritten). The default password should be changed immediately via the Change Password page after first login.

### 3.2 External Interface Requirements

#### 3.2.1 User Interface

* **UI-1 (Responsive):** The UI shall be responsive and functional on both desktop and mobile devices.
* **UI-2 (Layout):** The three main views (Inventory, Movements, Disposals) shall share a common layout featuring a fixed header and a vertically scrollable table for content.
* **UI-3 (Stable Header):** The fixed header shall contain navigation tabs, search, and data I/O controls. On admin-only pages, navigation tabs for other views shall be rendered as invisible placeholders to maintain layout stability.
* **UI-4 (Sticky Headers):** All data tables shall feature "sticky" headers (`position: sticky`) that remain visible when the content area is scrolled.
* **UI-5 (Theming):** The UI shall use a color-coded theme for its main sections:
    * **Green (Success):** Current Inventory view.
    * **Blue (Primary):** Movement Tracker view and Edit Item pages.
    * **Red (Danger):** Disposed Items view and Delete Item pages.
    * **Dark (Dark):** Navigation bar, login, and registration pages.
* **UI-6 (Client-Side Validation):** The disposal form shall use JavaScript to read the available quantity for a selected location and set the `max` attribute of the "quantity" input field, providing immediate user feedback.

### 3.3 Database Requirements

The system shall utilize an SQL database adhering to the following schema and constraints:

* **DB-1 (Tables):** The database shall include the following tables:
    * `location`: Stores location names.
    * `inventory`: Stores core item details.
    * `item_location`: A junction table linking `inventory` and `location` with a `quantity`.
    * `movement`: A log of all transfers, linking to `inventory` and `location` (from/to).
    * `disposed_item`: A log of all disposals, linking to `inventory` and `location`.
    * `user`: Stores user credentials and admin status.
    * `login_attempt`: A log of all login attempts.
* **DB-2 (Constraints):** The following key constraints must be enforced:
    * `location.name` must be unique.
    * `user.username` must be unique.
    * `item_location.(item_id, location_id)` pair must be unique.
    * `item_location.quantity` must be >= 0.
    * `movement.quantity` must be > 0.
    * `movement` must have either a `from_location_id` or a `to_location_id`.
    * `disposed_item.quantity` must be > 0.
* **DB-3 (Data Integrity):** Foreign keys from `item_location`, `movement`, and `disposed_item` to `inventory.id` shall be configured with `ON DELETE CASCADE` to ensure that deleting an item automatically removes all associated stock, movement, and disposal records.
* **DB-4 (Character Set):** The database shall use the `utf8mb4` character set to support a wide range of characters.

### 3.4 Non-Functional Requirements

#### NFR-1: Security

* **NFR-1.1 (Password Hashing):** User passwords shall be stored as hashes using the `pbkdf2:sha256` method.
* **NFR-1.2 (CSRF Protection):** All forms that modify data (POST requests) shall be protected by a unique CSRF token. The system shall reject any POST request with a missing or invalid token.
* **NFR-1.3 (Configuration):** The application's `SECRET_KEY` must be set via an environment variable in production. The application shall log a security warning if the insecure default key is used.
* **NFR-1.4 (Error Handling):** Custom error handlers shall prevent application internals or stack traces from being exposed to the user. Handlers exist for HTTP 400, 403, 404, 405, and 500. The 400 handler specifically detects CSRF-related errors and flashes a user-friendly message.

#### NFR-2: Performance

* **NFR-2.1 (Connection Pooling):** The system shall use database connection pooling with `pool_size=5`, `pool_recycle=280`, `pool_timeout=10`, `max_overflow=2`, and `pool_pre_ping=True` to ensure connection stability and reuse.
* **NFR-2.2 (Query Optimization - N+1):** The system shall actively prevent N+1 query problems.
    * Paginated inventory lists shall calculate total quantities using a single efficient subquery and `OUTER JOIN`.
    * Detailed views (e.g., `location_detail`) shall use a batch-preload method (`preload_total_quantities`) to fetch all necessary data in a minimal number of queries.
    * Views loading related models (e.g., `movements` loading `item`) shall use `joinedload` to eager-load data.
* **NFR-2.3 (Client-Side Caching):**
    * **Local static assets** (`/static/`): the system shall instruct browsers to cache them for 1 day (`max-age=86400`). When the request URL contains a query string (e.g. `style.css?v=1.0`), the cache duration is extended to 1 year (`max-age=31536000`) to support cache-busting via version parameters.
    * **Bootstrap framework assets** (CSS, JS, icons) are loaded from the jsDelivr CDN (`cdn.jsdelivr.net`) rather than self-hosted. This offloads ~700 KB of egress bandwidth from the application server and benefits from browser cross-site caching. CDN caching is controlled by jsDelivr's own cache headers.

#### NFR-3: Reliability

* **NFR-3.1 (Database Transactions):** All database operations that involve multiple steps (e.g., add item, transfer, dispose, edit) shall be atomic. Any error during the process shall trigger a `db.session.rollback()` to prevent partial data writes.
* **NFR-3.2 (500 Error Recovery):** In the event of an unhandled exception (500 error), the system shall roll back the current database session and remove the connection, releasing it back to the pool to prevent a poisoned connection from affecting subsequent requests.

#### NFR-4: Maintainability

* **NFR-4.1 (Logging):** The system shall generate detailed logs. On long-running deployments with a writable filesystem (e.g. PythonAnywhere, EC2), logs are written to `app.log` via a `RotatingFileHandler` (10 backup files, 1,000,000 bytes each). On PaaS free tiers with ephemeral/read-only filesystems (e.g. Render, Railway, Fly.io), or when `LOG_TO_STDOUT=1` is set, the handler falls back to a stdout `StreamHandler` so the platform's own log drain captures the output. The log level shall be configurable via the `LOG_LEVEL` environment variable, defaulting to `DEBUG`. The file handler is attached only when Flask is not running in debug mode.
* **NFR-4.2 (Code Reusability):** Common query logic (e.g., inventory search) shall be centralized in a utility function (`get_inventory_query_with_search`). Common CSV processing logic shall be in dedicated utility functions.
* **NFR-4.3 (Configuration):** All key configuration (Secret Key, Database URL, Log Level, Debug Status, Host, and Port) shall be manageable via environment variables.