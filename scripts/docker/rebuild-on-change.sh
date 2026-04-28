#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

POLL_SECONDS="${POLL_SECONDS:-2}"
WATCH_MODE=0
INCLUDE_UNTRACKED=1
COMPOSE_MODE=""
DRY_RUN="${DRY_RUN:-0}"

usage() {
  cat <<'EOF'
Usage:
  scripts/docker/rebuild-on-change.sh [--watch] [--interval SECONDS] [file ...]

Description:
  Rebuilds only the affected Docker Compose services based on changed files.
  Without file arguments, the script reads changes from git status.

Examples:
  scripts/docker/rebuild-on-change.sh
  scripts/docker/rebuild-on-change.sh --watch
  scripts/docker/rebuild-on-change.sh src/gui/app.py src/gui/tabs/databases.py
EOF
}

normalize_paths() {
  local path

  for path in "$@"; do
    path="${path#./}"
    if [[ -n "$path" ]]; then
      printf '%s\n' "$path"
    fi
  done
}

collect_changed_files() {
  local tracked=()
  local untracked=()

  mapfile -t tracked < <(git diff --name-only HEAD --)

  if (( INCLUDE_UNTRACKED )); then
    mapfile -t untracked < <(git ls-files --others --exclude-standard)
  fi

  normalize_paths "${tracked[@]}" "${untracked[@]}" | awk '!seen[$0]++'
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

classify_services() {
  local file
  local -A targets=()
  local has_relevant=0
  local target_count=0

  for file in "$@"; do
    case "$file" in
      docs/*|README.md|CHANGELOG.md|CONTRIBUTING.md|LICENSE|SECURITY.md|THIRD_PARTY_LICENSES.md|tests/*|archive/*|examples/*)
        ;;
      src/gui/*|src/gui/**/*|scripts/runtime/run_dashboard.py|images/*)
        targets[gui]=1
        has_relevant=1
        ;;
      src/api/*|src/api/**/*)
        targets[api]=1
        has_relevant=1
        ;;
      scripts/run_continuous_pipeline.py|src/worker/*|src/worker/**/*)
        targets[worker]=1
        has_relevant=1
        ;;
      Dockerfile|docker-compose.yml|docker-compose.yaml|compose.yml|compose.yaml|requirements.txt|requirements-docker.txt|pyproject.toml|alembic.ini|.env|.env.local|.env.example|migrations/*|migrations/**/*|scripts/docker/*|scripts/setup/*|scripts/db/*|src/*)
        targets[api]=1
        targets[gui]=1
        targets[worker]=1
        has_relevant=1
        ;;
      *)
        targets[api]=1
        targets[gui]=1
        targets[worker]=1
        has_relevant=1
        ;;
    esac
  done

  if (( ! has_relevant )); then
    return 1
  fi

  for file in api gui worker; do
    if [[ -n "${targets[$file]:-}" ]]; then
      ((target_count += 1))
    fi
  done

  if (( target_count > 1 )); then
    targets[api]=1
    targets[gui]=1
    targets[worker]=1
  fi

  if [[ -n "${targets[api]:-}" ]]; then
    printf '%s\n' api
  fi
  if [[ -n "${targets[gui]:-}" ]]; then
    printf '%s\n' gui
  fi
  if [[ -n "${targets[worker]:-}" ]]; then
    printf '%s\n' worker
  fi
}

print_summary() {
  local title="$1"
  shift

  printf '\n[%s]\n' "$title"
  printf '%s\n' "$@"
}

run_rebuild() {
  local services=("$@")
  local has_worker=0

  if printf '%s\n' "${services[@]}" | grep -qx 'worker'; then
    has_worker=1
  fi

  print_summary "Rebuild" "Services: ${services[*]}"

  if [[ "$COMPOSE_MODE" == "v2" ]]; then
    local cmd=(docker compose)
    if (( has_worker )); then
      cmd+=(--profile worker)
    fi
    cmd+=(up --build -d "${services[@]}")
    if (( DRY_RUN )); then
      printf 'Dry run: %s\n' "$(printf '%q ' "${cmd[@]}")"
      return
    fi
    "${cmd[@]}"
    return
  fi

  local build_cmd=(docker-compose build "${services[@]}")
  local rm_cmd=(docker-compose rm -f -s "${services[@]}")
  local up_cmd=(docker-compose up -d "${services[@]}")

  if (( has_worker )); then
    if (( DRY_RUN )); then
      printf 'Dry run: COMPOSE_PROFILES=worker %s\n' "$(printf '%q ' "${build_cmd[@]}")"
      printf 'Dry run: COMPOSE_PROFILES=worker %s\n' "$(printf '%q ' "${rm_cmd[@]}")"
      printf 'Dry run: COMPOSE_PROFILES=worker %s\n' "$(printf '%q ' "${up_cmd[@]}")"
      return
    fi
    COMPOSE_PROFILES=worker "${build_cmd[@]}"
    # docker-compose v1 can crash during recreate on newer Docker image metadata.
    # Removing only the affected service containers avoids the broken code path.
    COMPOSE_PROFILES=worker "${rm_cmd[@]}" >/dev/null 2>&1 || true
    COMPOSE_PROFILES=worker "${up_cmd[@]}"
  else
    if (( DRY_RUN )); then
      printf 'Dry run: %s\n' "$(printf '%q ' "${build_cmd[@]}")"
      printf 'Dry run: %s\n' "$(printf '%q ' "${rm_cmd[@]}")"
      printf 'Dry run: %s\n' "$(printf '%q ' "${up_cmd[@]}")"
      return
    fi
    "${build_cmd[@]}"
    # docker-compose v1 can crash during recreate on newer Docker image metadata.
    # Removing only the affected service containers avoids the broken code path.
    "${rm_cmd[@]}" >/dev/null 2>&1 || true
    "${up_cmd[@]}"
  fi
}

process_changes() {
  local changed_files=("$@")
  local services=()

  if (( ${#changed_files[@]} == 0 )); then
    echo "Keine geänderten Dateien gefunden."
    return 0
  fi

  mapfile -t services < <(classify_services "${changed_files[@]}" || true)

  print_summary "Geänderte Dateien" "${changed_files[@]}"

  if (( ${#services[@]} == 0 )); then
    echo "Nur Doku/Test-Dateien geändert. Kein Docker-Rebuild nötig."
    return 0
  fi

  run_rebuild "${services[@]}"
}

watch_loop() {
  local last_signature=""
  local current_signature=""
  local changed_files=()

  echo "Watch-Modus aktiv. Prüfe alle ${POLL_SECONDS}s auf Änderungen."

  while true; do
    mapfile -t changed_files < <(collect_changed_files)
    current_signature="$(printf '%s\n' "${changed_files[@]}" | sha256sum | awk '{print $1}')"

    if [[ "$current_signature" != "$last_signature" ]]; then
      if (( ${#changed_files[@]} > 0 )); then
        process_changes "${changed_files[@]}"
      else
        echo "Keine geänderten Dateien gefunden."
      fi
      last_signature="$current_signature"
    fi

    sleep "$POLL_SECONDS"
  done
}

ARGS=()

while (( $# > 0 )); do
  case "$1" in
    --watch)
      WATCH_MODE=1
      shift
      ;;
    --interval)
      POLL_SECONDS="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -z "${POLL_SECONDS}" || ! "${POLL_SECONDS}" =~ ^[0-9]+$ ]]; then
  echo "--interval muss eine ganze Zahl sein." >&2
  exit 1
fi

if (( WATCH_MODE )); then
  detect_compose_command
  watch_loop
  exit 0
fi

detect_compose_command

if (( ${#ARGS[@]} > 0 )); then
  mapfile -t ARGS < <(normalize_paths "${ARGS[@]}")
  process_changes "${ARGS[@]}"
else
  mapfile -t ARGS < <(collect_changed_files)
  process_changes "${ARGS[@]}"
fi
