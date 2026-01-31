# eLabFTW Integration Test Setup

## Automated Setup

The eLabFTW test database is automatically initialized with seed data on first startup.

### Start Docker Stack

```bash
cd tests/integration/docker
docker compose up -d
```

The init script will automatically:
1. Create a test team: "Test Team"
2. Create a test user: testuser@example.com / testpass123
3. Add user to team
4. Generate API key: `1-aaaa...` (84 'a' characters)

### Verify Initialization

```bash
# Check container logs
docker compose logs elabftw

# You should see:
# "Initialization complete!"
# with test credentials printed
```

### Test Credentials

The following credentials are hardcoded for integration testing:

- **API URL**: `http://elabftw.localhost:40080`
- **API Key**: `1-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` (84 'a' characters)
- **Test User**: `testuser@example.com`
- **Password**: `testpass123`

**Note**: The test user is created via direct database insertion for automated testing. The API key works perfectly for all integration tests.

## Running Integration Tests

```bash
# Set test environment variables (optional - tests use defaults if not set)
export NX_ELABFTW_URL="http://elabftw.localhost:40080"
export NX_ELABFTW_API_KEY="1-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

# Run all eLabFTW integration tests
uv run pytest tests/integration/test_elabftw_integration.py -v -m integration

# Run specific test
uv run pytest tests/integration/test_elabftw_integration.py::TestELabFTWClientIntegration::test_create_and_get_experiment -v
```

## Manual Reset

```bash
# Stop and remove volumes (full reset)
docker compose down -v

# Restart (will re-initialize)
docker compose up -d
```

## Troubleshooting

### Init script didn't run

Check if marker file exists:
```bash
docker compose exec elabftw cat /tmp/elabftw_init_complete
```

If it exists but setup seems wrong, remove volumes and restart:
```bash
docker compose down -v
docker compose up -d
```

### Database connection errors

Wait longer for MySQL to be ready:
```bash
docker compose logs elabftw-mysql
# Look for "ready for connections"
```

### API key not working

Verify the key in the database:
```bash
docker compose exec elabftw-mysql mysql -uelabftw -pnexuslims_elabftw elabftw \
  -e "SELECT id, name, can_write, userid FROM api_keys;"
```
