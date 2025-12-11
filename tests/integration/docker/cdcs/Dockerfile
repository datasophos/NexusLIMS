# Dockerfile for NexusLIMS CDCS testing service
# Based on datasophos/NexusLIMS-CDCS-Docker

FROM python:3.7-slim-bookworm

LABEL maintainer="datasophos, llc"
LABEL description="NexusLIMS CDCS test instance for integration testing"

# Directory in container for project source files
ENV DOCKYARD_SRVPROJ="/srv/curator"

# Install necessary packages
RUN apt-get update && apt-get install -y \
    netcat-openbsd vim python3 curl git dnsutils gettext \
    libxml2-dev libxslt-dev python3-dev libssl-dev \
    python3-pip libpq-dev postgresql-client xmlsec1

# Install uwsgi and psycopg2
RUN pip install uwsgi psycopg2==2.8.6

# Clone NexusLIMS-CDCS repository
RUN git clone https://github.com/datasophos/nexuslims-cdcs.git $DOCKYARD_SRVPROJ
RUN cd $DOCKYARD_SRVPROJ \
    && git checkout NexusLIMS_master

# Install Python dependencies
WORKDIR $DOCKYARD_SRVPROJ
RUN pip install -r requirements.txt
RUN pip install -r requirements.core.txt

# Copy entrypoint script and initialization files
COPY ./docker-entrypoint.sh /
COPY ./init_schema.py /
COPY ./settings_override.py /
RUN chmod 755 /docker-entrypoint.sh && \
    chmod 644 /init_schema.py && \
    chmod 644 /settings_override.py

# Create necessary directories
# Note: /fixtures/nexus-experiment.xsd will be mounted as a volume at runtime
RUN mkdir -p /tmp/curator $DOCKYARD_SRVPROJ/static.prod /fixtures

# Create unprivileged user
RUN groupadd -r cdcs && \
    useradd -r -g cdcs cdcs && \
    chown -R cdcs:cdcs $DOCKYARD_SRVPROJ /tmp/curator

# Switch to unprivileged user
USER cdcs

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["mdcs"]
