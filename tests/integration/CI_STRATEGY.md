# CI/CD Strategy for Integration Tests

This document explains how integration tests work in CI/CD pipelines and how to optimize build times.

## Overview

Integration tests use Docker Compose to spin up real NEMO and CDCS services. To avoid rebuilding Docker images on every CI run, we use a **pre-built image strategy** with GitHub Container Registry (GHCR).

## Current Implementation (Phase 4)

### Local Development

When running tests locally, `docker compose up -d` will:
1. Build images from Dockerfiles if they don't exist
2. Use cached images if available
3. Rebuild only if Dockerfiles change

**Build time**: ~10-15 minutes first run, ~30 seconds subsequent runs (with cache)

### CI Without Pre-built Images (Temporary)

Until Phase 7 is complete, CI will build images on every run:
- **First run**: ~10-15 minutes for builds
- **Subsequent runs**: ~3-5 minutes (Docker layer caching helps)
- **Total test time**: ~15-20 minutes

## Optimized Strategy (Phase 7: Docker Image Registry)

### How It Works

```
┌─────────────────────────────────────────────────────────┐
│  1. Developer Changes Docker Config                     │
│     - Updates tests/integration/docker/nemo/            │
│     - Pushes to main branch                             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  2. Image Build Workflow Triggers                       │
│     - Runs: .github/workflows/build-test-images.yml     │
│     - Builds NEMO and CDCS images                       │
│     - Pushes to ghcr.io/datasophos/nexuslims/*:latest  │
│     - Tags with commit SHA for versioning               │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  3. PR Integration Tests Run                            │
│     - Pulls pre-built images from GHCR                  │
│     - No build time needed                              │
│     - Starts services in ~30 seconds                    │
│     - Runs tests in ~5-10 minutes                       │
└─────────────────────────────────────────────────────────┘
```

### File Structure

```
tests/integration/docker/
├── docker-compose.yml              # Base config (builds images)
├── docker-compose.ci.yml           # CI override (uses pre-built images)
├── nemo/
│   ├── Dockerfile                  # Built by build-test-images.yml
│   └── ...
└── cdcs/
    ├── Dockerfile                  # Built by build-test-images.yml
    └── ...
```

### Automatic CI Override Detection

The `docker_services` fixture in `conftest.py` automatically detects and uses the CI override:

```python
# Check if docker-compose.ci.yml exists
ci_override = DOCKER_DIR / "docker-compose.ci.yml"
if ci_override.exists():
    print("[*] Using CI override with pre-built images")
    compose_cmd.extend(["-f", "docker-compose.ci.yml"])
```

This means:
- **Local development**: Uses base `docker-compose.yml` (builds images)
- **CI with override file**: Uses pre-built images from GHCR
- **No code changes needed** - it's automatic!

## Phase 7 Implementation Plan

### Step 1: Create Image Build Workflow

**File**: `.github/workflows/build-test-images.yml`

```yaml
name: Build Test Docker Images

on:
  push:
    branches: [main]
    paths:
      - 'tests/integration/docker/**'
  workflow_dispatch:

jobs:
  build-nemo:
    name: Build NEMO Test Image
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push NEMO image
        uses: docker/build-push-action@v5
        with:
          context: ./tests/integration/docker/nemo
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/nemo-test:latest
            ghcr.io/${{ github.repository }}/nemo-test:${{ github.sha }}
          cache-from: type=registry,ref=ghcr.io/${{ github.repository }}/nemo-test:latest
          cache-to: type=inline

  build-cdcs:
    name: Build CDCS Test Image
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push CDCS image
        uses: docker/build-push-action@v5
        with:
          context: ./tests/integration/docker/cdcs
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/cdcs-test:latest
            ghcr.io/${{ github.repository }}/cdcs-test:${{ github.sha }}
          cache-from: type=registry,ref=ghcr.io/${{ github.repository }}/cdcs-test:latest
          cache-to: type=inline
```

### Step 2: Create CI Override File

**File**: `tests/integration/docker/docker-compose.ci.yml`

```yaml
# CI-specific overrides that use pre-built images from GHCR
version: '3.8'

services:
  nemo:
    # Override build with pre-built image
    image: ghcr.io/datasophos/nexuslims/nemo-test:latest
    build: null

  cdcs:
    # Override build with pre-built image
    image: ghcr.io/datasophos/nexuslims/cdcs-test:latest
    build: null

  # Other services (mongo, postgres, redis, fileserver) inherit from base
  # and don't need overrides since they use official images
```

### Step 3: Update Integration Test Workflow

**File**: `.github/workflows/integration-tests.yml`

