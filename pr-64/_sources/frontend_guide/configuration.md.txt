(cdcs-configuration)=
# Configuration

NexusLIMS-CDCS is configured through environment variables defined in a `.env` file. This guide documents all available configuration options.

## Configuration Files

| File | Purpose |
|------|---------|
| `.env.dev` | Development defaults (tracked in git) |
| `.env.prod.example` | Production template (tracked in git) |
| `.env` | Active configuration (gitignored, copy from template) |

**Setup:**
- Development: `cp .env.dev .env`
- Production: `cp .env.prod.example .env` and customize

```{warning}
Never commit `.env` to version control - it contains secrets!
```

---

## Environment Variables Reference

### Project Identification

| Variable | Description | Dev Default | Prod Example |
|----------|-------------|-------------|--------------|
| `COMPOSE_PROJECT_NAME` | Docker Compose project name | `nexuslims_dev` | `nexuslims_prod` |
| `IMAGE_VERSION` | Docker image version tag | `latest` | `3.18.0` |

### Domain Configuration

| Variable | Description | Dev Default | Prod Example |
|----------|-------------|-------------|--------------|
| `DOMAIN` | Main application domain | `nexuslims-dev.localhost` | `nexuslims.example.com` |
| `FILES_DOMAIN` | File server domain | `files.nexuslims-dev.localhost` | `files.nexuslims.example.com` |
| `SERVER_URI` | Full server URL (derived) | `https://${DOMAIN}` | `https://${DOMAIN}` |
| `ALLOWED_HOSTS` | Django allowed hosts | `${DOMAIN}` | `${DOMAIN}` |
| `CSRF_TRUSTED_ORIGINS` | Django CSRF trusted origins | `https://${DOMAIN}` | `https://${DOMAIN}` |

### Django Configuration

| Variable | Description | Dev Default | Prod Example |
|----------|-------------|-------------|--------------|
| `DJANGO_SETTINGS_MODULE` | Settings module path | `config.settings.dev_settings` | `config.settings.prod_settings` |
| `DJANGO_SECRET_KEY` | Secret key for crypto operations | (dev key) | **Generate unique key!** |
| `DJANGO_DEBUG` | Enable debug mode | `True` | `False` |

**Generate a secret key:**
```bash
python3 -c "from secrets import token_urlsafe; print(token_urlsafe(50))"
```

### Database Configuration

| Variable | Description | Dev Default | Prod Example |
|----------|-------------|-------------|--------------|
| `POSTGRES_VERSION` | PostgreSQL version | `17` | `17` |
| `POSTGRES_DB` | Database name | `nexuslims` | `nexuslims` |
| `POSTGRES_USER` | Database user | `nexuslims` | `nexuslims` |
| `POSTGRES_PASS` | Database password | (dev password) | **Generate unique password!** |
| `POSTGRES_HOST` | Database hostname | `postgres` | `postgres` |
| `POSTGRES_PORT` | Internal port | `5432` | `5432` |
| `POSTGRES_HOST_PORT` | Host-exposed port | `5532` | `5532` |

**Generate a password:**
```bash
python3 -c "from secrets import token_urlsafe; print(token_urlsafe(32))"
```

### Redis Configuration

| Variable | Description | Dev Default | Prod Example |
|----------|-------------|-------------|--------------|
| `REDIS_VERSION` | Redis version | `8` | `8` |
| `REDIS_PASS` | Redis password | (dev password) | **Generate unique password!** |
| `REDIS_HOST` | Redis hostname | `redis` | `redis` |
| `REDIS_PORT` | Internal port | `6379` | `6379` |
| `REDIS_HOST_PORT` | Host-exposed port | `6479` | `6479` |

### Caddy Configuration

| Variable | Description | Dev Default | Prod Example |
|----------|-------------|-------------|--------------|
| `CADDYFILE` | Caddyfile to use | `Caddyfile.dev` | `Caddyfile.prod` |
| `CADDY_ACME_EMAIL` | Email for Let's Encrypt | - | `admin@example.com` |
| `CADDY_CERTS_HOST_PATH` | Path to manual certificates | - | `/opt/nexuslims/certs` |

### File Serving Configuration

| Variable | Description | Dev Default | Prod Example |
|----------|-------------|-------------|--------------|
| `NX_DATA_PATH` | Container path for preview data | `/srv/nx-data` | `/srv/nx-data` |
| `NX_INSTRUMENT_DATA_PATH` | Container path for instrument data | `/srv/nx-instrument-data` | `/srv/nx-instrument-data` |
| `NX_DATA_HOST_PATH` | Host path for preview data | `./test-data/data` | `/mnt/nexuslims/data` |
| `NX_INSTRUMENT_DATA_HOST_PATH` | Host path for instrument data | `./test-data/mmf` | `/mnt/nexuslims/instrument-data` |

### XSLT Configuration

