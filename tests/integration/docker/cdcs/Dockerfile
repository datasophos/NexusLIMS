# Dockerfile for NexusLIMS CDCS testing service
# Based on datasophos/NexusLIMS-CDCS-Docker

FROM python:3.11-slim

LABEL maintainer="datasophos, llc"
LABEL description="NexusLIMS CDCS test instance for integration testing"

# Environment variables
ENV DOCKYARD_SRVPROJ=/srv/curator \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    vim \
    curl \
    git \
    dnsutils \
    gettext \
    libxml2-dev \
    libxslt-dev \
    libssl-dev \
    libpq-dev \
    postgresql-client \
    xmlsec1 \
    && rm -rf /var/lib/apt/lists/*

# Install uwsgi and psycopg2
RUN pip install --no-cache-dir uwsgi psycopg2-binary==2.9.9

# Clone NexusLIMS-CDCS repository
# Using datasophos fork with NexusLIMS customizations
ARG CDCS_REPO=https://github.com/datasophos/NexusLIMS-CDCS.git
ARG BRANCH=master

RUN git clone $CDCS_REPO $DOCKYARD_SRVPROJ && \
    cd $DOCKYARD_SRVPROJ && \
    git checkout $BRANCH

# Install Python dependencies
WORKDIR $DOCKYARD_SRVPROJ
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements.core.txt

# Copy entrypoint script and initialization files
COPY ./docker-entrypoint.sh /
COPY ./init_schema.py /
RUN chmod +x /docker-entrypoint.sh

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