```yaml
name: Integration Tests

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  integration:
    name: Integration Tests
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Pull pre-built images
        run: |
          docker pull ghcr.io/${{ github.repository }}/nemo-test:latest
          docker pull ghcr.io/${{ github.repository }}/cdcs-test:latest

      - name: Start Docker services
        run: |
          cd tests/integration/docker
          # The docker_services fixture will automatically use
          # docker-compose.ci.yml since it exists
          docker compose -f docker-compose.yml -f docker-compose.ci.yml up -d

      - name: Wait for services
        run: |
          timeout 120 bash -c 'until curl -sf http://localhost:8000/; do sleep 2; done'
          timeout 120 bash -c 'until curl -sf http://localhost:8080/; do sleep 2; done'

      - name: Set up uv
        uses: astral-sh/setup-uv@v4

      - name: Run integration tests
        run: |
          uv sync
          uv run pytest tests/integration/ -v -m integration

      - name: Cleanup
        if: always()
        run: |
          cd tests/integration/docker
          docker compose down -v
```

### Step 4: Make Images Public

After the first build:
1. Go to GitHub repository → Packages
2. Find `nemo-test` and `cdcs-test` packages
3. Change visibility to **Public**
4. This allows pulling without authentication

## Performance Comparison

### Without Pre-built Images (Current)
```
┌─────────────────────────────────┐
│ Build NEMO image:   8-10 min    │
│ Build CDCS image:   8-10 min    │
│ Start services:     30 sec       │
│ Run tests:          5-8 min      │
│ ────────────────────────────────│
│ TOTAL:              ~20-30 min   │
└─────────────────────────────────┘
```

### With Pre-built Images (Phase 7)
```
┌─────────────────────────────────┐
│ Pull NEMO image:    20 sec       │
│ Pull CDCS image:    20 sec       │
│ Start services:     30 sec       │
│ Run tests:          5-8 min      │
│ ────────────────────────────────│
│ TOTAL:              ~7-10 min    │
└─────────────────────────────────┘
```

**Time savings**: ~15-20 minutes per CI run

## Image Update Strategy

### When Images Are Rebuilt

Images are rebuilt **only when**:
1. Docker configuration changes (Dockerfiles, init scripts, etc.)
2. Manual workflow dispatch
3. Push to `main` branch

### Image Versioning

Each build creates two tags:
- `:latest` - Always points to most recent build
- `:$SHA` - Specific commit hash (for rollback)

Example:
```
ghcr.io/datasophos/nexuslims/nemo-test:latest
ghcr.io/datasophos/nexuslims/nemo-test:9b72408a1b2c3d4e5f6
```

### Using Specific Versions

To pin to a specific version in CI:
```yaml
# docker-compose.ci.yml
services:
  nemo:
    image: ghcr.io/datasophos/nexuslims/nemo-test:9b72408a1b2c3d4e5f6
```

## Testing the Strategy Locally

You can test the pre-built image workflow locally:

### Option 1: Build and Push Locally (for testing)

```bash
# Build and tag images
cd tests/integration/docker
docker compose build

# Tag for GHCR (adjust repository name)
docker tag nexuslims-test-nemo ghcr.io/datasophos/nexuslims/nemo-test:latest
docker tag nexuslims-test-cdcs ghcr.io/datasophos/nexuslims/cdcs-test:latest

# Create docker-compose.ci.yml
cat > docker-compose.ci.yml << 'EOF'
services:
  nemo:
    image: ghcr.io/datasophos/nexuslims/nemo-test:latest
    build: null
  cdcs:
    image: ghcr.io/datasophos/nexuslims/cdcs-test:latest
    build: null
EOF

# Run with override
docker compose -f docker-compose.yml -f docker-compose.ci.yml up -d
```

### Option 2: Test Fixture Auto-Detection

```bash
# Run tests - fixture will detect docker-compose.ci.yml
cd tests/integration
uv run pytest -xvs

# Check output for:
# [*] Using CI override with pre-built images
```

## Troubleshooting

### Issue: Images not found in CI

**Solution**: Ensure images are built and pushed:
```bash
# Manually trigger build workflow
gh workflow run build-test-images.yml
```

### Issue: Permission denied pulling images

**Solution**: Check package visibility is set to Public

### Issue: Old cached images being used

**Solution**: Pull specific SHA tag or clear local cache:
```bash
docker pull ghcr.io/datasophos/nexuslims/nemo-test:latest
docker pull ghcr.io/datasophos/nexuslims/cdcs-test:latest
```

## Benefits

1. **Faster CI runs**: 15-20 minutes saved per run
2. **Cheaper**: Less GitHub Actions minutes consumed
3. **More reliable**: Pre-built images reduce build failures
4. **Easier debugging**: Can pull exact image version used in CI
5. **Better caching**: Registry caching more effective than local

## Migration Path

Phase 7 is **non-breaking**:
- Local development continues to work unchanged
- CI works with or without pre-built images
- Gradual rollout possible (one service at a time)

No changes to test code required - everything is handled by Docker Compose configuration.
