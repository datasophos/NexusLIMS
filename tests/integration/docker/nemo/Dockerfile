# Dockerfile for NEMO Integration Test Service
# Based on nanofab/nemo_splash_pad with customizations for NexusLIMS testing

FROM nanofab/nemo_splash_pad:latest

# Install system dependencies
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for data seeding and NEMO plugins
RUN pip install --no-cache-dir \
    requests \
    pytz \
    NEMO-periodic-table-question

# Copy initialization script and fixtures
COPY init_data.py /init_data.py
COPY configure_settings.py /configure_settings.py
COPY wait-for-it.sh /wait-for-it.sh
COPY fixtures/seed_data.json /fixtures/seed_data.json
COPY fixtures/reservation_questions.json /fixtures/reservation_questions.json

# Make scripts executable
RUN chmod +x /wait-for-it.sh /init_data.py /configure_settings.py

# Set environment variables for test mode
ENV DJANGO_SETTINGS_MODULE=NEMO.settings
ENV NEMO_DEBUG=True
ENV PYTHONUNBUFFERED=1

# Expose NEMO API port
EXPOSE 8000

# The entrypoint will be overridden by docker-compose
# to run migrations, seed data, and start the server
