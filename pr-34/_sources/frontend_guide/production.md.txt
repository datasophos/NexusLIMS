(cdcs-production)=
# Production Deployment

This guide covers deploying NexusLIMS-CDCS to a production environment with proper security, SSL certificates, and data management.

## Prerequisites

### Required Knowledge

- Linux system administration
- Docker and Docker Compose
- Basic understanding of DNS and SSL/TLS certificates
- Basic PostgreSQL database administration
- Web server/reverse proxy concepts

### Required Access

- Root or sudo access to production server
- DNS management for your domain
- (Optional) CIFS/SMB or NFS for data files
- (Optional) SMTP server for application notifications

---

## System Requirements

### Minimum Hardware

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **CPU** | 4 cores | 8 cores |
| **RAM** | 8 GB | 16 GB |
| **Disk** | 20 GB SSD | 100+ GB SSD |
| **Network** | 100 Mbps | 1 Gbps |

### Software Requirements

| Software | Version |
|----------|---------|
| **OS** | Ubuntu 22.04 LTS or RHEL 8+ |
| **Docker** | 24.0+ |
| **Docker Compose** | 2.20+ |
| **Git** | 2.0+ |

### Network Requirements

- **Firewall**: Ports 80 and 443 open (for ACME certificate validation)
- **DNS**: Ability to create A records pointing to your server
- **Optional**: Firewall rules for database ports if external access needed

---

## Pre-Deployment Checklist

Before deploying, ensure you have:

