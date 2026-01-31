(cdcs-development)=
# Development Setup

This guide walks you through setting up a local NexusLIMS-CDCS development environment with hot-reload, test data, and HTTPS support.

## Prerequisites

- **Docker Desktop** or Docker Engine with Docker Compose
- **Git** for cloning the repository
- **4GB RAM** minimum available for Docker

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/datasophos/NexusLIMS-CDCS.git
cd NexusLIMS-CDCS/deployment
```

### 2. Set Up Environment

```bash
cp .env.dev .env
```

The development defaults work out of the box - no modifications needed.

### 3. Load Development Commands

```bash
source dev-commands.sh
```

This loads convenient aliases for common development tasks (see {ref}`development-commands` below).

### 4. Start the Environment

```bash
dev-up
```

This command:
- Extracts test data (preview images and sample records)
- Builds the CDCS Docker image
- Pulls supporting images (PostgreSQL, Redis, Caddy)
- Starts all services
- Initializes the database with a superuser and sample schema

### 5. Trust the Development CA Certificate

The development environment uses a local Certificate Authority for HTTPS. To avoid browser warnings, trust the CA certificate once:

`````{tab-set}

````{tab-item} macOS
```bash
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain caddy/certs/ca.crt
```
````

````{tab-item} Ubuntu/Debian
```bash
sudo cp caddy/certs/ca.crt /usr/local/share/ca-certificates/nexuslims-dev-ca.crt
sudo update-ca-certificates
```
````

````{tab-item} Fedora/RHEL
```bash
sudo cp caddy/certs/ca.crt /etc/pki/ca-trust/source/anchors/nexuslims-dev-ca.crt
sudo update-ca-trust
```
````

````{tab-item} Windows
1. Open `certmgr.msc`
2. Navigate to "Trusted Root Certification Authorities" > "Certificates"
3. Right-click > "All Tasks" > "Import"
4. Select `caddy/certs/ca.crt`
````

`````

**Alternative - Browser-specific import:**

If you prefer not to trust the certificate system-wide:
- **Chrome/Edge**: Settings > Privacy and security > Security > Manage certificates > Authorities > Import
- **Firefox**: Settings > Privacy & Security > Certificates > View Certificates > Authorities > Import

### 6. Access the Application

| URL | Purpose |
|-----|---------|
| https://nexuslims-dev.localhost | Main application |
| https://files.nexuslims-dev.localhost/data/ | Preview images and metadata |
| https://files.nexuslims-dev.localhost/instrument-data/ | Instrument data files |

**Default credentials:**
- Superuser: `admin` / `admin`
- Regular user: `user` / `user`

---

## Development Features

### Hot Reload

Application code is mounted into the container. Changes to Python files automatically reload the application - no rebuild required.

### Test Data

The development environment includes sample microscopy data (~149MB extracted):
- Preview images at `https://files.nexuslims-dev.localhost/data/`
- Instrument data at `https://files.nexuslims-dev.localhost/instrument-data/`
- Example XML records in the database
- The test data contains only zero-data so it is highly compressible, meaning the preview images
  will appear to be all black or blank. This is expected.
- Test data is automatically extracted by `dev-up` and is gitignored.

### Local HTTPS

Caddy uses a local CA for secure HTTPS connections. After trusting the CA certificate (step 5), all browsers will show valid HTTPS.

### Direct Database Access

For debugging, PostgreSQL and Redis are exposed on host ports:
- PostgreSQL: `localhost:5532`
- Redis: `localhost:6479`

---

(development-commands)=
## Development Commands

Load commands with `source dev-commands.sh` from the `deployment/` directory.

### Lifecycle

| Command | Description |
|---------|-------------|
| `dev-up` | Start all services (includes test data setup) |
| `dev-down` | Stop all services |
| `dev-restart` | Restart CDCS application |
| `dev-clean` | Stop and remove all data (clean slate) |

### Viewing Logs

| Command | Description |
|---------|-------------|
| `dev-logs` | View all service logs |
| `dev-logs-app` | CDCS application logs only |
| `dev-logs-caddy` | Caddy proxy logs |

### Shell Access

| Command | Description |
|---------|-------------|
| `dev-shell` | Bash shell in CDCS container |
| `dev-djshell` | Django Python shell |
| `dev-dbshell` | PostgreSQL shell |

### Database

| Command | Description |
|---------|-------------|
| `dev-migrate` | Run Django migrations |
| `dev-makemigrations` | Create new migrations |

### NexusLIMS-Specific

| Command | Description |
|---------|-------------|
| `dev-update-xslt` | Update both XSLT stylesheets in database |
| `dev-update-xslt-detail` | Update only detail_stylesheet.xsl |
| `dev-update-xslt-list` | Update only list_stylesheet.xsl |

### Dependency Management

