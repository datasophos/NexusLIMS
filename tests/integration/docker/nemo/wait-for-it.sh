#!/bin/bash
# wait-for-it.sh - Wait for NEMO service to be ready
# This script polls the NEMO API until it responds with a 200 status code

set -e

NEMO_URL="${1:-http://localhost:8000/api/users/}"
TIMEOUT="${2:-120}"
START_TIME=$(date +%s)

echo "Waiting for NEMO service at ${NEMO_URL}..."
echo "Timeout: ${TIMEOUT} seconds"

while true; do
    # Calculate elapsed time
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))

    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "ERROR: Timeout waiting for NEMO service after ${TIMEOUT} seconds"
        exit 1
    fi

    # Try to connect to NEMO API
    if curl -sf "${NEMO_URL}" > /dev/null 2>&1; then
        echo "NEMO service is ready!"
        exit 0
    fi

    echo "Waiting for NEMO... (${ELAPSED}s elapsed)"
    sleep 2
done
