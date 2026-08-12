# DEMO PROJECT: INVENTORY MANAGEMENT SYSTEM

## Description

A simple **Flask-based inventory management system** designed to track items, their locations, stock movements, and disposals. This is an experimental project originally developed for managing inventory in a church setting. It includes user authentication with admin controls, CSV import/export functionality, and reporting tools for managing resources across multiple locations.

## Disclaimer

* This project is intended for **educational, testing, and experimentation purposes only**.
* **Not suitable for production use**.
* This guide and project will not be updated regularly.
* Use at your own risk. No warranties, guarantees, or support are provided.

## Tech Stack

* **Backend:** Flask (Python)
* **Frontend:** Bootstrap 5
* **Database:** MySQL

---

# Local Deployment Guide for Windows 11 (MySQL)

This guide provides instructions on how to set up and run the application on a local Windows 11 machine using MySQL as the database.

---

## 1. Install MySQL

1.  **Download MySQL Installer:**
    *   Go to the [MySQL Downloads page](https://dev.mysql.com/downloads/installer/) and download the latest MySQL Installer for Windows.
2.  **Run the Installer:**
    *   Execute the downloaded installer. Choose a "Developer Default" setup type or customize to include MySQL Server, MySQL Workbench, and MySQL Shell.
    *   During configuration, you will be prompted to set a root password. **Remember this password.**
    *   Ensure MySQL Server is configured to run as a Windows Service.

---

## 2. Create the Database and User

1.  **Open MySQL Command Line Client:**
    *   Search for "MySQL Command Line Client" in the Start Menu and open it.
    *   Enter the root password you set during installation.
2.  **Execute the following SQL commands** to create the database and a dedicated user for the application.

    *   Replace `YourSuperSecretDBPassword` with a secure password of your choice.

    ```sql
    -- Create the database for the inventory system
    CREATE DATABASE inventory_management_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

    -- Create a new user and grant privileges to the database
    CREATE USER 'mysql_username'@'localhost' IDENTIFIED BY 'YourSuperSecretDBPassword';
    GRANT ALL PRIVILEGES ON inventory_management_db.* TO 'mysql_username'@'localhost';

    -- Apply the changes
    FLUSH PRIVILEGES;

    -- Exit the client
    EXIT;
    ```

---

## 3. Set Up the Project

1.  **Clone the Repository:**
    *   Open PowerShell or Command Prompt and navigate to your desired project directory.
    *   Run the following command:
        ```bash
        git clone https://github.com/stephen-cpe/inventory_management_system.git
        cd inventory_management_system
        ```
2.  **Create and Activate a Virtual Environment:**
    ```bash
    # Create the virtual environment
    python -m venv venv

    # Activate the virtual environment
    venv\Scripts\activate
    ```
3.  **Install Dependencies:**
    ```bash
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    ```

---

## 4. Initialize the Database Schema

1.  **Open MySQL Command Line Client (if closed) and select the database:**
    *   Search for "MySQL Command Line Client" in the Start Menu and open it.
    *   Enter the root password.
    *   Type:
        ```sql
        USE inventory_management_db;
        ```
2.  **Paste the contents of `init_db.sql`:**
    *   Open the `init_db.sql` file located in your project directory with a text editor.
    *   Copy the entire content of the file.
    *   Paste it into the MySQL Command Line Client and press Enter. This will create the necessary tables and schema.

---

## 5. Create a `.env` file

1.  In the root of your project directory, create a new file named `.env`.
2.  Add the following content to the `.env` file. Replace `YourSuperSecretVeryLongKey` and `YourSuperSecretDBPassword` with your actual secret key and the database user's password.

    ```
    SECRET_KEY=YourSuperSecretVeryLongKey
    DATABASE_URL=mysql+pymysql://mysql_username:YourSuperSecretDBPassword@localhost/inventory_management_db
    LOG_LEVEL=INFO
    # Flask configuration
    FLASK_APP=app.py
    FLASK_DEBUG=False
    # Admin user credentials (used by create-admin CLI command)
    ADMIN_USERNAME=admin
    ADMIN_PASSWORD=admin123
    ```

    > **Note:** The `.env` file is used to load environment variables locally. For production deployments, it's recommended to set these variables directly in your hosting environment.

---

## 6. Run Migrations and Create Admin User

1.  **Ensure your virtual environment is active** and you are in the project's root directory.
2.  **Run Flask migrations** (this will ensure Flask-Migrate is in sync with your database schema, though `init_db.sql` already created the tables):
    ```bash
    flask db init
    flask db upgrade
    ```
3.  **Create the first admin user:**
    ```bash
    flask create-admin
    ```
    *   You will be prompted to enter a username and password for the admin account.

---

## 7. Run the Application

*   Execute the following command to start the Flask development server:
    ```bash
    flask run
    ```
*   Open your web browser and navigate to:
    ```
    http://127.0.0.1:5000
    ```
*   You can now log in with the admin credentials you created.

---

---


## Project Demo

Watch the demo: [https://www.youtube.com/watch?v=5BZoWD-7U-s](https://www.youtube.com/watch?v=5BZoWD-7U-s)

---

## TODO

* Conduct further testing and gather feedback.
* Add Unit Tests. Perform Corrective, Adaptive, and Perfective Maintenance.
