# NexusLIMS Integration Test Docker Services

This directory contains Docker configurations for running integration tests with real NEMO and CDCS services.

## Quick Start

### Prerequisites

- Docker (>= 20.10)
- Docker Compose (>= 2.0)
- curl (for manual testing)

### Starting Services

```bash
# Start all services
cd tests/integration/docker
docker-compose up -d

# View logs
docker-compose logs -f

# Check service health
docker-compose ps
```

### Stopping Services

```bash
# Stop services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

## Services

### NEMO Service

- **URL**: http://localhost:8000
- **API**: http://localhost:8000/api/
- **Admin Panel**: http://localhost:8000/admin/
- **Admin Credentials**: admin / admin

#### Test Data

The NEMO service is pre-populated with test data from [`nemo/fixtures/seed_data.json`](nemo/fixtures/seed_data.json):

**Users:**
- captain (superuser, facility manager)
- professor (staff)
- ned (regular user)
- commander (accounting officer)

**Tools:**
- 643 Titan (S)TEM
- 642 FEI Titan
- JEOL JEM-3010

**Projects:**
- Project Alpha (PROJ-001)
- Project Beta (PROJ-002)
- Project Gamma (PROJ-003)

**Reservation Questions:**
All tools are configured with NexusLIMS-style reservation questions including:
- Project ID
- Experiment Title
- Experiment Purpose
- Data Consent Agreement
- Sample Information (group question with multiple samples support)
  - Sample Name/PID
  - Sample or PID selector
  - Sample Details
  - Periodic Table element selector (via NEMO-periodic-table-question plugin)

**Sample Reservations and Usage Events:**
The database includes sample data matching unit test scenarios:
- 3 reservations with varying question_data (including samples and periodic table elements)
- 2 corresponding usage events
- Data created on "643 Titan (S)TEM" tool with ned/professor as users

All users have the password: `test_password_123`

#### Testing the NEMO API

```bash
# List users
curl http://localhost:8000/api/users/

# List tools
curl http://localhost:8000/api/tools/

# List projects
curl http://localhost:8000/api/projects/
```

### PostgreSQL Database

- **Host**: localhost
- **Port**: 5432
- **Database**: nemo_test
- **User**: nemo
- **Password**: nemo_test_pass

Connect with:
```bash
psql -h localhost -p 5432 -U nemo -d nemo_test
```

## Directory Structure

```
docker/
├── docker-compose.yml           # Main service orchestration
├── docker-compose.ci.yml        # CI-specific overrides (future)
├── nemo/
│   ├── Dockerfile              # NEMO service image
│   ├── init_data.py            # Database seeding script
│   ├── wait-for-it.sh          # Health check script
│   └── fixtures/
│       └── seed_data.json      # Test data (matches shared_data.py)
└── cdcs/                       # CDCS service (Phase 3)
    └── ...
```

## Development Workflow

### Rebuilding After Changes

If you modify the Dockerfile or initialization scripts:

```bash
# Rebuild NEMO service
docker-compose build nemo

# Restart with fresh data
docker-compose down -v
docker-compose up -d
```

### Accessing Service Logs

```bash
# All services
docker-compose logs -f

# NEMO only
docker-compose logs -f nemo

# Database only
docker-compose logs -f nemo-postgres
```

### Debugging

```bash
# Execute commands in NEMO container
docker-compose exec nemo bash

# Access Django shell
docker-compose exec nemo python manage.py shell

# Run migrations manually
docker-compose exec nemo python manage.py migrate

# Re-seed data
docker-compose exec nemo python /init_data.py
```

## Troubleshooting

### NEMO service fails to start

1. **Check database connection:**
   ```bash
   docker-compose logs nemo-postgres
   docker-compose exec nemo-postgres pg_isready -U nemo
   ```

2. **Check NEMO logs:**
   ```bash
   docker-compose logs nemo
   ```

3. **Restart services:**
   ```bash
   docker-compose restart nemo
   ```

### Port conflicts

If ports 8000 or 5432 are already in use, modify [`docker-compose.yml`](docker-compose.yml):

```yaml
services:
  nemo:
    ports:
      - "8001:8000"  # Use different host port

  nemo-postgres:
    ports:
      - "5433:5432"  # Use different host port
```

### Clearing all data

```bash
# Remove containers, networks, and volumes
docker-compose down -v

# Remove images (forces rebuild)
docker-compose down --rmi all -v
```

## CI/CD Usage

In CI environments, use pre-built images from GitHub Container Registry:

```bash
# Pull pre-built images
export GITHUB_REPOSITORY=datasophos/NexusLIMS
docker pull ghcr.io/${GITHUB_REPOSITORY}/nemo-test:latest

# Use with CI-specific compose file
docker-compose -f docker-compose.yml -f docker-compose.ci.yml up -d
```

## Implementation Status

### Phase 2: NEMO Docker Service ✅ COMPLETED

- [x] Create `nemo/Dockerfile`
- [x] Create `nemo/init_data.py`
- [x] Create `nemo/fixtures/seed_data.json`
- [x] Create `nemo/wait-for-it.sh`
- [x] Add NEMO service to `docker-compose.yml`
- [x] Manual testing documentation

### Phase 3: CDCS Docker Service ✅ COMPLETED

- [x] Create `cdcs/Dockerfile`
- [x] Create `cdcs/init_schema.py`
- [x] Mount schema from source repository
- [x] Add CDCS services to `docker-compose.yml` (CDCS, MongoDB, PostgreSQL, Redis)
- [x] Add Caddy fileserver for test data
- [x] Configure XSLT patching with fileserver URLs
- [x] Test CDCS service manually

## CDCS Service

### Accessing CDCS

- **URL**: http://localhost:8080
- **Admin Panel**: http://localhost:8080/admin/
- **Admin Credentials**: admin / admin
- **Templates Page**: http://localhost:8080/admin/templates

### File Server

- **URL**: http://localhost:8081
- **Instrument Data**: http://localhost:8081/instrument-data
- **Preview Data**: http://localhost:8081/data

The file server uses Caddy and serves test data from:
- `/tmp/nexuslims-test-instrument-data` → Instrument files
- `/tmp/nexuslims-test-data` → Preview images and metadata

**Note:** Test fixtures must create and populate these directories before running tests.

### Schema Initialization

The Nexus Experiment schema is automatically loaded on first startup:

1. Schema loaded from `nexusLIMS/schemas/nexus-experiment.xsd` as a global template
2. XSLT stylesheets downloaded from NexusLIMS-CDCS repository
3. XSLT variables patched with fileserver URLs:
   - `datasetBaseUrl` → `http://localhost:8081/instrument-data`
   - `previewBaseUrl` → `http://localhost:8081/data`
4. Template registered with XSLT rendering configuration
5. Test workspace created
6. Anonymous access configured

To re-initialize the schema:
```bash
docker compose down -v
docker compose up -d
```

### XSLT Configuration

XSLT stylesheet URLs are controlled by environment variables in `docker-compose.yml`:
- `FILESERVER_DATASET_URL`: Base URL for instrument data files
- `FILESERVER_PREVIEW_URL`: Base URL for preview images

These are automatically patched into the XSLTs during initialization.

## See Also

- [Integration Testing Plan](../../../.claude/plans/implement-integration-testing.md)
- [Integration Testing TODO](../../../INTEGRATION_TESTING_TODO.md)
- [Shared Test Data](../../fixtures/shared_data.py)