The project uses [UV](https://github.com/astral-sh/uv) for fast, reliable Python dependency management with lockfiles for reproducibility.

| Command | Description |
|---------|-------------|
| `dev-uv-lock` | Regenerate `uv.lock` from `pyproject.toml` |
| `dev-uv-upgrade` | Upgrade all dependencies (respecting version constraints) |
| `dev-uv-sync` | Sync local environment with lockfile (for local dev outside Docker) |
| `dev-uv-add` | Show usage for adding new dependencies |

```{note}
After adding or updating dependencies, rebuild the Docker image with `dev-build-clean` to apply changes.
```

**Key Files:**
- `pyproject.toml` - Single source of truth for all dependencies
- `uv.lock` - Lockfile ensuring reproducible builds (must be committed)
- `.python-version` - Required Python version (3.13)

**Dependency Groups:**
- **Main**: Core application (celery, Django, django-redis)
- **core**: 21 CDCS/MDCS packages pinned to `2.18.*`
- **server**: Production servers (psycopg2-binary, uwsgi, gunicorn)

For detailed dependency workflows, see the repository's `CLAUDE.md` and `deployment/README.md`.

---

## Architecture

The development stack uses Docker Compose with three configuration layers:

```
docker-compose.base.yml    # Shared configuration (services, networks, volumes)
docker-compose.dev.yml     # Development overrides (ports, mounts, commands)
```

```{mermaid}
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e3f2fd', 'primaryTextColor': '#000', 'primaryBorderColor': '#1976d2', 'lineColor': '#1976d2'}}}%%
flowchart TB
    Browser([Browser]) -->|HTTPS :443| Caddy

    subgraph Docker["Docker Compose"]
        Caddy[Caddy<br/>Local CA Certs<br/>File Server]
        Django[Django runserver<br/>Hot Reload]
        Postgres[(PostgreSQL<br/>:5532)]
        Redis[(Redis<br/>:6479)]

        Caddy -->|:8000| Django
        Django --> Postgres
        Django --> Redis
    end

    subgraph Mounts["Mounted Directories"]
        Code[Source Code<br/>./]
        XSLT[XSLT Files<br/>xslt/]
        TestData[Test Data<br/>test-data/]
    end

    Django -.- Code
    Django -.- XSLT
    Caddy -.- TestData

    classDef browser fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef service fill:#e1f5ff,stroke:#1976d2,stroke-width:2px
    classDef mount fill:#e8f5e9,stroke:#388e3c,stroke-width:2px

    class Browser browser
    class Caddy,Django,Postgres,Redis service
    class Code,XSLT,TestData mount
```

---

## Directory Structure

```text
deployment/
├── docker-compose.base.yml    # Shared configuration
├── docker-compose.dev.yml     # Development overrides
├── Dockerfile                 # Application image
├── docker-entrypoint.sh       # Container startup script
│
├── .env                       # Active environment (copy from .env.dev)
├── .env.dev                   # Development defaults
│
├── caddy/
│   ├── Dockerfile             # Custom Caddy with plugins
│   ├── Caddyfile.dev          # Development reverse proxy
│   └── certs/                 # CA certificate for HTTPS
│
├── scripts/
│   ├── init_environment.py    # Superuser + schema + XSLT setup
│   ├── update-xslt.sh         # Update XSLT in database
│   └── setup-test-data.sh     # Extract test data
│
├── test-data/                 # Test data (extracted, gitignored)
│
└── dev-commands.sh            # Development helper aliases
```

---

## XSLT Stylesheet Development

```{important}
XSLT stylesheets are stored in the Django database, not just as files. Editing the `.xsl` file is not enough - you must update the database.
```

### Update Process

1. Edit the XSL file in `xslt/` (at repository root)
2. Update the database:

```bash
cd deployment
source dev-commands.sh
dev-update-xslt
```

3. Refresh your browser to see changes

### URL Configuration

The update script automatically patches URLs in the XSLT based on environment variables:
- `XSLT_DATASET_BASE_URL` - Base URL for instrument data files
- `XSLT_PREVIEW_BASE_URL` - Base URL for preview images

Development defaults:
```bash
XSLT_DATASET_BASE_URL=https://files.nexuslims-dev.localhost/instrument-data
XSLT_PREVIEW_BASE_URL=https://files.nexuslims-dev.localhost/data
```

---

## Troubleshooting

### Certificate Warnings

Trust the CA certificate (step 5 above). After trusting `caddy/certs/ca.crt`, all HTTPS connections work without warnings.

### Port Conflicts

Edit port mappings in `.env`:
```bash
POSTGRES_HOST_PORT=5532  # Change if 5532 is in use
REDIS_HOST_PORT=6479     # Change if 6479 is in use
```

### Permission Errors

Ensure scripts are executable:
```bash
chmod +x dev-commands.sh
chmod +x scripts/*.sh scripts/*.py
```

### Test Data Not Loading

Run extraction manually:
```bash
bash scripts/setup-test-data.sh
```

### XSLT Changes Not Appearing

Update the database and refresh:
```bash
dev-update-xslt
```

### Database Connection Errors

Wait for services to fully start. The Django container waits for PostgreSQL to be ready, but this can take a few seconds on first startup.

---

## Next Steps

- {doc}`production` - Deploy to production
- {doc}`configuration` - Detailed environment configuration
- {doc}`local-test-deployment` - Test production config locally with mkcert
