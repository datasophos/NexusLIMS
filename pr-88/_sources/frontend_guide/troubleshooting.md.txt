(cdcs-troubleshooting)=
# Troubleshooting

This guide covers common issues and their solutions for NexusLIMS-CDCS deployments.

## Quick Diagnostics

Before diving into specific issues, gather diagnostic information:

```bash
cd /path/to/NexusLIMS-CDCS/deployment
source admin-commands.sh

# Check service status
dc-prod ps

# View recent logs
dc-prod logs --tail=100

# Check system stats
admin-stats
```

---

## Certificate Issues

### Problem: "Certificate not trusted" or SSL warnings

**In Development:**

The development environment uses a local CA. Trust the certificate:

`````{tab-set}

````{tab-item} macOS
```bash
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain caddy/certs/ca.crt
```
````

````{tab-item} Linux
```bash
sudo cp caddy/certs/ca.crt /usr/local/share/ca-certificates/nexuslims-dev-ca.crt
sudo update-ca-certificates
```
````

`````

**In Production (ACME/Let's Encrypt):**

1. **Verify DNS points to server:**
   ```bash
   dig nexuslims.example.com
   ```

2. **Check Caddy logs for certificate errors:**
   ```bash
   dc-prod logs caddy | grep -i cert
   ```

3. **Verify ports 80 and 443 are accessible:**
   ```bash
   sudo netstat -tlnp | grep -E ':(80|443)'
   ```

4. **Test ACME challenge endpoint:**
   ```bash
   curl http://nexuslims.example.com/.well-known/acme-challenge/test
   ```

### Problem: Certificate renewal failing

ACME certificates auto-renew. If renewal fails:

1. **Check Caddy data volume:**
   ```bash
   docker volume inspect nexuslims_prod_caddy_data
   ```

2. **Force certificate renewal:**
   ```bash
   dc-prod restart caddy
   ```

3. **Verify ACME email is set:**
   ```bash
   grep CADDY_ACME_EMAIL .env
   ```

---

## Database Issues

### Problem: "FATAL: password authentication failed"

1. **Verify password in `.env`:**
   ```bash
   grep POSTGRES_PASS .env
   ```

2. **Restart services:**
   ```bash
   dc-prod restart
   ```

3. **If password was changed**, you may need to reset the PostgreSQL data volume:
   ```bash
   dc-prod down -v  # WARNING: Deletes all data!
   dc-prod up -d
   ```

### Problem: Database connection timeout

1. **Check PostgreSQL is running:**
   ```bash
   dc-prod ps postgres
   ```

2. **View PostgreSQL logs:**
   ```bash
   dc-prod logs postgres
   ```

3. **Check container health:**
   ```bash
   docker inspect nexuslims_prod_cdcs_postgres | grep -A 10 Health
   ```

### Problem: Database disk full

1. **Check disk usage:**
   ```bash
   docker system df
   df -h
   ```

2. **Vacuum the database:**
   ```bash
   docker exec nexuslims_prod_cdcs_postgres vacuumdb -U nexuslims --all --full
   ```

3. **Clean up Docker resources:**
   ```bash
   docker system prune -f
   ```

---

## File Serving Issues

### Problem: 404 errors on file server

1. **Verify file paths in `.env`:**
   ```bash
   echo "Data path: $NX_DATA_HOST_PATH"
   echo "Instrument data path: $NX_INSTRUMENT_DATA_HOST_PATH"
   ```

2. **Check directories exist and have correct permissions:**
   ```bash
   ls -la $NX_DATA_HOST_PATH
   ls -la $NX_INSTRUMENT_DATA_HOST_PATH
   ```

3. **Verify mounts in container:**
   ```bash
   docker exec nexuslims_prod_cdcs ls -la /srv/nx-data
   docker exec nexuslims_prod_cdcs ls -la /srv/nx-instrument-data
   ```

### Problem: Permission denied errors

1. **Check directory ownership:**
   ```bash
   ls -la /mnt/nexuslims/
   ```

2. **Fix permissions (if needed):**
   ```bash
   sudo chown -R $USER:$USER /mnt/nexuslims/
   sudo chmod -R 755 /mnt/nexuslims/
   ```

### Problem: Files not appearing after mount change

Restart services after changing mount paths:

```bash
dc-prod down
dc-prod up -d
```

---

## Application Issues

### Problem: Container exits immediately

1. **Check logs:**
   ```bash
   dc-prod logs cdcs
   ```

2. **Verify environment variables:**
   ```bash
   dc-prod config
   ```

3. **Check health status:**
   ```bash
   docker inspect nexuslims_prod_cdcs | grep -A 10 Health
   ```

### Problem: Application returns 500 errors

1. **Check application logs:**
   ```bash
   dc-prod logs -f cdcs
   ```

2. **Enable Django debug mode temporarily:**
   ```bash
   # In .env
   DJANGO_DEBUG=True

   # Then restart
   dc-prod restart cdcs
   ```

   ```{warning}
   Remember to disable debug mode after troubleshooting!
   ```

3. **Check database connectivity:**
   ```bash
   docker exec nexuslims_prod_cdcs python manage.py check
   ```

### Problem: Slow response times

1. **Check resource usage:**
   ```bash
   docker stats
   ```

2. **Check database performance:**
   ```bash
   docker exec nexuslims_prod_cdcs_postgres psql -U nexuslims -d nexuslims \
     -c "SELECT pid, query, state FROM pg_stat_activity WHERE state != 'idle';"
   ```

3. **Optimize database:**
   ```bash
   docker exec nexuslims_prod_cdcs_postgres vacuumdb -U nexuslims --all --full --analyze
   ```

4. **Consider increasing Gunicorn workers:**
   ```bash
   # In .env
   GUNICORN_WORKERS=8
   GUNICORN_THREADS=4
   ```

---

## XSLT Issues

### Problem: XSLT changes not appearing

XSLT stylesheets are stored in the database. After editing `.xsl` files:

**Development:**
```bash
source dev-commands.sh
dev-update-xslt
```

**Production:**
```bash
docker exec nexuslims_prod_cdcs bash /srv/scripts/update-xslt.sh
```

Then refresh your browser (clear cache if needed).

### Problem: Wrong URLs in rendered HTML

1. **Check XSLT URL configuration:**
   ```bash
   grep XSLT_ .env
   ```

2. **Re-upload XSLT with correct URLs:**
   ```bash
   docker exec nexuslims_prod_cdcs bash /srv/scripts/update-xslt.sh
   ```

### Problem: XSLT parsing errors

Check the XSL file for valid XML:

```bash
xmllint --noout xslt/detail_stylesheet.xsl
xmllint --noout xslt/list_stylesheet.xsl
```

---

## Backup Issues

### Problem: Permission denied when creating backup

The backup directory must be owned by the Docker user:

```bash
sudo chown $USER:$USER /opt/nexuslims/backups
```

On macOS, use `$USER:staff`:
```bash
sudo chown $USER:staff /opt/nexuslims/backups
```

### Problem: Backup directory not found in container

Ensure the backup path is mounted. Check `.env`:

```bash
grep NX_CDCS_BACKUPS_HOST_PATH .env
```

Restart services after setting:
```bash
dc-prod down
dc-prod up -d
```

### Problem: Restore fails with "file not found"

The restore command expects the container path, not host path. Use `admin-restore` which handles path conversion:

```bash
source admin-commands.sh
admin-restore /opt/nexuslims/backups/backup_20260115_143022
```

---

## Network Issues

### Problem: Port already in use

1. **Find what's using the port:**
   ```bash
   sudo lsof -i :80
   sudo lsof -i :443
   ```

2. **Stop the conflicting service** or change ports in `.env`:
   ```bash
   # Use alternative ports
   HTTP_PORT=8080
   HTTPS_PORT=8443
   ```

### Problem: Cannot access from other machines

1. **Check firewall rules:**
   ```bash
   sudo ufw status  # Ubuntu
   sudo firewall-cmd --list-all  # RHEL
   ```

2. **Verify `ALLOWED_HOSTS` includes the hostname/IP:**
   ```bash
   grep ALLOWED_HOSTS .env
   ```

---

## Common Error Messages

### "OperationalError: FATAL: database does not exist"

The database hasn't been created. Either:
1. Start fresh: `dc-prod up -d` (creates database on first run)
2. Or restore from backup: `admin-db-restore <backup.sql>`

### "DisallowedHost at /"

Add the hostname to `ALLOWED_HOSTS` in `.env`:
```bash
ALLOWED_HOSTS=nexuslims.example.com,www.nexuslims.example.com
```

### "CSRF verification failed"

Add the URL to `CSRF_TRUSTED_ORIGINS` in `.env`:
```bash
CSRF_TRUSTED_ORIGINS=https://nexuslims.example.com
```

### "No module named 'config.settings.xxx'"

Verify `DJANGO_SETTINGS_MODULE` in `.env` points to a valid settings file:
```bash
DJANGO_SETTINGS_MODULE=config.settings.prod_settings
```

---

## Getting Help

If you can't resolve an issue:

1. **Gather diagnostic information:**
   ```bash
   dc-prod ps
   dc-prod logs --tail=500 > logs.txt
   admin-stats
   ```

2. **Check for similar issues:**
   [https://github.com/datasophos/NexusLIMS-CDCS/issues](https://github.com/datasophos/NexusLIMS-CDCS/issues)

3. **Open a new issue** with:
   - Description of the problem
   - Steps to reproduce
   - Relevant log output
   - Environment details (OS, Docker version, etc.)

4. **Professional support** is available from [Datasophos](https://datasophos.co)
