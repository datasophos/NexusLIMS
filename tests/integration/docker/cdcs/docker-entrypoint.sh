#!/bin/bash
# Docker entrypoint script for NexusLIMS CDCS test instance
# Based on datasophos/NexusLIMS-CDCS-Docker

set -e

PROJECT_NAME=$1

echo "========================================"
echo "NexusLIMS CDCS Test Instance Starting"
echo "========================================"

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until PGPASSWORD=$POSTGRES_PASS psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q' 2>/dev/null; do
  echo "  PostgreSQL is unavailable - sleeping"
  sleep 2
done
echo "  PostgreSQL is ready!"

# Wait for MongoDB to be ready
echo "Waiting for MongoDB..."
until curl -s http://$MONGO_HOST:$MONGO_PORT > /dev/null 2>&1; do
  echo "  MongoDB is unavailable - sleeping"
  sleep 2
done
echo "  MongoDB is ready!"

# Apply settings override for anonymous access
echo "Applying settings override..."
if ! grep -q "settings_override" /srv/curator/mdcs/settings.py; then
    echo "" >> /srv/curator/mdcs/settings.py
    echo "# NexusLIMS test instance overrides" >> /srv/curator/mdcs/settings.py
    echo "import sys" >> /srv/curator/mdcs/settings.py
    echo "sys.path.insert(0, '/')" >> /srv/curator/mdcs/settings.py
    echo "from settings_override import *" >> /srv/curator/mdcs/settings.py
    echo "  Settings override applied"
else
    echo "  Settings override already applied"
fi

# Run Django migrations
echo "Running Django migrations..."
echo "  Migrating auth..."
/srv/curator/manage.py migrate auth --noinput
echo "  Migrating all apps..."
/srv/curator/manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
/srv/curator/manage.py collectstatic --noinput

# Compile messages
echo "Compiling messages..."
/srv/curator/manage.py compilemessages

# Create default superuser if it doesn't exist
echo "Creating default superuser..."
/srv/curator/manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@test.local', 'admin')
    print('  Superuser created: admin/admin')
else:
    print('  Superuser already exists')
EOF

# Run schema initialization
echo "Initializing test schema and data..."
python /init_schema.py

# Start Celery worker and beat in background
echo "Starting Celery worker..."
celery -A $PROJECT_NAME worker -E -l info &

echo "Starting Celery beat..."
celery -A $PROJECT_NAME beat -l info &

# Start uWSGI server
echo "Starting uWSGI server..."
echo "========================================"
echo "CDCS is ready at http://localhost:8080"
echo "========================================"

exec uwsgi --chdir /srv/curator/ \
      --uid cdcs \
      --gid cdcs \
      --http 0.0.0.0:8080 \
      --wsgi-file /srv/curator/$PROJECT_NAME/wsgi.py \
      --touch-reload=/srv/curator/$PROJECT_NAME/wsgi.py \
      --static-map /static=/srv/curator/static.prod \
      --processes=2 \
      --enable-threads \
      --lazy-apps \
      --master \
      --vacuum
