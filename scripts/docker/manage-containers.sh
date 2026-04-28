#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

DEFAULT_SERVICES=(postgres api gui)
ALL_SERVICES=(postgres api gui worker)
COMPOSE_MODE=""

usage() {
  cat <<'EOF'
Usage:
  scripts/docker/manage-containers.sh <start|stop|restart|status|logs> [service ...]

Description:
  Startet, stoppt oder zeigt den Status der Docker-Compose-Services.
  Ohne Service-Angabe werden standardmaessig `postgres api gui` verwendet.
  Fuer `worker` wird automatisch das Compose-Profil aktiviert.

Examples:
  scripts/docker/manage-containers.sh start
  scripts/docker/manage-containers.sh stop
  scripts/docker/manage-containers.sh restart api gui
  scripts/docker/manage-containers.sh status
  scripts/docker/manage-containers.sh logs api
  scripts/docker/manage-containers.sh start worker
EOF
}

detect_compose_command() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_MODE="v2"
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_MODE="v1"
  else
    echo "Weder 'docker compose' noch 'docker-compose' wurde gefunden." >&2
    exit 1
  fi
}

is_valid_service() {
  local candidate="$1"
  local service

  for service in "${ALL_SERVICES[@]}"; do
    if [[ "$service" == "$candidate" ]]; then
      return 0
    fi
  done

  return 1
}

normalize_services() {
  local raw_services=("$@")
  local service
  local -A seen=()

  if (( ${#raw_services[@]} == 0 )); then
    raw_services=("${DEFAULT_SERVICES[@]}")
  fi

  for service in "${raw_services[@]}"; do
    if ! is_valid_service "$service"; then
      echo "Unbekannter Service: $service" >&2
      echo "Erlaubt: ${ALL_SERVICES[*]}" >&2
      exit 1
    fi

    if [[ -z "${seen[$service]:-}" ]]; then
      seen["$service"]=1
      printf '%s\n' "$service"
    fi
  done
}

run_compose() {
  local use_worker_profile="$1"
  shift
  local args=("$@")

  if [[ "$COMPOSE_MODE" == "v2" ]]; then
    local cmd=(docker compose)
    if [[ "$use_worker_profile" == "1" ]]; then
      cmd+=(--profile worker)
    fi
    cmd+=("${args[@]}")
    "${cmd[@]}"
    return
  fi

  if [[ "$use_worker_profile" == "1" ]]; then
    COMPOSE_PROFILES=worker docker-compose "${args[@]}"
  else
    docker-compose "${args[@]}"
  fi
}

main() {
  if (( $# == 0 )); then
    usage
    exit 1
  fi

  local action="$1"
  shift

  case "$action" in
    start|stop|restart|status|logs)
      ;;
    -h|--help|help)
      usage
      exit 0
      ;;
    *)
      echo "Unbekannte Aktion: $action" >&2
      usage
      exit 1
      ;;
  esac

  detect_compose_command

  local services=()
  mapfile -t services < <(normalize_services "$@")

  local use_worker_profile=0
  if printf '%s\n' "${services[@]}" | grep -qx 'worker'; then
    use_worker_profile=1
  fi

  case "$action" in
    start)
      run_compose "$use_worker_profile" up -d "${services[@]}"
      ;;
    stop)
      run_compose "$use_worker_profile" stop "${services[@]}"
      ;;
    restart)
      run_compose "$use_worker_profile" restart "${services[@]}"
      ;;
    status)
      run_compose "$use_worker_profile" ps "${services[@]}"
      ;;
    logs)
      run_compose "$use_worker_profile" logs -f "${services[@]}"
      ;;
  esac
}

main "$@"
