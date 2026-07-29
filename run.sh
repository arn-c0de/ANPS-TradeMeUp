#!/usr/bin/env bash
# ============================================================================
# TradeMeUp - control script
# ============================================================================
#   ./run.sh install    create venv, prepare .env, build the images
#   ./run.sh start      bring the stack up and wait until it is healthy
#   ./run.sh stop       shut the stack down
#   ./run.sh restart    stop, then start
#   ./run.sh rebuild    rebuild the images from scratch and restart
#   ./run.sh status     containers, published ports, venv
#   ./run.sh smoke      connectivity checks + the full test suite, per test
#                       (--quick skips the suite)
#   ./run.sh test       only the test suite, per test with failure detail
#   ./run.sh logs       follow everything live: container output and the
#                       app's own logs/*.log (--containers / --files to
#                       narrow, or name a service: ./run.sh logs api)
# ============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

VENV_DIR="$ROOT_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python"
COMPOSE_TIMEOUT=180

# ---------------------------------------------------------------------------
# output helpers
# ---------------------------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    C_RESET=$'\033[0m'; C_RED=$'\033[31m'; C_GREEN=$'\033[32m'
    C_YELLOW=$'\033[33m'; C_BLUE=$'\033[34m'; C_BOLD=$'\033[1m'
else
    C_RESET=; C_RED=; C_GREEN=; C_YELLOW=; C_BLUE=; C_BOLD=
fi

