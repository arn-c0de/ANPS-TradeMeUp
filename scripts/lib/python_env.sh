# Shared helpers for the wrapper scripts the GUI launches.
# Sourced, not executed. Call from the project root.

# Pick the interpreter to run project scripts with.
#
# On a developer machine the dependencies live in ./venv. Inside the container
# they are installed system-wide during the image build and no venv exists, so
# insisting on venv/bin/python made every pipeline the GUI starts fail with
# "Virtual environment not found". Prefer the venv, fall back to the
# interpreter on PATH, and only give up when there is none.
#
# Sets PYTHON_BIN.
resolve_python() {
    if [ -x "venv/bin/python" ]; then
        PYTHON_BIN="$(pwd)/venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python)"
    else
        echo "ERROR: no Python interpreter found."
        echo ""
        echo "On the host, create the project venv:"
        echo "  python3 -m venv venv"
        echo "  venv/bin/pip install -r requirements.txt"
        echo "or use ./run.sh install"
        return 1
    fi
    return 0
}

# Keep a terminal window open after the run, but only when one is attached.
# The GUI also starts these wrappers as a plain background process (in the
# container, and on any desktop without a supported terminal emulator), where
# there is no stdin to read from.
pause_if_interactive() {
    [ -t 0 ] || return 0
    read -r -p "${1:-Press enter to close this window...}" _ || true
}
