# CDCS Docker Service for Integration Testing

This directory contains the Docker configuration for running a CDCS (Curator Data Collection System) test instance for NexusLIMS integration testing.

## Overview

The CDCS service provides a lightweight test instance of the NexusLIMS frontend, based on the [datasophos/NexusLIMS-CDCS](https://github.com/datasophos/NexusLIMS-CDCS) repository. This service is used for integration testing to validate that the NexusLIMS backend can successfully upload experimental records to CDCS.

## Architecture

The CDCS service consists of four containers:

1. **cdcs-mongo**: MongoDB database for storing records and templates
2. **cdcs-postgres**: PostgreSQL database for Django application data
3. **cdcs-redis**: Redis cache and message broker for Celery tasks
4. **cdcs**: Main Django/Curator application

## Files

- **Dockerfile**: Builds the CDCS application container
  - Based on Python 3.11
  - Clones NexusLIMS-CDCS repository
  - Installs dependencies from requirements.txt
  - Runs as unprivileged `cdcs` user

- **docker-entrypoint.sh**: Container startup script
  - Waits for PostgreSQL and MongoDB to be ready
  - Runs Django migrations
  - Creates default superuser (admin/admin)
  - Initializes schema and test data
  - Starts Celery worker and beat
  - Starts uWSGI server on port 8080

- **init_schema.py**: Schema initialization script
  - Loads Nexus Experiment XSD schema as a CDCS template
  - Creates "NexusLIMS Test Workspace" for testing
  - Run automatically during container startup

## Configuration

### Environment Variables

The CDCS service is configured via environment variables in `docker-compose.yml`:

**Django Settings:**
- `DJANGO_SETTINGS_MODULE=mdcs.settings`
- `DJANGO_SECRET_KEY`: Secret key for Django (test value only)
- `SERVER_URI`: Base URL for the CDCS instance
- `ALLOWED_HOSTS`: Django allowed hosts (set to `*` for testing)
- `SERVER_NAME`: Display name for the application

**Database Connections:**
- MongoDB: `MONGO_HOST`, `MONGO_PORT`, `MONGO_DB`, `MONGO_USER`, `MONGO_PASS`
- PostgreSQL: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASS`
- Redis: `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASS`

**Performance:**
- `UWSGI_PROCESSES=2`: Number of uWSGI worker processes (kept low for testing)

### Default Credentials

The service creates a default superuser for testing:
- **Username:** `admin`
- **Password:** `admin`
- **Email:** `admin@test.local`

**⚠️ WARNING:** These credentials are for testing only. Never use these in production!

## Volume Mounts

The schema file is mounted from the main NexusLIMS repository:

```yaml
volumes:
  - ../../../nexusLIMS/schemas/nexus-experiment.xsd:/fixtures/nexus-experiment.xsd:ro
```

This approach:
- Avoids file duplication
- Ensures tests always use the latest schema
- Makes schema changes immediately available to tests
- Follows Docker best practices

## Usage

### Starting the Service

From the `tests/integration/docker` directory:

```bash
# Start all services (including CDCS)
docker-compose up -d

# Start only CDCS and its dependencies
docker-compose up -d cdcs

# View logs
docker-compose logs -f cdcs
```

### Accessing the Service

Once started, the CDCS instance is available at:
- **URL:** http://localhost:8080
- **Admin Interface:** http://localhost:8080/admin
- **REST API:** http://localhost:8080/rest/

### Testing the Service

```bash
# Check service health
curl http://localhost:8080/

# Check REST API
curl http://localhost:8080/rest/workspace/read_access

# Login and get API token
curl -X POST http://localhost:8080/rest/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

### Stopping the Service

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

## Health Checks

The service includes comprehensive health checks:

**MongoDB:**
- Command: `mongosh --eval "db.adminCommand('ping')"`
- Interval: 5s, Start period: 10s

**PostgreSQL:**
- Command: `pg_isready -U cdcs`
- Interval: 5s, Start period: 10s

**Redis:**
- Command: `redis-cli --raw incr ping`
- Interval: 5s, Start period: 5s

**CDCS Application:**
- Command: `curl -f http://localhost:8080/`
- Interval: 10s, Start period: 60s (allows time for initialization)

## Initialization Process

When the CDCS container starts:

1. **Wait for dependencies**: PostgreSQL and MongoDB must be healthy
2. **Run migrations**: `manage.py migrate` initializes database schema
3. **Collect static files**: Frontend assets are gathered
4. **Compile messages**: i18n translation files are compiled
5. **Create superuser**: Default admin user is created if it doesn't exist
6. **Load schema**: `init_schema.py` uploads Nexus Experiment XSD template
7. **Create workspace**: Test workspace is created for record storage
8. **Create marker file**: `/srv/curator/.init_complete` is created to prevent re-initialization
9. **Start Celery**: Background task worker and scheduler are started
10. **Start uWSGI**: Web server begins accepting requests

The entire process takes approximately 30-60 seconds.

### Idempotent Initialization

The initialization script (`init_schema.py`) uses a marker file to prevent duplicate data creation:

- **Marker file location**: `/srv/curator/.init_complete`
- **Behavior**: If this file exists, initialization is skipped
- **Benefit**: You can safely restart the container (`docker compose restart cdcs`) without creating duplicate schemas or workspaces
- **Reset**: To force re-initialization, run `docker compose down -v` to remove all volumes

## Troubleshooting

### Service won't start

```bash
# Check logs for all CDCS services
docker-compose logs cdcs cdcs-mongo cdcs-postgres cdcs-redis

# Check if ports are already in use
lsof -i :8080  # CDCS web interface

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache cdcs
docker-compose up -d cdcs
```

### Schema not loading

```bash
# Verify schema file is mounted
docker exec nexuslims-test-cdcs ls -la /fixtures/

# Check init_schema.py logs
docker-compose logs cdcs | grep -A 20 "Schema Initialization"

# Manually run initialization
docker exec -it nexuslims-test-cdcs python /init_schema.py
```

### Database connection errors

```bash
# Check database services are healthy
docker-compose ps

# Test MongoDB connection
docker exec nexuslims-test-cdcs-mongo mongosh --eval "db.adminCommand('ping')"

# Test PostgreSQL connection
docker exec nexuslims-test-cdcs-postgres pg_isready -U cdcs
```

### Memory issues

The CDCS stack (Django + Celery + 3 databases) can be memory-intensive. If you experience issues:

```bash
# Check Docker resources
docker stats

# Reduce uWSGI workers (edit docker-compose.yml)
- UWSGI_PROCESSES=1  # Down from 2

# Stop unused services
docker-compose stop nemo  # If only testing CDCS
```

## Development Notes

### Schema Updates

When you modify [nexus-experiment.xsd](../../../../nexusLIMS/schemas/nexus-experiment.xsd):

1. The change is immediately reflected (file is volume-mounted)
2. Restart the CDCS container to reload the schema:
   ```bash
   docker-compose restart cdcs
   ```
3. Or manually re-run the initialization:
   ```bash
   docker exec nexuslims-test-cdcs python /init_schema.py
   ```

### Adding Test Data

To add sample records or additional test data, modify [init_schema.py](init_schema.py):

```python
def create_sample_records():
    """Create sample experimental records for testing."""
    # Add your test record creation logic here
    pass
```

### Debugging

```bash
# Get a shell in the running container
docker exec -it nexuslims-test-cdcs /bin/bash

# Run Django management commands
docker exec nexuslims-test-cdcs /srv/curator/manage.py shell

# Check Python package versions
docker exec nexuslims-test-cdcs pip list | grep -i cdcs
```

## Integration with Tests

Python integration tests can interact with this service using the fixtures in `tests/integration/conftest.py`:

```python
def test_upload_record(cdcs_service, cdcs_credentials):
    """Test uploading a record to CDCS."""
    username, password = cdcs_credentials
    # ... test code ...
```

See `tests/integration/test_cdcs_integration.py` for examples.

## Related Documentation

- [NexusLIMS-CDCS Repository](https://github.com/datasophos/NexusLIMS-CDCS)
- [NexusLIMS-CDCS-Docker Deployment](https://github.com/datasophos/NexusLIMS-CDCS-Docker)
- [Integration Testing Plan](../../../../.claude/plans/implement-integration-testing.md)
- [Integration Testing TODO](../../../../INTEGRATION_TESTING_TODO.md)

## Differences from Production

This test instance differs from production deployments:

1. **No NGINX**: uWSGI serves HTTP directly (no reverse proxy)
2. **No SSL**: HTTP only, no TLS/certificates
3. **No SAML**: Basic authentication only
4. **Reduced workers**: 2 uWSGI processes vs 10+ in production
5. **Test credentials**: Hardcoded admin/admin credentials
6. **No volumes**: Data is ephemeral (lost when container stops)
7. **No backups**: No backup/restore mechanisms
8. **Single host**: All services on one machine vs distributed

This simplified configuration is intentional to keep tests fast and isolated.