| Variable | Description | Dev Default | Prod Example |
|----------|-------------|-------------|--------------|
| `XSLT_DATASET_BASE_URL` | Base URL for instrument data links | `https://files.nexuslims-dev.localhost/instrument-data` | `https://files.nexuslims.example.com/instrument-data` |
| `XSLT_PREVIEW_BASE_URL` | Base URL for preview image links | `https://files.nexuslims-dev.localhost/data` | `https://files.nexuslims.example.com/data` |

These URLs are patched into XSLT stylesheets when they're uploaded to the database.

### Backup Configuration

| Variable | Description | Dev Default | Prod Example |
|----------|-------------|-------------|--------------|
| `TZ` | Timezone for backup timestamps | `America/New_York` | `America/New_York` |
| `NX_CDCS_BACKUPS_HOST_PATH` | Host path for backups | - | `/opt/nexuslims/backups` |

### Gunicorn Configuration (Production Only)

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `GUNICORN_WORKERS` | Number of worker processes | `4` | 2-4 × CPU cores |
| `GUNICORN_THREADS` | Threads per worker | `2` | 2-4 typical |
| `GUNICORN_TIMEOUT` | Request timeout (seconds) | `120` | Increase for long operations |

**Recommended configurations:**

| Server Size | Cores | RAM | Workers | Threads |
|-------------|-------|-----|---------|---------|
| Small | 2-4 | 4-8 GB | 4 | 2 |
| Medium | 4-8 | 8-16 GB | 8 | 2 |
| Large | 8+ | 16+ GB | 12 | 4 |

---

## Development vs Production

Key differences between development and production configurations:

| Aspect | Development | Production |
|--------|-------------|------------|
| **Debug mode** | Enabled (`True`) | Disabled (`False`) |
| **Web server** | Django runserver | Gunicorn |
| **Certificates** | Local CA (self-signed) | Let's Encrypt (ACME) |
| **Domains** | `.localhost` | Real domains |
| **File paths** | Test data directory | Network storage mounts |
| **Passwords** | Simple defaults | Strong generated passwords |
| **Code mounting** | Yes (hot reload) | No (built into image) |

---

## XSLT URL Configuration

XSLT stylesheets contain URLs for linking to instrument data and preview images. These URLs must match your deployment:

```{mermaid}
%%{init: {'theme': 'base'}}%%
flowchart LR
    subgraph XSLT["XSLT Stylesheet"]
        DatasetURL["datasetBaseUrl"]
        PreviewURL["previewBaseUrl"]
    end

    subgraph ENV["Environment Variables"]
        XSLT_DATASET_BASE_URL
        XSLT_PREVIEW_BASE_URL
    end

    subgraph Caddy["Caddy File Server"]
        InstrumentData["/instrument-data/"]
        PreviewData["/data/"]
    end

    XSLT_DATASET_BASE_URL --> DatasetURL
    XSLT_PREVIEW_BASE_URL --> PreviewURL
    DatasetURL -->|links to| InstrumentData
    PreviewURL -->|links to| PreviewData
```

### Update Process

When you run `dev-update-xslt` or `admin-init`, the scripts:
1. Read the XSL file from `xslt/`
2. Replace placeholder URLs with values from environment variables
3. Upload the patched stylesheet to the database

### Manual URL Patching

If you need to update URLs manually:

```bash
# Inside CDCS container
python manage.py shell
```

```python
from core_main_app.components.xsl_transformation.models import XslTransformation

# Get stylesheet
xslt = XslTransformation.objects.get(name="detail_stylesheet.xsl")

# Update content
xslt.content = xslt.content.replace(
    "https://old-url.com/data",
    "https://new-url.com/data"
)
xslt.save()
```

---

## Optional Integrations

### SAML2 Authentication

SAML2 configuration is stored in `deployment/saml2/.env`. Consult the MDCS documentation for SAML2 setup.

### Handle System

Handle system configuration is stored in `deployment/handle/.env`. This enables persistent identifiers for records.

### Custom Settings

For advanced customization, create a custom settings module:

1. Create `config/settings/custom_settings.py`
2. Import from `prod_settings.py` and override as needed
3. Set `DJANGO_SETTINGS_MODULE=config.settings.custom_settings`

---

## Troubleshooting Configuration

### Environment Not Loading

Verify `.env` file exists and is readable:
```bash
ls -la .env
cat .env | head -20
```

### Variables Not Applied

Docker Compose caches environment. Force reload:
```bash
dc-prod down
dc-prod up -d
```

### XSLT URLs Not Updating

XSLT stylesheets must be re-uploaded after changing URL variables:
```bash
dev-update-xslt  # Development
# or
admin-init       # Production (re-runs full initialization)
```

### Secret Key Errors

If Django complains about the secret key:
1. Ensure `DJANGO_SECRET_KEY` is set
2. Key must be at least 50 characters
3. Don't use special characters that need escaping

---

## Next Steps

- {doc}`production` - Apply configuration for production deployment
- {doc}`administration` - Manage backups and updates
- {doc}`development` - Set up local development environment