- Production server provisioned and accessible via SSH
- Domain name(s) registered and DNS configured
- SSL certificate strategy determined (either self-managed certs or automatic ACME/Let's Encrypt)
- Data storage locations identified and accessible
- Backup strategy planned
- Strong passwords generated for database and Redis
- Django secret key generated (minimum 50 characters)
- (Optional) SMTP server configured for email notifications

---

## Domain and DNS Setup

### Required DNS Records

You need two subdomains (replace `nexuslims.example.com` with your domain):

1. **Main application**: `nexuslims.example.com`
2. **File server**: `files.nexuslims.example.com`

### DNS Configuration

Create A records pointing to your server's public IP:

```
nexuslims.example.com.       A    203.0.113.42
files.nexuslims.example.com. A    203.0.113.42
```

### Verify DNS Propagation

Before deployment, verify DNS is working:

```bash
dig nexuslims.example.com
dig files.nexuslims.example.com
```

Both should return your server's IP address.

---

## SSL Certificate Options

### Option 1: Automatic ACME (Recommended)

**Best for**: Production deployments with public network access

Caddy automatically obtains and renews certificates from Let's Encrypt:

1. Set `CADDY_ACME_EMAIL` in your `.env` file
2. Ensure ports 80 and 443 are accessible from the internet
3. Caddy handles everything else automatically

**Advantages:**
- Fully automated certificate issuance and renewal
- Free certificates from Let's Encrypt
- Trusted by all browsers
- No manual intervention required

### Option 2: Manual Certificates

**Best for**: Organizations with existing PKI or certificate vendors

1. Obtain certificates from your CA (you need `fullchain.pem` and `privkey.pem`)

2. Create certificate directory and copy certificates:
   ```bash
   mkdir -p /opt/nexuslims/certs
   chmod 700 /opt/nexuslims/certs
   cp fullchain.pem /opt/nexuslims/certs/
   cp privkey.pem /opt/nexuslims/certs/
   chmod 600 /opt/nexuslims/certs/*
   ```

3. Set the certificate path in your `.env` file:
   ```bash
   CADDY_CERTS_HOST_PATH=/opt/nexuslims/certs
   ```

   The `docker-compose.prod.yml` already includes a volume mount that uses this variable:
   ```yaml
   - ${CADDY_CERTS_HOST_PATH}:/etc/caddy/certs:ro
   ```

4. Update `caddy/Caddyfile.prod` to use the certificates:
   ```text
   https://{$DOMAIN} {
       tls /etc/caddy/certs/fullchain.pem /etc/caddy/certs/privkey.pem
       # ... rest of config
   }

   https://{$FILES_DOMAIN} {
       tls /etc/caddy/certs/fullchain.pem /etc/caddy/certs/privkey.pem
       # ... rest of config
   }
   ```

```{note}
When using manual certificates, you are responsible for renewing them before expiration.
```

---

## Environment Configuration

### 1. Clone Repository

```bash
sudo mkdir -p /opt/nexuslims
cd /opt/nexuslims
git clone https://github.com/datasophos/NexusLIMS-CDCS.git
cd NexusLIMS-CDCS/deployment
```

### 2. Create Environment File

```bash
cp .env.prod.example .env
chmod 600 .env
```

### 3. Configure Environment Variables

Edit `.env` with your production values. See {doc}`configuration` for detailed documentation of all variables.

**Critical variables to set:**

```bash
# Domain configuration
DOMAIN=nexuslims.example.com
FILES_DOMAIN=files.nexuslims.example.com

# Security (generate strong values!)
SECRET_KEY=your-50-character-minimum-secret-key
POSTGRES_PASS=strong-database-password
REDIS_PASS=strong-redis-password

# ACME certificate email
CADDY_ACME_EMAIL=admin@example.com

# File paths (adjust to your storage locations)
NX_DATA_HOST_PATH=/mnt/nexuslims/data
NX_INSTRUMENT_DATA_HOST_PATH=/mnt/nexuslims/instrument-data
NX_CDCS_BACKUPS_HOST_PATH=/opt/nexuslims/backups
```

```{warning}
Never commit `.env` to version control! It contains secrets.
```

---

## File Storage Setup

NexusLIMS-CDCS serves two types of files:
- **NexusLIMS data**: Thumbnail images, metadata files
- **Instrument data**: Raw microscopy data files

### Option 1: Local Storage

```bash
sudo mkdir -p /mnt/nexuslims/data
sudo mkdir -p /mnt/nexuslims/instrument-data
sudo chown -R $USER:$USER /mnt/nexuslims
sudo chmod -R 755 /mnt/nexuslims
```

### Option 2: NFS Mount

```bash
# Install NFS client
sudo apt-get install nfs-common  # Ubuntu/Debian

# Create mount points
sudo mkdir -p /mnt/nexuslims/data
sudo mkdir -p /mnt/nexuslims/instrument-data

# Mount NFS shares
sudo mount -t nfs nfs-server:/export/nexuslims/data /mnt/nexuslims/data
sudo mount -t nfs nfs-server:/export/nexuslims/instrument-data /mnt/nexuslims/instrument-data

# Add to /etc/fstab for persistence
echo "nfs-server:/export/nexuslims/data /mnt/nexuslims/data nfs defaults 0 0" | sudo tee -a /etc/fstab
echo "nfs-server:/export/nexuslims/instrument-data /mnt/nexuslims/instrument-data nfs defaults 0 0" | sudo tee -a /etc/fstab
```

### Option 3: CIFS/SMB Mount

```bash
# Install CIFS utilities
sudo apt-get install cifs-utils  # Ubuntu/Debian

# Create credentials file
sudo mkdir -p /etc/smbcredentials
sudo touch /etc/smbcredentials/nexuslims.cred
sudo chmod 600 /etc/smbcredentials/nexuslims.cred

sudo tee /etc/smbcredentials/nexuslims.cred > /dev/null << EOF
username=your_smb_username
password=your_smb_password
domain=WORKGROUP
EOF

# Create mount points and mount
sudo mkdir -p /mnt/nexuslims/data
sudo mkdir -p /mnt/nexuslims/instrument-data

sudo mount -t cifs //nas-server/nexuslims-data /mnt/nexuslims/data \
  -o credentials=/etc/smbcredentials/nexuslims.cred,uid=$(id -u),gid=$(id -g)

sudo mount -t cifs //nas-server/nexuslims-instrument-data /mnt/nexuslims/instrument-data \
  -o credentials=/etc/smbcredentials/nexuslims.cred,uid=$(id -u),gid=$(id -g)
```

---

## Deployment

### 1. Load Admin Commands

```bash
cd /opt/nexuslims/NexusLIMS-CDCS/deployment
source admin-commands.sh
```

This provides the `dc-prod` alias (shortcut for `docker compose -f docker-compose.base.yml -f docker-compose.prod.yml`).

### 2. Build and Pull Images

```bash
dc-prod build  # Build CDCS and Caddy images
dc-prod pull   # Pull PostgreSQL and Redis images
```

### 3. Start Services

```bash
dc-prod up -d
```

### 4. Monitor Startup

```bash
# Watch logs
dc-prod logs -f

# Check service status
dc-prod ps
```

All services should show `Up` and `healthy`.

### 5. Verify Certificate Acquisition

If using ACME, watch Caddy logs for certificate issuance:

```bash
dc-prod logs -f caddy
```

You should see: `certificate obtained successfully`

---

## Post-Deployment Setup

### 1. Run Initialization Script

The initialization script sets up the superuser, schema, and XSLT stylesheets:

```bash
admin-init
```

This will:
1. Verify database migrations are complete
2. Create superuser (prompts for credentials)
3. Upload NexusLIMS schema
4. Load and configure XSLT stylesheets
5. Load data exporters

### 2. Verify Installation

```bash
admin-stats
```

Expected output:
```
============================================================
NexusLIMS-CDCS System Statistics
============================================================

Users:
  Total:      1
  Superusers: 1

Templates:
  Total: 1
    - Nexus Experiment Schema (Version 1)

XSLT Stylesheets:
  Total: 2
    - detail_stylesheet.xsl
    - list_stylesheet.xsl

============================================================
```

### 3. Test File Serving

Navigate to:
- `https://files.nexuslims.example.com/data/`
- `https://files.nexuslims.example.com/instrument-data/`

Both should show directory listings.

### 4. Create Backup Directory

```bash
sudo mkdir -p /opt/nexuslims/backups
sudo chown $USER:$USER /opt/nexuslims/backups
```

```{important}
The backup directory must be owned by the user running Docker, not root. Otherwise backup scripts will fail with permission errors.
```

Restart services to pick up the mount:
```bash
dc-prod down
dc-prod up -d
```

### 5. Configure Automated Backups

Create a daily backup script:

```bash
cat > /opt/nexuslims-backup.sh << 'EOF'
#!/bin/bash
set -e

cd /opt/nexuslims/NexusLIMS-CDCS/deployment
source admin-commands.sh

# Run backup
admin-backup

# Also create a database dump
admin-db-dump

# Remove backups older than 30 days
find /opt/nexuslims/backups -type d -name "backup_*" -mtime +30 -exec rm -rf {} \; 2>/dev/null || true
find /opt/nexuslims/backups -type f -name "backup_*.sql" -mtime +30 -delete 2>/dev/null || true
EOF

chmod +x /opt/nexuslims-backup.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/nexuslims-backup.sh") | crontab -
```

---

## Security Hardening

### Firewall Configuration

**UFW (Ubuntu):**
```bash
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP (for ACME)
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

**firewalld (RHEL):**
```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
```

### Database Security

- Don't expose PostgreSQL port externally unless necessary
- Use strong passwords (already set in `.env`)
- Keep PostgreSQL container updated

### Container Security

Keep images updated regularly:
```bash
dc-prod pull
dc-prod up -d
```

### Log Rotation

Configure Docker log rotation in `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Restart Docker: `sudo systemctl restart docker`

---

## Upgrading

### Application Updates

1. **Backup current deployment:**
   ```bash
   source admin-commands.sh
   admin-backup
   ```

2. **Pull latest code:**
   ```bash
   cd /opt/nexuslims/NexusLIMS-CDCS
   git fetch
   git checkout v3.19.0  # or desired version
   ```

3. **Review changelog** for breaking changes

4. **Check for new environment variables** in `.env.prod.example`

5. **Rebuild and restart:**
   ```bash
   cd deployment
   source admin-commands.sh
   dc-prod build
   dc-prod down
   dc-prod up -d
   ```

6. **Run migrations:**
   ```bash
   docker exec nexuslims_prod_cdcs python manage.py migrate
   ```

### Rollback

If upgrade fails:

```bash
dc-prod down
git checkout v3.18.0  # Previous version
cd deployment
dc-prod build
dc-prod up -d
```

If database schema changed, restore from backup:
```bash
admin-db-restore /opt/nexuslims/backups/backup_20260109_120000.sql
```

---

## Next Steps

- {doc}`configuration` - Detailed environment variable reference
- {doc}`administration` - Backup, restore, and maintenance procedures
- {doc}`troubleshooting` - Common issues and solutions
- {doc}`local-https-testing` - Test production config locally before deploying
