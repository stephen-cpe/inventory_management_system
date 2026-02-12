# Deployment Guide for AWS EC2 Amazon Linux (ARM)

This guide assumes you're starting with a fresh AWS account using Free Tier eligible resources (t4g.micro instance).

## Disclaimer

* This project is intended for **educational, testing, and experimentation purposes only**.
* **Not suitable for production use**.
* This guide and project will not be updated regularly.
* Use at your own risk. No warranties, guarantees, or support are provided.

## 1. Launch EC2 Instance
From AWS Management Console:
- Navigate to EC2 → Instances → Launch Instance
- Name: `inventory-management-app`
- Application and OS Images: **Amazon Linux 2023 6.12 (ARM)**
- Instance type: **t4g.micro** (Free Tier eligible, ARM-based)
- Key pair: Create or select an existing key pair for SSH access
- Network settings:
  - Allow SSH (port 22)
  - Allow HTTP (port 80) and HTTPS (port 443)
- Storage: 8 GB gp3 (Free Tier eligible)
- Launch instance

## 2. Connect to EC2 Instance
```bash
# Connect via SSH (replace with your key and public IP)
ssh -i "your-key.pem" ec2-user@your-ec2-public-ip
```

## 3. Install Required Software
```bash
# Update system packages
sudo dnf update -y

# Install MySQL Server
sudo dnf install -y https://dev.mysql.com/get/mysql80-community-release-el9-1.noarch.rpm
sudo dnf install -y mysql-community-server --nogpgcheck
sudo systemctl start mysqld
sudo systemctl enable mysqld

# Install Python and build tools
sudo dnf install python3.13 python3.13-pip python3.13-devel mariadb105-devel mariadb105 git gcc openssl nginx -y


# Retrieve the temporary password
sudo grep 'temporary password' /var/log/mysqld.log

# Start MySQL and secure installation
sudo mysql_secure_installation
# Follow prompts (set root password when asked)
```
**Note:** When prompted, you can simply choose **Yes** through all of them.

## 4. Create the Database and User
```bash
# Log into MySQL as root
sudo mysql -u root -p
# Enter the root password you set during mysql_secure_installation
```

```sql
-- Create the database for the inventory system
CREATE DATABASE inventory_management_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create a new user and grant privileges to the database
CREATE USER 'mysql_username'@'localhost' IDENTIFIED BY 'Y0uRsUp3rS3cR3tDBP4ssw0Rd!';
GRANT ALL PRIVILEGES ON inventory_management_db.* TO 'mysql_username'@'localhost';

-- Apply the changes
FLUSH PRIVILEGES;

-- Exit the client
EXIT;
```

## 5. Set Up the Project
```bash
# Clone the repository
git clone https://github.com/stephen-cpe/inventory_management_system.git
cd inventory_management_system

# Create and activate virtual environment
python3.13 -m pip install --upgrade pip
python3.13 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn
```

## 6. Initialize the Database Schema
```bash
# Execute the SQL schema
mysql -u mysql_username -pY0uRsUp3rS3cR3tDBP4ssw0Rd! inventory_management_db < init_db.sql
```

## 7. Create `.env` file
```bash
nano .env
```

Add the following content:
```ini
SECRET_KEY=YourSuperSecretVeryLongKey
DATABASE_URL=mysql+pymysql://mysql_username:Y0uRsUp3rS3cR3tDBP4ssw0Rd!@localhost/inventory_management_db
LOG_LEVEL=INFO
FLASK_APP=app.py
FLASK_DEBUG=False
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

## 8. Run Migrations and Create Admin User
```bash
# Set environment variables for the session
export $(cat .env | xargs)

# Run Flask commands
flask db init
flask db upgrade

