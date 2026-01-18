# CDCS Docker Service for Integration Testing

This directory contains support files for running a CDCS (Curator Data Collection System) test instance for NexusLIMS integration testing.

## Overview

The CDCS service is built directly from the [datasophos/NexusLIMS-CDCS](https://github.com/datasophos/NexusLIMS-CDCS) repository using Docker's Git URL build context feature. This approach:

- Eliminates code duplication between repositories
- Ensures the test environment matches the actual deployment
- Simplifies maintenance by using a single source of truth

## Architecture

The CDCS service consists of three containers (MongoDB is no longer required):

1. **cdcs-postgres**: PostgreSQL database for Django application data
2. **cdcs-redis**: Redis cache and message broker for Celery tasks
3. **cdcs**: Main Django/Curator application (built from NexusLIMS-CDCS)

## How It Works

The `docker-compose.yml` uses Docker's ability to build from a Git URL:

```yaml
cdcs:
  build:
    context: https://github.com/datasophos/NexusLIMS-CDCS.git#main
    dockerfile: deployment/Dockerfile
```

This clones the NexusLIMS-CDCS repository during the build phase and uses the `deployment/Dockerfile` to build the image.

## Files in This Directory

- **fixtures/**: Test data files (e.g., `test_record.xml`)
- **README.md**: This documentation file
- **__init__.py**: Python package marker (for test imports)

## Configuration

### Environment Variables

The CDCS service is configured via environment variables in `docker-compose.yml`:

**Django Settings:**
- `DJANGO_SETTINGS_MODULE=config.settings.dev_settings`
- `DJANGO_SECRET_KEY`: Secret key for Django (test value only)
- `DJANGO_DEBUG=True`: Enable debug mode
- `SERVER_URI`: Base URL for the CDCS instance
- `ALLOWED_HOSTS`: Django allowed hosts (set to `*` for testing)
- `SERVER_NAME`: Display name for the application

**Database Connections:**
- PostgreSQL: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASS`
- Redis: `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASS`

**XSLT Configuration:**
- `XSLT_DATASET_BASE_URL`: URL for instrument data files
- `XSLT_PREVIEW_BASE_URL`: URL for preview images and metadata

### Default Credentials

The service creates default users for testing:
- **Superuser:** `admin` / `admin`
- **Regular user:** `user` / `user`

**Warning:** These credentials are for testing only. Never use these in production!

## Volume Mounts

The schema file is mounted from the main NexusLIMS repository:

```yaml
volumes:
  - ../../../nexusLIMS/schemas/nexus-experiment.xsd:/srv/nexuslims/schemas/nexus-experiment.xsd:ro
```

This approach:
- Avoids file duplication
- Ensures tests always use the current schema version
- Makes schema changes immediately available to tests

## Usage

### Starting the Service

From the `tests/integration/docker` directory:

```bash
# Start all services (including CDCS)
docker compose up -d

# Start only CDCS and its dependencies
docker compose up -d cdcs

# View logs
docker compose logs -f cdcs
```

### Accessing the Service

Once started, the CDCS instance is available at:
- **URL:** http://cdcs.localhost:40080
- **Admin Interface:** http://cdcs.localhost:40080/admin
- **REST API:** http://cdcs.localhost:40080/rest/

### Stopping the Service

```bash
# Stop all services
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v
```

## Initialization Process

When the CDCS container starts (via `/docker-entrypoint.dev.sh`):

1. **Wait for PostgreSQL**: Check database connectivity
2. **Run migrations**: Initialize database schema
3. **Collect static files**: Gather frontend assets
4. **Initialize environment**: Run `init_environment.py` which:
   - Creates superuser (admin/admin) and regular user (user/user)
   - Uploads Nexus Experiment XSD schema
   - Configures XSLT stylesheets
   - Loads exporters
5. **Start Celery**: Background task worker and scheduler
6. **Start Django runserver**: Development server on port 8000

The entire process takes approximately 30-60 seconds.

## Troubleshooting

### Service won't start

```bash
# Check logs for all CDCS services
docker compose logs cdcs cdcs-postgres cdcs-redis

# Check if ports are already in use
lsof -i :48080  # CDCS web interface

# Rebuild from scratch
docker compose down -v
docker compose build --no-cache cdcs
docker compose up -d cdcs
```

### Database connection errors

```bash
# Check database services are healthy
docker compose ps

# Test PostgreSQL connection
docker exec nexuslims-test-cdcs-postgres pg_isready -U nexuslims
```

### Schema not loading

```bash
# Verify schema file is mounted
docker exec nexuslims-test-cdcs ls -la /srv/nexuslims/schemas/

# Check init_environment.py logs
docker compose logs cdcs | grep -i "schema"
```

## Development Notes

### Schema Updates

When you modify the nexus-experiment.xsd schema:

1. The mounted file is immediately available in the container
2. Restart the CDCS container to reload the schema:
   ```bash
   docker compose restart cdcs
   ```

### Debugging

```bash
# Get a shell in the running container
docker exec -it nexuslims-test-cdcs /bin/bash

# Run Django management commands
docker exec nexuslims-test-cdcs python /srv/nexuslims/manage.py shell
```

## Related Documentation

- [NexusLIMS-CDCS Repository](https://github.com/datasophos/NexusLIMS-CDCS)
- [NexusLIMS-CDCS Deployment](https://github.com/datasophos/NexusLIMS-CDCS/tree/main/deployment)

## Differences from Production

This test instance differs from production deployments:

1. **Django runserver**: Development server instead of Gunicorn/uWSGI
2. **No SSL**: HTTP only (via Caddy reverse proxy)
3. **No SAML**: Basic authentication only
4. **Test credentials**: Hardcoded admin/admin credentials
5. **Ephemeral data**: No persistent volumes
6. **No backups**: No backup/restore mechanisms

This simplified configuration is intentional to keep tests fast and isolated.