info() { printf '%s==>%s %s\n' "$C_BLUE" "$C_RESET" "$*"; }
ok()   { printf '  %sok%s   %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '  %swarn%s %s\n' "$C_YELLOW" "$C_RESET" "$*"; }
fail() { printf '  %sFAIL%s %s\n' "$C_RED" "$C_RESET" "$*"; }
die()  { printf '%serror:%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; exit 1; }
head1() { printf '\n%s%s%s\n' "$C_BOLD" "$*" "$C_RESET"; }

# ---------------------------------------------------------------------------
# environment
# ---------------------------------------------------------------------------

# Read a single key out of .env. Deliberately NOT `source .env`: CORS_ORIGINS
# holds a JSON array that the shell would mangle, and exporting the whole file
# would shadow values the app expects to read itself.
env_get() {
    local key="$1" default="${2:-}" line
    [ -f "$ROOT_DIR/.env" ] || { printf '%s' "$default"; return; }
    line="$(grep -m1 -E "^[[:space:]]*${key}=" "$ROOT_DIR/.env" || true)"
    [ -n "$line" ] || { printf '%s' "$default"; return; }
    line="${line#*=}"
    line="${line%\"}"; line="${line#\"}"
    line="${line%\'}"; line="${line#\'}"
    printf '%s' "$line"
}

require_docker() {
    command -v docker >/dev/null 2>&1 || die "docker is not installed"
    docker compose version >/dev/null 2>&1 || die "the 'docker compose' plugin is missing"
    docker info >/dev/null 2>&1 || die "the docker daemon is not reachable (is it running? are you in the 'docker' group?)"
}

# The image creates its user with a fixed uid. logs/ and models/ are bind
# mounts, so that uid has to match whoever owns them on the host or the
# container cannot write to them.
build_args() {
    printf -- '--build-arg\nAPP_UID=%s\n--build-arg\nAPP_GID=%s\n' "$(id -u)" "$(id -g)"
}

compose_build() {
    local extra=("$@") args=()
    mapfile -t args < <(build_args)
    docker compose build "${args[@]}" "${extra[@]}"
}

# The port compose resolves for a service, with docker-compose.override.yml
# and every other overlay folded in. Reading POSTGRES_PORT out of .env would
# report the wrong number whenever an override file replaces the port list.
configured_port() {
    local svc="$1" target="$2" fallback="$3" out=""
    if command -v python3 >/dev/null 2>&1; then
        out="$(docker compose config --format json 2>/dev/null | python3 -c '
import json, sys
try:
    cfg = json.load(sys.stdin)
except Exception:
    sys.exit(1)
svc, target = sys.argv[1], int(sys.argv[2])
for p in cfg.get("services", {}).get(svc, {}).get("ports", []):
    if int(p.get("target") or 0) == target:
        print(p.get("published") or "")
        break
' "$svc" "$target" 2>/dev/null)" || out=""
    fi
    if [ -n "$out" ]; then printf '%s' "$out"; else printf '%s' "$fallback"; fi
}

published_port() {
    # Prefer the mapping docker reports for the live container; fall back to the
    # resolved config when the stack is down.
    local svc="$1" port="$2" fallback="$3" out
    if out="$(docker compose port "$svc" "$port" 2>/dev/null)" && [ -n "$out" ]; then
        printf '%s' "${out##*:}"
    else
        configured_port "$svc" "$port" "$fallback"
    fi
}

api_url() {
    printf 'http://%s:%s' "$(env_get BIND_HOST 127.0.0.1)" "$(published_port api 8000 8000)"
}

gui_url() {
    printf 'http://%s:%s' "$(env_get BIND_HOST 127.0.0.1)" "$(published_port gui 8050 8050)"
}

stack_running() {
    [ -n "$(docker compose ps --status running --quiet 2>/dev/null)" ]
}

# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------
ensure_env_file() {
    if [ -f "$ROOT_DIR/.env" ]; then
        ok ".env present"
        return
    fi
    [ -f "$ROOT_DIR/.env.example" ] || die ".env is missing and .env.example is not there to copy"

    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    chmod 600 "$ROOT_DIR/.env"

    # Both are required: compose refuses to start without POSTGRES_PASSWORD and
    # SECRET_KEY, and the sample values must never reach a real deployment.
    if command -v openssl >/dev/null 2>&1; then
        local secret pgpass
        secret="$(openssl rand -hex 32)"
        pgpass="$(openssl rand -hex 16)"
        if grep -qE '^[[:space:]]*SECRET_KEY=' "$ROOT_DIR/.env"; then
            sed -i "s|^[[:space:]]*SECRET_KEY=.*|SECRET_KEY=${secret}|" "$ROOT_DIR/.env"
        else
            printf '\nSECRET_KEY=%s\n' "$secret" >>"$ROOT_DIR/.env"
        fi
        if grep -qE '^[[:space:]]*POSTGRES_PASSWORD=' "$ROOT_DIR/.env"; then
            sed -i "s|^[[:space:]]*POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${pgpass}|" "$ROOT_DIR/.env"
        else
            printf 'POSTGRES_PASSWORD=%s\n' "$pgpass" >>"$ROOT_DIR/.env"
        fi
        ok ".env created from .env.example with generated SECRET_KEY and POSTGRES_PASSWORD"
    else
        warn ".env created from .env.example - set SECRET_KEY and POSTGRES_PASSWORD by hand (openssl not found)"
    fi
}

check_port_conflicts() {
    command -v ss >/dev/null 2>&1 || return 0
    stack_running && return 0  # our own containers would show up as conflicts

    local conflict=0 name port
    for pair in "postgres:$(configured_port postgres 5432 5432)" \
                "redis:$(configured_port redis 6379 6379)" \
                "api:$(configured_port api 8000 8000)" \
                "gui:$(configured_port gui 8050 8050)"; do
        name="${pair%%:*}"; port="${pair##*:}"
        if ss -ltn "sport = :${port}" 2>/dev/null | grep -q LISTEN; then
            fail "host port ${port} (${name}) is already in use"
            conflict=1
        fi
    done

    if [ "$conflict" -eq 1 ]; then
        warn "set POSTGRES_PORT / REDIS_PORT in .env, or edit docker-compose.override.yml"
        warn "these are host-side ports only - the containers always talk to each other internally"
    fi
    return 0
}

cmd_install() {
    local with_dev=0
    [ "${1:-}" = "--dev" ] && with_dev=1

    head1 "1/4  Python environment"
    command -v python3 >/dev/null 2>&1 || die "python3 is not installed"
    local pyver
    pyver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    case "$pyver" in
        3.1[1-9]|3.[2-9][0-9]|[4-9].*) ok "python $pyver" ;;
        *) die "python >= 3.11 required, found $pyver" ;;
    esac

    if [ ! -x "$VENV_PYTHON" ]; then
        info "creating venv in ./venv"
        python3 -m venv "$VENV_DIR"
    fi
    ok "venv ready"

    info "installing requirements.txt (this pulls torch via sentence-transformers and takes a while)"
    "$VENV_PYTHON" -m pip install --upgrade pip >/dev/null
    "$VENV_PYTHON" -m pip install -r "$ROOT_DIR/requirements.txt"
    if [ "$with_dev" -eq 1 ]; then
        info "installing dev tools"
        "$VENV_PYTHON" -m pip install ruff black mypy pre-commit ipython ipykernel
    fi
    ok "dependencies installed"

    head1 "2/4  Configuration"
    ensure_env_file

    head1 "3/4  Docker"
    require_docker
    ok "docker daemon reachable"
    docker compose config --quiet || die "docker-compose.yml is invalid"
    ok "compose config valid"
    check_port_conflicts

    head1 "4/4  Images"
    compose_build
    ok "images built"

    printf '\n%sInstall complete.%s Next: ./run.sh start\n' "$C_GREEN" "$C_RESET"
}

# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------
cmd_start() {
    require_docker
    check_port_conflicts
    info "starting stack"
    if ! docker compose up -d --wait --wait-timeout "$COMPOSE_TIMEOUT"; then
        fail "stack did not come up healthy"
        docker compose ps
        printf '\nlast lines from each service:\n'
        docker compose logs --tail 25
        return 1
    fi
    ok "all services healthy"
    cmd_status
    printf '\nrun %s./run.sh smoke%s to verify connectivity\n' "$C_BOLD" "$C_RESET"
}

cmd_stop() {
    require_docker
    info "stopping stack"
    docker compose down
    ok "stopped (the postgres volume is kept - use 'docker compose down -v' to wipe it)"
}

cmd_restart() {
    cmd_stop
    cmd_start
}

cmd_rebuild() {
    require_docker
    info "rebuilding images without cache"
    docker compose down
    compose_build --no-cache
    ok "images rebuilt"
    cmd_start
}

cmd_status() {
    require_docker
    head1 "Containers"
    docker compose ps --format 'table {{.Name}}\t{{.Service}}\t{{.Status}}' 2>/dev/null || docker compose ps

    head1 "Endpoints"
    if stack_running; then
        printf '  api      %s\n' "$(api_url)"
        printf '  docs     %s/docs\n' "$(api_url)"
        printf '  gui      %s\n' "$(gui_url)"
        printf '  postgres 127.0.0.1:%s\n' "$(published_port postgres 5432 5432)"
        printf '  redis    127.0.0.1:%s\n' "$(published_port redis 6379 6379)"
    else
        printf '  stack is not running\n'
    fi

    head1 "Host environment"
    if [ -x "$VENV_PYTHON" ]; then
        ok "venv: $("$VENV_PYTHON" --version 2>&1)"
    else
        warn "no venv - run ./run.sh install if you want to run the app outside docker"
    fi
    [ -f "$ROOT_DIR/.env" ] && ok ".env present" || warn ".env missing"
}

