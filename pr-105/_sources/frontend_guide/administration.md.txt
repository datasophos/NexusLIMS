(cdcs-administration)=
# Administration

This guide covers day-to-day administration tasks for NexusLIMS-CDCS including backups, XSLT management, user administration, and monitoring.

## Admin Commands Overview

Load admin commands before running any administrative task:

```bash
cd /path/to/NexusLIMS-CDCS/deployment
source admin-commands.sh
```

### Command Summary

| Command | Description |
|---------|-------------|
| `dc-prod` | Docker Compose alias for production stack |
| `admin-backup` | Backup all CDCS data |
| `admin-restore <dir>` | Restore from backup directory |
| `admin-db-dump` | Create PostgreSQL database dump |
| `admin-db-restore <file>` | Restore database from dump |
| `admin-list-users` | List all users with status |
| `admin-export-users` | Export users to JSON |
| `admin-import-users <file>` | Import users from JSON |
| `admin-stats` | Show system statistics |
| `admin-init` | Initialize environment (superuser, schema, XSLT) |

---

## Backup and Restore

### Understanding Backup Types

NexusLIMS-CDCS supports two backup approaches:

| Type | Command | Use Case |
|------|---------|----------|
| **Application Backup** | `admin-backup` | Regular backups, includes all data |
| **Database Dump** | `admin-db-dump` | Disaster recovery, PostgreSQL raw dump |

**Recommendation**: Use `admin-backup` for regular backups. Use `admin-db-dump` only for disaster recovery scenarios.

### Application Backup

Application backups include:
- Templates (XSD schemas)
- Data records (XML documents)
- Binary blobs (uploaded files)
- Users (Django fixtures)
- XSLT stylesheets
- Persistent queries

```bash
source admin-commands.sh
admin-backup
```

**Output:**

```text
→ Starting CDCS backup...
→ Exporting templates...
✓ Exported 1 templates to /srv/nexuslims/backups/backup_20260115_143022/templates/
→ Exporting records...
✓ Exported 42 records to /srv/nexuslims/backups/backup_20260115_143022/records/
→ Exporting blobs...
✓ Exported 128 blobs to /srv/nexuslims/backups/backup_20260115_143022/blobs/
→ Exporting users...
✓ Exported 5 users to /srv/nexuslims/backups/backup_20260115_143022/users.json
→ Exporting XSLT...
✓ Exported 2 stylesheets to /srv/nexuslims/backups/backup_20260115_143022/xslt/
✓ Backup completed: /srv/nexuslims/backups/backup_20260115_143022/
```

Backups are stored at the path configured in `NX_CDCS_BACKUPS_HOST_PATH` (default: `/opt/nexuslims/backups/`).

### Restoring from Backup

```bash
source admin-commands.sh
admin-restore /opt/nexuslims/backups/backup_20260115_143022
```

The restore command:
1. Imports templates
2. Imports records
3. Imports blobs
4. Imports users
5. Imports XSLT stylesheets

### Database Dump (Disaster Recovery)

For complete disaster recovery, create a PostgreSQL dump:

```bash
source admin-commands.sh
admin-db-dump
```

Creates a SQL file at `$NX_CDCS_BACKUPS_HOST_PATH/db_backup_YYYYMMDD_HHMMSS.sql`

### Database Restore (Disaster Recovery)

```{warning}
Database restore will **DROP and RECREATE** the entire database. All existing data will be lost!
```

```bash
source admin-commands.sh
admin-db-restore /opt/nexuslims/backups/db_backup_20260115_143022.sql
```

The command requires two confirmations before proceeding.

### Automated Backup Schedule

Set up a cron job for automated backups:

```bash
# Create backup script
cat > /opt/nexuslims-backup.sh << 'EOF'
#!/bin/bash
set -e
cd /opt/nexuslims/NexusLIMS-CDCS/deployment
source admin-commands.sh
admin-backup
admin-db-dump

# Cleanup old backups (30 days)
find /opt/nexuslims/backups -type d -name "backup_*" -mtime +30 -exec rm -rf {} \; 2>/dev/null || true
find /opt/nexuslims/backups -type f -name "db_backup_*.sql" -mtime +30 -delete 2>/dev/null || true
EOF

chmod +x /opt/nexuslims-backup.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/nexuslims-backup.sh") | crontab -
```

---

## XSLT Stylesheet Management

```{important}
XSLT stylesheets are stored in the Django database. Editing the `.xsl` files alone is not enough - you must update the database.
```

### XSLT Files

| File | Purpose |
|------|---------|
| `xslt/detail_stylesheet.xsl` | Full record view (single record page) |
| `xslt/list_stylesheet.xsl` | Search result cards (list view) |

### Update Process

1. **Edit the XSL file** in the `xslt/` directory
2. **Update the database**:

