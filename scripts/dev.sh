#!/usr/bin/env bash
set -euo pipefail

root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
usage() {
    printf '%s\n' 'Usage: dev.sh [help|build|start|stop|restart|status|logs [web|api|worker|postgres]|test|verify]'
}
command=${1:-help}
case "$command" in
    logs)
        if (( $# > 2 )); then usage >&2; exit 2; fi
        case "${2:-}" in ''|web|api|worker|postgres) ;; *) usage >&2; exit 2 ;; esac ;;
    help|build|start|stop|restart|status|test|verify)
        if (( $# > 1 )); then usage >&2; exit 2; fi ;;
    *) usage >&2; exit 2 ;;
esac
if [[ "$command" == help ]]; then usage; exit 0; fi
cd -- "$root"
if [[ "$command" == test || "$command" == verify ]]; then
    python="$root/.venv/bin/python"
    if [[ ! -x "$python" ]]; then python=python3; fi
    if ! command -v "$python" >/dev/null; then
        printf '%s\n' 'Install Python 3.12+; create .venv and install backend/requirements-test.txt.' >&2
        exit 1
    fi
    if [[ "$command" == test ]]; then
        exec "$python" -m unittest discover -s tests -p 'test_*.py'
    fi
    exec "$python" "$root/tests/verify_compose.py"
fi
if [[ ! -f "$root/.env.docker" ]]; then
    printf '%s\n' 'Missing .env.docker: copy .env.docker.example and edit privately.' 'Set POSTGRES_PASSWORD, separate DATABASE_PASSWORD, and the six provider URL/credential names in the template.' >&2
    exit 1
fi
if ! command -v docker >/dev/null; then
    printf '%s\n' 'Install Docker Engine and Compose v2+.' >&2
    exit 1
fi
docker compose version >/dev/null
docker info >/dev/null 2>&1 || { printf '%s\n' 'Docker daemon is unavailable; start Docker and check access.' >&2; exit 1; }
compose() {
    docker compose --project-directory "$root" --env-file "$root/.env.docker" -f "$root/docker-compose.yml" "$@"
}
case "$command" in
    build) compose build ;;
    start) compose up -d --build --wait --wait-timeout 120 ;;
    stop) compose down ;;
    restart) compose up -d --build --force-recreate --wait --wait-timeout 120 ;;
    status) compose ps ;;
    logs)
        if [[ -n "${2:-}" ]]; then compose logs -f --tail 100 "$2";
        else compose logs -f --tail 100; fi ;;
esac