# Everything the program writes, live and in one stream.
#
# Container stdout is only half of it: the pipeline and the dashboard also
# write to logs/*.log, which is bind-mounted from the host. Following just one
# of the two sources shows a partial picture, and the gap is easy to miss
# because both look complete on their own.
cmd_logs() {
    require_docker

    local files_only=0 containers_only=0
    case "${1:-}" in
        --files)      files_only=1; shift ;;
        --containers) containers_only=1; shift ;;
    esac

    # A named service is a request for that container alone; hand it to
    # compose unchanged so its own flags keep working.
    if [ $# -gt 0 ]; then
        docker compose logs -f --tail 100 "$@"
        return
    fi

    local pids=()

    # `tail | sed &` leaves two children but $! names only sed, so killing the
    # recorded pids alone would strand every tail. Everything started here is
    # a direct child of this shell, so sweep those too.
    stop_followers() {
        local pid
        for pid in "${pids[@]}"; do
            kill "$pid" 2>/dev/null
        done
        pkill -P $$ 2>/dev/null
        wait 2>/dev/null
        return 0
    }
    trap 'stop_followers; exit 0' INT TERM

    if [ "$files_only" -eq 0 ]; then
        docker compose logs -f --tail 50 &
        pids+=($!)
    fi

    if [ "$containers_only" -eq 0 ]; then
        local logfile label found=0
        for logfile in "$ROOT_DIR"/logs/*.log; do
            [ -f "$logfile" ] || continue
            found=1
            label="$(basename "$logfile" .log)"
            # -F keeps following across the truncation and rotation the app
            # does; sed -u so lines are not held back in a pipe buffer.
            tail -n 50 -F "$logfile" 2>/dev/null | sed -u "s|^|${label}  \||" &
            pids+=($!)
        done
        if [ "$found" -eq 0 ] && [ "$files_only" -eq 1 ]; then
            warn "no log files in logs/ yet - the app writes them once it runs"
        fi
    fi

    if [ "${#pids[@]}" -eq 0 ]; then
        warn "nothing to follow"
        return 0
    fi

    wait
}

# ---------------------------------------------------------------------------
# smoke
# ---------------------------------------------------------------------------
SMOKE_FAILURES=0

check() {
    local name="$1"; shift
    local out status=0
    out="$("$@" 2>&1)" || status=$?
    if [ "$status" -eq 0 ]; then
        if [ -n "$out" ]; then ok "$name -> $(printf '%s' "$out" | tr '\n' ' ' | cut -c1-90)"
        else ok "$name"; fi
    else
        fail "$name"
        [ -n "$out" ] && printf '%s\n' "$out" | sed 's/^/       /'
        SMOKE_FAILURES=$((SMOKE_FAILURES + 1))
    fi
    return 0
}

TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# The full suite, run inside the api container against the code that is
# actually deployed there - not the working tree. After editing source, run
# ./run.sh rebuild before trusting this.
run_test_suite() {
    local logfile xml details collected
    logfile="$(mktemp)"; xml="$(mktemp)"; details="$(mktemp)"

    if ! docker compose exec -T api sh -c 'python -c "import pytest"' >/dev/null 2>&1; then
        fail "pytest is not installed in the api image - run ./run.sh rebuild"
        SMOKE_FAILURES=$((SMOKE_FAILURES + 1))
        rm -f "$logfile" "$xml" "$details"
        return 0
    fi

    docker compose exec -T api sh -c \
        'cd /app && python -m pytest tests -q --tb=short --color=no -p no:cacheprovider \
             -o junit_family=xunit1 --junitxml=/tmp/run-sh-junit.xml' \
        >"$logfile" 2>&1 || true
    docker compose exec -T api cat /tmp/run-sh-junit.xml >"$xml" 2>/dev/null || true

    local verdict name reason
    while IFS=$'\t' read -r verdict name reason; do
        case "$verdict" in
            PASS) ok "$name"; TESTS_PASSED=$((TESTS_PASSED + 1)) ;;
            FAIL) fail "$name${reason:+ - $reason}"; TESTS_FAILED=$((TESTS_FAILED + 1)) ;;
            SKIP) warn "$name${reason:+ - $reason}"; TESTS_SKIPPED=$((TESTS_SKIPPED + 1)) ;;
        esac
    done < <(python3 "$ROOT_DIR/scripts/lib/junit_report.py" "$xml" "$details" 2>/dev/null || true)

    collected=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))
    if [ "$collected" -eq 0 ]; then
        # No report at all: pytest died before it could run anything, usually a
        # collection error. Its own output is the only thing worth showing.
        fail "the suite did not run"
        tail -30 "$logfile" | sed 's/^/       /'
        SMOKE_FAILURES=$((SMOKE_FAILURES + 1))
        rm -f "$logfile" "$xml" "$details"
        return 0
    fi

    printf '\n  %d tests: %d passed, %d failed, %d skipped\n' \
        "$collected" "$TESTS_PASSED" "$TESTS_FAILED" "$TESTS_SKIPPED"

    if [ "$TESTS_FAILED" -gt 0 ]; then
        printf '\n%sWhy they failed%s\n' "$C_BOLD" "$C_RESET"
        sed 's/^/  /' "$details"
        SMOKE_FAILURES=$((SMOKE_FAILURES + TESTS_FAILED))
    fi

    rm -f "$logfile" "$xml" "$details"
    return 0
}

# Run one SQL statement as the application role. The statement travels as an
# environment variable so it never has to survive a second round of shell
# quoting inside the container.
pg_query() {
    docker compose exec -T -e SQL="$1" postgres \
        sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$SQL"'
}

# Each check is a function so the quoting stays readable.
smoke_compose_valid()  { docker compose config --quiet; }
smoke_pg_role()        { pg_query "select current_user"; }
smoke_pg_schema()      { pg_query "select count(*) || ' tables in public' from pg_tables where schemaname = 'public'"; }
smoke_pg_extensions()  { pg_query "select string_agg(extname, ',') from pg_extension where extname in ('vector', 'uuid-ossp')"; }
smoke_redis_ping()     { docker compose exec -T redis redis-cli ping; }
smoke_api_to_pg()      { docker compose exec -T api python -c "import os,psycopg;
c=psycopg.connect(os.environ['DATABASE_URL']);
print(c.execute('select 1').fetchone()[0] and 'connected')"; }
smoke_api_to_redis()   { docker compose exec -T api python -c "import os,redis;
u=os.environ['REDIS_URL'];
assert 'localhost' not in u and '127.0.0.1' not in u, f'REDIS_URL points at the container itself: {u}';
print(u, redis.from_url(u).ping())"; }
smoke_alembic()        { docker compose exec -T api sh -c "alembic current 2>/dev/null | grep -q head && echo 'at head'"; }
smoke_api_health()     { curl -fsS --max-time 10 "$(api_url)/health"; }
smoke_api_v1()         { curl -fsS -o /dev/null -w '%{http_code}' --max-time 10 "$(api_url)/docs"; }
smoke_gui_http()       { curl -fsS -o /dev/null -w '%{http_code}' --max-time 15 "$(gui_url)/"; }

cmd_test() {
    require_docker
    stack_running || die "the stack is not running - start it first with ./run.sh start"
    head1 "Test suite"
    run_test_suite
    printf '\n'
    [ "$TESTS_FAILED" -eq 0 ] || return 1
    printf '%sall tests passed%s\n' "$C_GREEN" "$C_RESET"
}

cmd_smoke() {
    local run_tests=1
    [ "${1:-}" = "--quick" ] && run_tests=0

    require_docker
    if ! stack_running; then
        die "the stack is not running - start it first with ./run.sh start"
    fi
    command -v curl >/dev/null 2>&1 || warn "curl not found, skipping the HTTP checks"

    head1 "Configuration"
    check "compose config parses"           smoke_compose_valid

    head1 "Postgres"
    check "login as the application role"   smoke_pg_role
    check "schema present"                  smoke_pg_schema
    check "extensions installed"            smoke_pg_extensions

    head1 "Redis"
    check "redis responds to ping"          smoke_redis_ping

    head1 "Container to container"
    check "api reaches postgres"            smoke_api_to_pg
    check "api reaches redis"               smoke_api_to_redis
    check "migrations at head"              smoke_alembic

    if command -v curl >/dev/null 2>&1; then
        head1 "Host to container"
        check "api /health"                 smoke_api_health
        check "api /docs"                   smoke_api_v1
        check "gui responds"                smoke_gui_http
    fi

    if [ "$run_tests" -eq 1 ]; then
        head1 "Test suite"
        run_test_suite
    else
        head1 "Test suite"
        warn "skipped (--quick)"
    fi

    printf '\n'
    if [ "$SMOKE_FAILURES" -eq 0 ]; then
        printf '%sall smoke checks passed%s\n' "$C_GREEN" "$C_RESET"
        return 0
    fi
    printf '%s%d smoke check(s) failed%s\n' "$C_RED" "$SMOKE_FAILURES" "$C_RESET"
    return 1
}

# ---------------------------------------------------------------------------
usage() {
    # Print the header comment block: from line 2 up to the first line that is
    # not a comment, minus that line. Survives edits to the block's length.
    sed -n '2,/^[^#]/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//'
}

main() {
    local cmd="${1:-}"
    [ $# -gt 0 ] && shift || true
    case "$cmd" in
        install) cmd_install "$@" ;;
        start)   cmd_start ;;
        stop)    cmd_stop ;;
        restart) cmd_restart ;;
        rebuild) cmd_rebuild ;;
        status)  cmd_status ;;
        smoke)   cmd_smoke "$@" ;;
        test)    cmd_test ;;
        logs)    cmd_logs "$@" ;;
        ""|-h|--help|help) usage ;;
        *) printf '%sunknown command: %s%s\n\n' "$C_RED" "$cmd" "$C_RESET" >&2; usage >&2; exit 2 ;;
    esac
}

main "$@"