# Create the admin user
flask create-admin
# Use default credentials when prompted (admin/admin123)
```

## 9. Configure Systemd Service

```bash
sudo nano /etc/systemd/system/inventory-app.service
```

Add this configuration:

```ini
[Unit]
Description=Church Inventory Management System
After=network.target mysqld.service

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=/home/ec2-user/inventory_management_system
EnvironmentFile=/home/ec2-user/inventory_management_system/.env
# Note: Binding to 127.0.0.1 ensures only Nginx can talk to the app
ExecStart=/home/ec2-user/inventory_management_system/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Reload and restart the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable inventory-app
sudo systemctl restart inventory-app
```

## 10. Generate Self-Signed SSL Certificate

```bash
# Generate the private key and certificate in one command
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/pki/tls/private/selfsigned.key -out /etc/pki/tls/certs/selfsigned.crt
```

**Note:** When prompted for details (Country, State, Common Name, etc.), you can simply press **Enter** through all of them.

## 11. Configure Nginx for HTTPS (Self-Signed)

```bash
# Start and enable Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# Create the configuration file
sudo nano /etc/nginx/conf.d/inventory-app.conf
```

Add the following configuration. This sets up both HTTP (port 80) and HTTPS (port 443).

*Note: Since you don't have a domain, we use `server_name _;` which tells Nginx to catch any IP address or hostname used to access the server.*

```nginx
server {
    listen 80;
    server_name _;
    # Redirect all HTTP traffic to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name _;

    # SSL Configuration
    ssl_certificate /etc/pki/tls/certs/selfsigned.crt;
    ssl_certificate_key /etc/pki/tls/private/selfsigned.key;

    # Basic SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        # Proxy to the Flask App (Gunicorn) running on localhost
        proxy_pass http://127.0.0.1:5000;
        
        # Pass headers so Flask knows the real IP and that request is HTTPS
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

Test and reload Nginx:
```bash
# Check for syntax errors
sudo nginx -t

# If successful, reload Nginx
sudo systemctl reload nginx
```

## 12. Access the Application

1.  Open your browser.
2.  Navigate to: `https://YOUR-EC2-PUBLIC-IP`

### Troubleshooting
If the site does not load:

1.  **Check Security Groups:** Ensure your EC2 Security Group allows Inbound traffic on **Port 443** (HTTPS).
2.  **Check Nginx Logs:**
    ```bash
    sudo tail -f /var/log/nginx/error.log
    ```
3.  **Check Gunicorn Status:**
    ```bash
    sudo systemctl status inventory-app
    ```
---

# Deployment Guide for EC2 Amazon Linux (ARM) with RDS

This guide assumes you're starting with a fresh AWS account using Free Tier eligible resources (t4g.micro instance and db.t4g.micro RDS).

## 1. Launch EC2 Instance
From AWS Management Console:
- Navigate to EC2 → Instances → Launch Instance
- Name: `inventory-management-app`
- Application and OS Images: **Amazon Linux 2023 6.12 (ARM)**
- Instance type: **t4g.micro** (Free Tier eligible, ARM-based)
- Key pair: Create or select an existing key pair for SSH access
- Network settings:
  - Allow SSH (port 22)
  - Allow HTTP (port 80) and HTTPS (port 443)
- Storage: 8 GB gp3 (Free Tier eligible)
- Launch instance
- *Take note of the EC2 VPC ID*

## 2. Create RDS Database Instance
From AWS Management Console:
- Navigate to RDS → Databases → Create database
- Choose database creation method: **Easy create**
- Engine options: **MySQL**
- Templates: **Free tier**
- Settings:
  - DB instance identifier: `inventory-db`
  - Master username: `mysql_username`
  - Master password: `Y0uRsUp3rS3cR3tDBP4ssw0Rd!`
- DB instance size: **db.t4g.micro** (Free Tier)
- Set up EC2 connection - optional
   - Connect to an EC2 compute resource and select your EC2 instance
- Click **Create database** (takes ~5-10 minutes)

## 3. Get RDS Endpoint
- Go to RDS → Databases → `inventory-db`
- Wait for Status to show **Available**
- Copy the **Endpoint** (something like: `inventory-db.abc123xyz.us-east-1.rds.amazonaws.com`)
- Save this for later use

## 5. Connect to EC2 Instance
```bash
# Connect via SSH (replace with your key and public IP)
ssh -i "your-key.pem" ec2-user@your-ec2-public-ip
```

## 6. Install Required Software
```bash
# Update system packages
sudo dnf update -y

# Install Python, MySQL client, and build tools
sudo dnf install python3.13 python3.13-pip python3.13-devel mariadb105-devel mariadb105 git gcc openssl nginx -y
```

## 7. Test RDS Connection and Create Database User
```bash
# Connect to RDS MySQL (replace with your RDS endpoint)
mysql -h inventory-db.abc123xyz.us-east-1.rds.amazonaws.com -u mysql_username -p
# Enter the password: Y0uRsUp3rS3cR3tDBP4ssw0Rd!
```

```sql
-- The database should already exist, but verify
CREATE DATABASE inventory_management_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON inventory_management_db.* TO 'mysql_username'@'%';

-- Apply the changes
FLUSH PRIVILEGES;

-- Exit the client
EXIT;
```

## 8. Set Up the Project
```bash
# Clone the repository
git clone https://github.com/stephen-cpe/inventory_management_system.git
cd inventory_management_system

# Create and activate virtual environment
python3.13 -m pip install --upgrade pip
python3.13 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn
```

## 9. Initialize the Database Schema
```bash
# Execute the SQL schema (replace with your RDS endpoint)
mysql -h inventory-db.abc123xyz.us-east-1.rds.amazonaws.com -u mysql_username -pY0uRsUp3rS3cR3tDBP4ssw0Rd! inventory_management_db < init_db.sql
```

## 10. Create `.env` file
```bash
nano .env
```

Add the following content (replace RDS_ENDPOINT with your actual endpoint):
```ini
SECRET_KEY=YourSuperSecretVeryLongKey
DATABASE_URL=mysql+pymysql://mysql_username:Y0uRsUp3rS3cR3tDBP4ssw0Rd!@inventory-db.abc123xyz.us-east-1.rds.amazonaws.com/inventory_management_db
LOG_LEVEL=INFO
FLASK_APP=app.py
FLASK_DEBUG=False
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

## 11. Run Migrations and Create Admin User
```bash
# Set environment variables for the session
export $(cat .env | xargs)

# Run Flask commands
flask db init
flask db upgrade

# Create the admin user
flask create-admin
# Use default credentials when prompted (admin/admin123)
```

## 12. Configure Systemd Service

```bash
sudo nano /etc/systemd/system/inventory-app.service
```

Add this configuration:

```ini
[Unit]
Description=Church Inventory Management System
After=network.target

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=/home/ec2-user/inventory_management_system
EnvironmentFile=/home/ec2-user/inventory_management_system/.env
# Note: Binding to 127.0.0.1 ensures only Nginx can talk to the app
ExecStart=/home/ec2-user/inventory_management_system/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Reload and restart the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable inventory-app
sudo systemctl restart inventory-app
```

## 13. Generate Self-Signed SSL Certificate

```bash
# Generate the private key and certificate in one command
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/pki/tls/private/selfsigned.key -out /etc/pki/tls/certs/selfsigned.crt
```

**Note:** When prompted for details (Country, State, Common Name, etc.), you can simply press **Enter** through all of them.

## 14. Configure Nginx for HTTPS (Self-Signed)

```bash
# Start and enable Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# Create the configuration file
sudo nano /etc/nginx/conf.d/inventory-app.conf
```

Add the following configuration. This sets up both HTTP (port 80) and HTTPS (port 443).

```nginx
server {
    listen 80;
    server_name _;
    # Redirect all HTTP traffic to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name _;

    # SSL Configuration
    ssl_certificate /etc/pki/tls/certs/selfsigned.crt;
    ssl_certificate_key /etc/pki/tls/private/selfsigned.key;

    # Basic SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        # Proxy to the Flask App (Gunicorn) running on localhost
        proxy_pass http://127.0.0.1:5000;
        
        # Pass headers so Flask knows the real IP and that request is HTTPS
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

Test and reload Nginx:
```bash
# Check for syntax errors
sudo nginx -t

# If successful, reload Nginx
sudo systemctl reload nginx
```

## 15. Access the Application

1.  Open your browser.
2.  Navigate to: `https://YOUR-EC2-PUBLIC-IP`

### Troubleshooting

If the site does not load:

1.  **Check Security Groups:** 
    - EC2 Security Group allows Inbound traffic on **Port 443** (HTTPS)
    - RDS Security Group allows MySQL/Aurora (3306) from EC2

2.  **Check RDS Connection:**
    ```bash
    mysql -h your-rds-endpoint -u mysql_username -p
    ```

3.  **Check Nginx Logs:**
    ```bash
    sudo tail -f /var/log/nginx/error.log
    ```

4.  **Check Gunicorn Status:**
    ```bash
    sudo systemctl status inventory-app
    sudo journalctl -u inventory-app -f
    ```

5.  **Verify RDS Status:**
    - AWS Console → RDS → Check database is "Available"
    - Check CloudWatch metrics for connection errors

---