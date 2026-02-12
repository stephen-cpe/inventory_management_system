# DigitalOcean Deployment Guide with DuckDNS
## For $12/month Ubuntu 24.04 LTS Droplet + DuckDNS + Let's Encrypt SSL

## Disclaimer

* This project is intended for **educational, testing, and experimentation purposes only**.
* **Not suitable for production use**.
* This guide and project will not be updated regularly.
* Use at your own risk. No warranties, guarantees, or support are provided.

---

## 1. Prerequisites
1. **DigitalOcean Account** with payment method set up
2. **DuckDNS Account** (free at [duckdns.org](https://duckdns.org))
3. **Domain**: We'll use `churchinventory.duckdns.org` (replace with your DuckDNS domain)

---

## 2. Create Droplet with Proper Hostname
From DigitalOcean Dashboard:
1. Click **Create → Droplet**
2. Choose:
   - **Ubuntu 24.04 LTS**
   - **Basic Plan** → **Regular with SSD** → **$12/month** (Choose the droplet with 2 GB RAM)
3. **Choose a hostname**: `churchinventory` (this will help with SSL certs)
4. **Authentication**: Password (create your own strong password)
5. Click **Create Droplet**
6. Wait ~1 minute, then note your **Droplet IP address**

---

## 3. Configure DuckDNS
1. Go to [duckdns.org](https://duckdns.org)
2. Sign in with your preferred method (GitHub, Google, etc.)
3. On the main page:
   - In the domain field, type: `churchinventory` (without .duckdns.org)
   - Click **Add Domain**
4. Once domain appears, update the IP address:
   - Enter your Droplet's IP address
   - Click **Update IP**
5. Keep this page open or note down your **DuckDNS Token** (click "token" link)

---

## 4. Connect to Droplet
1. Once Droplet is created, just use **Access console**
2. Then click **Launch Droplet Console**

---

## 5. Initial Server Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Set proper hostname (helps with SSL)
sudo hostnamectl set-hostname churchinventory

# Install Python 3.13
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev python3-pip python3-certbot-nginx

# Install other software and tools
sudo apt install -y curl git mysql-server libmysqlclient-dev build-essential pkg-config libssl-dev nginx certbot

```

---

## 6. Configure MySQL
```bash
# Update package list
sudo apt update

# Start and enable MySQL
sudo systemctl start mysql
sudo systemctl enable mysql

# Secure MySQL installation
sudo mysql_secure_installation
# Follow prompts: Set root password, remove anonymous users, etc.
```

---

## 7. Configure DuckDNS Automatic Updates
```bash
# Create directory for DuckDNS updater
mkdir -p ~/duckdns
cd ~/duckdns

# Create update script (replace YOUR_TOKEN with actual token)
cat > duck.sh << 'EOF'
#!/bin/bash
echo url="https://www.duckdns.org/update?domains=churchinventory&token=YOUR_TOKEN&ip=" | curl -k -o ~/duckdns/duck.log -K -
EOF

# Make it executable
chmod 700 duck.sh

# Test the script
./duck.sh

# Check log
cat duck.log

# Set up cron job to update every 5 minutes
(crontab -l 2>/dev/null; echo "*/5 * * * * ~/duckdns/duck.sh >/dev/null 2>&1") | crontab -
```

---

## 8. Create Database and User
```bash
# Log into MySQL
sudo mysql -u root -p
# Enter the root password you set during secure installation
```

```sql
-- Create database
CREATE DATABASE inventory_management_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user (use a STRONG password!)
CREATE USER 'inv_user'@'localhost' IDENTIFIED BY 'StrongPassword123!';

-- Grant privileges
GRANT ALL PRIVILEGES ON inventory_management_db.* TO 'inv_user'@'localhost';

-- Apply changes
FLUSH PRIVILEGES;

-- Exit
EXIT;
```

---

## 9. Set Up Project
```bash
# Clone repository
cd /root
git clone https://github.com/stephen-cpe/inventory_management_system.git
cd inventory_management_system

# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn mysqlclient
```

---

## 10. Initialize Database Schema
```bash
# Import schema
mysql -u inv_user -pStrongPassword123! inventory_management_db < init_db.sql
```

---

## 11. Configure Environment File
```bash
# Create .env file
nano .env
```

Add (adjust passwords as needed):
```ini
SECRET_KEY=YourSuperSecretVeryLongKeyChangeThis123!
DATABASE_URL=mysql+pymysql://inv_user:StrongPassword123!@localhost/inventory_management_db
LOG_LEVEL=INFO
FLASK_APP=app.py
FLASK_DEBUG=False
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

---

## 12. Run Migrations and Create Admin
```bash
# Load environment variables
export $(cat .env | xargs)

# Run migrations
flask db init
flask db upgrade

# Create admin user
flask create-admin
# When prompted, use admin/admin123 or your custom credentials
```

---

## 13. Create Systemd Service
```bash
# Create service file
sudo nano /etc/systemd/system/inventory-app.service
```

Add:
```ini
[Unit]
Description=Inventory Management System
After=network.target mysql.service

[Service]
User=root
Group=www-data
WorkingDirectory=/root/inventory_management_system
EnvironmentFile=/root/inventory_management_system/.env
ExecStart=/root/inventory_management_system/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable inventory-app
sudo systemctl start inventory-app

# Check status
sudo systemctl status inventory-app
```

---

## 14. Configure Nginx with Let's Encrypt SSL

### Step 1: Create Basic Nginx Config
```bash
# Create Nginx config
sudo nano /etc/nginx/sites-available/inventory-app
```

Add:
```nginx
server {
    listen 80;
    server_name churchinventory.duckdns.org;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/inventory-app /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test config
sudo nginx -t

# Start Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 15. Obtain Let's Encrypt SSL Certificate
```bash
# 1) First run WITHOUT --redirect (more reliable)
sudo certbot --nginx -d churchinventory.duckdns.org --email youremail@address.com --agree-tos

# 2) Then run again WITH --redirect to force HTTP -> HTTPS
sudo certbot --nginx -d churchinventory.duckdns.org --email youremail@address.com --agree-tos --redirect

# Test automatic renewal
sudo certbot renew --dry-run
```

---

## 16. Configure Firewall
```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable

# Check status
sudo ufw status
```

---

## 17. Update DuckDNS Script for Cron (if needed)
If your IP changes, DuckDNS needs to update. Let's improve the script:

```bash
cd ~/duckdns
# Edit the script with your actual token
nano duck.sh
```

Update with your token (looks like: `a7c4d0ad-114e-40aa-ba8d-8f3b9f7c8b9e`):
```bash
#!/bin/bash
# Replace YOUR_TOKEN with your actual DuckDNS token
TOKEN="a7c4d0ad-114e-40aa-ba8d-8f3b9f7c8b9e"
DOMAIN="churchinventory"
echo url="https://www.duckdns.org/update?domains=${DOMAIN}&token=${TOKEN}&ip=" | curl -k -o ~/duckdns/duck.log -K -
```

```bash
# Make executable and test
chmod 700 duck.sh
./duck.sh
cat duck.log  # Should say "OK"
```

---

## 18. Final Configuration Check
```bash
# Verify services are running
sudo systemctl status inventory-app
sudo systemctl status nginx
sudo systemctl status mysql

# Check Nginx config
sudo nginx -t

# Check SSL certificate
sudo certbot certificates

# Test application
curl -I https://churchinventory.duckdns.org
```

---

## 19. Access Application
1. Open browser
2. Go to: `https://churchinventory.duckdns.org`
3. **No security warnings** (valid SSL certificate!)
4. Login with admin credentials (default: admin/admin123)

---

## 20. Monitoring and Maintenance

### Check Logs
```bash
# Application logs
sudo journalctl -u inventory-app -f

# Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Nginx access logs
sudo tail -f /var/log/nginx/access.log
```

### Update Application
```bash
cd /root/inventory_management_system
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart inventory-app
```

### Renew SSL Certificate (auto-handled, but can force)
```bash
# Check renewal status
sudo certbot renew --dry-run

# Force renewal if needed
sudo certbot renew --force-renewal
```

### Backup Database
```bash
# Backup
mysqldump -u inv_user -pStrongPassword123! inventory_management_db > backup.sql

# Restore
mysql -u inv_user -pStrongPassword123! inventory_management_db < backup.sql
```

---

## 21. Troubleshooting

### If SSL certificate fails:
```bash
# Check if DuckDNS resolves correctly
nslookup churchinventory.duckdns.org

# Check certbot logs
sudo tail -f /var/log/letsencrypt/letsencrypt.log

# Retry certbot
sudo certbot --nginx -d churchinventory.duckdns.org --force-renewal
```

### If application doesn't load:
```bash
# Check all services
sudo systemctl status inventory-app
sudo systemctl status nginx
sudo systemctl status mysql

# Check if port 5000 is listening
sudo netstat -tulpn | grep :5000

# Check firewall
sudo ufw status
```

### If DuckDNS stops updating:
```bash
# Test the update script manually
cd ~/duckdns
./duck.sh
cat duck.log

# Check cron job
crontab -l

# Manual update via browser:
# https://www.duckdns.org/update?domains=churchinventory&token=YOUR_TOKEN&ip=
```

---

## 22. Security Hardening (Optional)

```bash
# Change SSH port (edit /etc/ssh/sshd_config)
sudo nano /etc/ssh/sshd_config
# Change Port 22 to something else (e.g., 2222)
sudo systemctl restart sshd

# Install fail2ban for SSH protection
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---


**Your application is now live at:** `https://churchinventory.duckdns.org`
