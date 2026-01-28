(cdcs-local-https-testing)=
# Local HTTPS Testing

This guide explains how to set up a local production-like environment with HTTPS for testing production deployment procedures before deploying to a real server.

## Overview

Testing production configurations locally helps you:
- Validate your `.env` settings before deployment
- Test backup and restore procedures
- Verify SSL certificate configuration
- Practice upgrade and rollback procedures
- Debug issues in a safe environment

## Prerequisites

- Docker Desktop or Docker Engine with Compose
- [mkcert](https://github.com/FiloSottile/mkcert) for generating trusted local certificates
- Access to edit `/etc/hosts`

---

## Setup Steps

### 1. Install mkcert

`````{tab-set}

````{tab-item} macOS
```bash
brew install mkcert
brew install nss  # Firefox support
mkcert -install
```
````

````{tab-item} Linux
```bash
# Ubuntu/Debian
sudo apt install libnss3-tools
# Download mkcert from https://github.com/FiloSottile/mkcert/releases
sudo mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert
sudo chmod +x /usr/local/bin/mkcert
mkcert -install
```
````

````{tab-item} Windows
```powershell
choco install mkcert
mkcert -install
```
````

`````

### 2. Generate Certificates

Create certificates for your test domain:

```bash
sudo mkdir -p /opt/nexuslims/local-certs
sudo chown $USER:staff /opt/nexuslims/local-certs

cd /opt/nexuslims/local-certs
mkcert \
  "nexuslims-local.test" \
  "files.nexuslims-local.test" \
  "localhost" \
  "127.0.0.1" \
  "::1"
```

This creates:
- `nexuslims-local.test+4.pem` (certificate)
- `nexuslims-local.test+4-key.pem` (private key)

### 3. Update /etc/hosts

Redirect the test domains to localhost:

```bash
sudo tee -a /etc/hosts << EOF
127.0.0.1 nexuslims-local.test
127.0.0.1 files.nexuslims-local.test
EOF
```

### 4. Create Backup Directory

```bash
sudo mkdir -p /opt/nexuslims/backups
sudo chown $USER:staff /opt/nexuslims/backups
```

### 5. Configure Environment

```bash
cd /path/to/NexusLIMS-CDCS/deployment
cp .env.prod.example .env
```

Edit `.env` with local test values:

```bash
# Domain configuration
DOMAIN=nexuslims-local.test
FILES_DOMAIN=files.nexuslims-local.test

# Certificate paths
CADDY_CERTS_HOST_PATH=/opt/nexuslims/local-certs

# File paths (adjust to match your setup)
NX_DATA_HOST_PATH=/mnt/nexuslims/data
NX_INSTRUMENT_DATA_HOST_PATH=/mnt/nexuslims/instrument-data
NX_CDCS_BACKUPS_HOST_PATH=/opt/nexuslims/backups
```

### 6. Start Services

```bash
source admin-commands.sh
dc-prod up -d
admin-init   # Set up superuser, schema, XSLT
```

---

## Testing Production Procedures

With this setup, you can now test all production procedures from the {doc}`production` guide.

### Test Access

Navigate to:
- `https://nexuslims-local.test` - Main application
- `https://files.nexuslims-local.test/data/` - File server

### Test Backups

```bash
source admin-commands.sh
admin-backup

# Check backup was created
ls -la /opt/nexuslims/backups/
```

### Test Database Operations

```bash
source admin-commands.sh

# Create a database dump
admin-db-dump

# View statistics
admin-stats
```

### Verify SSL Certificate

```bash
# Verify HTTPS is working with trusted certificate
curl -I https://nexuslims-local.test

# Check certificate details
openssl s_client -connect nexuslims-local.test:443 \
  -servername nexuslims-local.test < /dev/null 2>/dev/null | \
  openssl x509 -noout -dates -issuer
```

---

## Stopping the Environment

```bash
cd deployment
source admin-commands.sh
dc-prod down
```

---

## Cleanup

To completely remove the local test environment:

```bash
# Stop containers and remove volumes
cd deployment
source admin-commands.sh
dc-prod down -v

# Remove certificates
sudo rm -rf /opt/nexuslims/local-certs

# Remove backups
sudo rm -rf /opt/nexuslims/backups

# Remove /etc/hosts entries
sudo sed -i.bak '/nexuslims-local.test/d' /etc/hosts
```

---

## Differences from Production

This local test environment differs from real production in these ways:

| Aspect | Local Test | Production |
|--------|-----------|------------|
| **Certificates** | mkcert (local CA) | Let's Encrypt (ACME) |
| **Domains** | `.test` TLD | Real domains |
| **DNS** | `/etc/hosts` | Real DNS |
| **Data** | Test data or empty | Production data |
| **Passwords** | Simple test values | Strong passwords |

---

## Troubleshooting

### Certificate Not Trusted

If browsers show "not secure":

```bash
# Reinstall mkcert CA
mkcert -install

# Restart browser
```

### Cannot Access URLs

Check `/etc/hosts`:
```bash
cat /etc/hosts | grep nexuslims
```

Should show:
```
127.0.0.1 nexuslims-local.test
127.0.0.1 files.nexuslims-local.test
```

### Port Already in Use

If ports 80/443 are in use:
```bash
# Find what's using the ports
sudo lsof -i :80
sudo lsof -i :443

# Stop the conflicting service
```

---

## Next Steps

Once your local HTTPS test environment is working:

1. Walk through each section of the {doc}`production` guide
2. Test backup and restore procedures
3. Practice upgrade and rollback workflows
4. Document any issues for your production deployment
