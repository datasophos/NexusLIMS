#!/bin/bash
# Manage the NexusLIMS integration test Docker stack.
#
# Services (all accessible via http://*.localhost:40080):
#   nemo      - NEMO lab management system (also :48000 direct)
#   cdcs      - NexusLIMS CDCS front-end   (also :48080 direct)
#   elabftw   - eLabFTW ELN                (also :48148 direct, HTTPS)
#   mailpit   - Mailpit SMTP test server   (also :41025 SMTP, :48025 UI)
#
# Usage:
#   ./scripts/integration_docker.sh up        # Start the stack
#   ./scripts/integration_docker.sh down      # Stop and remove volumes
#   ./scripts/integration_docker.sh stop      # Stop without removing volumes
#   ./scripts/integration_docker.sh restart   # Stop then start
#   ./scripts/integration_docker.sh status    # Show running containers
#   ./scripts/integration_docker.sh logs      # Tail all service logs
#   ./scripts/integration_docker.sh logs nemo # Tail a specific service
#   ./scripts/integration_docker.sh build     # Rebuild images (no cache)
#   ./scripts/integration_docker.sh ps        # Alias for status

set -euo pipefail

DOCKER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../tests/integration/docker" && pwd)"
COMPOSE="docker compose -f ${DOCKER_DIR}/docker-compose.yml"

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [service...]

Commands:
  up              Start the full stack (builds images if needed)
  down            Stop and remove all containers and volumes
  stop            Stop containers without removing volumes
  restart         Stop then start the full stack
  status / ps     Show container status
  logs [service]  Tail logs (all services, or a named one)
  build           Rebuild images from scratch (--no-cache)

Services (for targeted commands):
  nemo, cdcs, elabftw, mailpit, caddy-proxy,
  cdcs-postgres, cdcs-redis, elabftw-mysql

Endpoints (via Caddy proxy at :40080):
  NEMO:     http://nemo.localhost:40080
  CDCS:     http://cdcs.localhost:40080      admin / admin
  eLabFTW:  http://elabftw.localhost:40080   admin / testpassword
  Mailpit:  http://mailpit.localhost:40080

Direct ports (bypassing Caddy):
  NEMO:     http://localhost:48000
  CDCS:     http://localhost:48080
  eLabFTW:  https://localhost:48148
  Mailpit:  http://localhost:48025 (UI), localhost:41025 (SMTP)
EOF
}

cmd="${1:-}"
shift || true

case "$cmd" in
    up)
        echo "[*] Starting integration test stack..."
        $COMPOSE up -d "$@"
        echo ""
        echo "[+] Stack is up. Waiting for healthchecks..."
        $COMPOSE ps
        ;;
    down)
        echo "[*] Stopping and removing integration test stack (including volumes)..."
        $COMPOSE down -v "$@"
        echo "[+] Done."
        ;;
    stop)
        echo "[*] Stopping integration test stack (volumes preserved)..."
        $COMPOSE stop "$@"
        echo "[+] Done."
        ;;
    restart)
        echo "[*] Restarting integration test stack..."
        $COMPOSE stop "$@"
        $COMPOSE up -d "$@"
        echo "[+] Stack is up."
        ;;
    status|ps)
        $COMPOSE ps "$@"
        ;;
    logs)
        $COMPOSE logs -f --tail=100 "$@"
        ;;
    build)
        echo "[*] Rebuilding images (--no-cache)..."
        $COMPOSE build --no-cache "$@"
        echo "[+] Build complete. Run '$(basename "$0") up' to start."
        ;;
    ""|-h|--help|help)
        usage
        ;;
    *)
        echo "Error: unknown command '${cmd}'" >&2
        echo ""
        usage
        exit 1
        ;;
esac