**Development:**
```bash
source dev-commands.sh
dev-update-xslt
```

**Production:**
```bash
# Re-run initialization (uploads XSLT along with schema)
docker exec -it nexuslims_prod_cdcs python /srv/scripts/init_environment.py
```

Or use the update script directly:
```bash
docker exec nexuslims_prod_cdcs bash /srv/scripts/update-xslt.sh
```

### URL Patching

XSLT stylesheets contain URLs for linking to instrument data and preview images. These are automatically patched from environment variables:

- `XSLT_DATASET_BASE_URL` → links to instrument data files
- `XSLT_PREVIEW_BASE_URL` → links to preview images

See {doc}`configuration` for details.

### Verifying XSLT Updates

After updating, verify in the web interface:
1. Navigate to any record
2. Check that links to data files and images work correctly
3. Inspect the HTML source to confirm URLs are correct

---

## Schema Management

### Schema File Location

The NexusLIMS schema (`nexus-experiment.xsd`) is located at:
- Repository: `deployment/schemas/nexus-experiment.xsd`
- Container: `/srv/nexuslims/schemas/nexus-experiment.xsd`

### Updating the Schema

1. **Download latest schema** from the NexusLIMS repository:
   ```bash
   cd deployment
   bash scripts/update-schema.sh
   ```

2. **Apply to database** by re-running initialization:
   ```bash
   docker exec -it nexuslims_prod_cdcs python /srv/scripts/init_environment.py
   ```

```{note}
Schema updates create a new template version. Existing records remain valid against their original template version.
```

---

## User Management

### List Users

```bash
source admin-commands.sh
admin-list-users
```

**Output:**
```
admin (admin@example.com) - Active: True, Admin: True
jsmith (jane.smith@example.com) - Active: True, Admin: False
```

### Export Users

Export all users to JSON for backup or migration:

```bash
admin-export-users
# Creates: /opt/nexuslims/backups/users_YYYYMMDD_HHMMSS.json
```

### Import Users

Import users from a JSON fixture:

```bash
admin-import-users /opt/nexuslims/backups/users_20260115_143022.json
```

### Create Superuser

To create an additional superuser:

```bash
docker exec -it nexuslims_prod_cdcs python manage.py createsuperuser
```

### Reset User Password

```bash
docker exec -it nexuslims_prod_cdcs python manage.py changepassword username
```

---

## Monitoring

### System Statistics

```bash
source admin-commands.sh
admin-stats
```

**Output:**
```
============================================================
NexusLIMS-CDCS System Statistics
============================================================

Users:
  Total:      5
  Active:     5
  Superusers: 1

Templates:
  Total: 1
    - Nexus Experiment Schema (Version 1)

Data Records:
  Total: 42

XSLT Stylesheets:
  Total: 2
    - detail_stylesheet.xsl
    - list_stylesheet.xsl

============================================================
```

### Container Health

```bash
dc-prod ps
```

All services should show `Up` and `healthy`.

### View Logs

```bash
# All services
dc-prod logs -f

# Specific service
dc-prod logs -f cdcs
dc-prod logs -f postgres
dc-prod logs -f caddy
```

### Resource Usage

```bash
docker stats
```

### Database Queries

For advanced troubleshooting, access the PostgreSQL shell:

```bash
docker exec -it nexuslims_prod_cdcs_postgres psql -U nexuslims nexuslims
```

Example queries:
```sql
-- Active connections
SELECT pid, query, state FROM pg_stat_activity WHERE state != 'idle';

-- Table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;

-- Vacuum stats
SELECT relname, last_vacuum, last_analyze FROM pg_stat_user_tables;
```

---

## Maintenance Tasks

### Clear Expired Sessions

```bash
docker exec nexuslims_prod_cdcs python manage.py clearsessions
```

### Clear Redis Cache

```bash
docker exec nexuslims_prod_cdcs_redis redis-cli -a $REDIS_PASS FLUSHDB
```

### Optimize Database

```bash
docker exec nexuslims_prod_cdcs_postgres vacuumdb -U nexuslims --all --full --analyze
```

### Restart Services

```bash
source admin-commands.sh
dc-prod restart
```

Or restart specific services:
```bash
dc-prod restart cdcs
dc-prod restart caddy
```

---

## Service Management

### Start/Stop Services

```bash
source admin-commands.sh

# Stop all services
dc-prod down

# Start all services
dc-prod up -d

# Stop specific service
dc-prod stop cdcs

# Start specific service
dc-prod start cdcs
```

### Update Images

Pull latest images and restart:

```bash
dc-prod pull
dc-prod up -d
```

### View Configuration

Verify the resolved Docker Compose configuration:

```bash
dc-prod config
```

---

## Next Steps

- {doc}`troubleshooting` - Common issues and solutions
- {doc}`production` - Production deployment guide
- {doc}`configuration` - Environment variable reference
