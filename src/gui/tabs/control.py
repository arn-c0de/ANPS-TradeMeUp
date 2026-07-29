"""
Agent Control Tab - Start, Stop and Monitor Agents
"""

import logging
import os
import platform
import re
import shlex
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html

from src.models.database import SessionLocal
from src.models.system_logs import SystemLog
from src.utils.activity_logger import activity_logger
from src.utils.process_utils import check_process_running, stop_process

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
logger = logging.getLogger(__name__)

# Detect platform
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'
IS_MAC = platform.system() == 'Darwin'
_CONTINUOUS_PIPELINE_SCRIPT = "scripts/run_continuous_pipeline.py"
_PIPELINE_ACTIVITY_WINDOW_SECONDS = 900
_PIPELINE_LOG_FILES = (
    Path("logs/pipeline_activity.log"),
    Path("logs/dashboard.log"),
)


def _find_continuous_pipeline_pid():
    """Find a locally visible continuous pipeline process by command line."""
    try:
        import psutil
    except ImportError:
        return None

    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            if not cmdline:
                continue
            if _CONTINUOUS_PIPELINE_SCRIPT in " ".join(cmdline) and proc.pid != os.getpid():
                return proc.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def _has_recent_pipeline_activity(window_seconds: int = _PIPELINE_ACTIVITY_WINDOW_SECONDS) -> bool:
    """Infer pipeline activity from the shared DB log stream."""
    cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
    activity_signals = (
        "Continuous Pipeline Mode STARTED",
        "Starting Pipeline Iteration #",
        "All articles fully processed, waiting",
        "Pipeline console started",
        "Pipeline process started",
        "Full MVP Pipeline console opened",
        "Quick Test console opened",
    )
    stop_signals = (
        "Continuous Pipeline STOPPED",
        "Pipeline stopped by user",
    )

    try:
        with SessionLocal() as db:
            entries = (
                db.query(SystemLog)
                .filter(
                    SystemLog.timestamp >= cutoff,
                    SystemLog.source.in_(["pipeline", "control"]),
                )
                .order_by(SystemLog.timestamp.desc())
                .limit(50)
                .all()
            )
    except Exception:
        entries = []

    for entry in entries:
        message = entry.message or ""
        if any(signal in message for signal in stop_signals):
            return False
        if any(signal in message for signal in activity_signals):
            return True

    for log_path in _PIPELINE_LOG_FILES:
        if not log_path.exists():
            continue
        try:
            with open(log_path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-120:]
        except OSError:
            continue

        for line in reversed(lines):
            if not line.strip():
                continue
            if any(signal in line for signal in stop_signals):
                return False
            if any(signal in line for signal in activity_signals):
                return True
    return False


def _resolve_continuous_pipeline_state(current_state):
    """Reconstruct pipeline state from runtime signals instead of only the Dash store."""
    state = current_state or {}
    pid = state.get("pid")

    if pid and check_process_running(pid):
        return {"running": True, "pid": pid}

    local_pid = _find_continuous_pipeline_pid()
    if local_pid:
        return {"running": True, "pid": local_pid}

    if _has_recent_pipeline_activity():
        return {"running": True, "pid": None}

    return {"running": False, "pid": None}


def _request_continuous_pipeline_stop():
    """Send a cross-process stop request through the shared log table."""
    activity_logger.log_activity(
        "STOP_REQUEST",
        "WARNING",
        source="control",
        component="continuous_pipeline",
        details={"requested_at": datetime.now(UTC).isoformat()},
    )

# Wrapper arguments are built from GUI state, and GUI state is attacker-controlled:
# Dash callbacks are plain HTTP endpoints, so a client can put anything in a
# State value. Every argument must therefore survive this allowlist before it
# reaches a terminal emulator, several of which need a shell string.
_SAFE_ARG_RE = re.compile(r"^[A-Za-z0-9_.:=/@+-]+$")


def _coerce_batch_size(value, default: int = 50, minimum: int = 1, maximum: int = 10000) -> int:
    """Clamp a GUI-supplied batch size to a sane integer, falling back to a default."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def _validate_args(args):
    """Return args as a list, rejecting anything with shell-significant characters."""
    validated = []
    for arg in args or []:
        arg = str(arg)
        if not _SAFE_ARG_RE.match(arg):
            raise ValueError(f"Refusing to pass unsafe command argument: {arg!r}")
        validated.append(arg)
    return validated


def open_terminal_with_command(script_path, args=None, title="TradeMeUp"):
    """Open a new terminal window and run a command (cross-platform).

    ``args`` is a list of argument strings. It is validated against an allowlist
    and quoted for the target shell; never interpolate raw user input here.
    """
    script_path = Path(script_path).absolute()
    args = _validate_args(args)

    if IS_WINDOWS:
        # cmd.exe 'start' takes a command line, not an argv list. Arguments are
        # allowlisted above, so no cmd metacharacters can survive to this point.
        joined = subprocess.list2cmdline(args)
        cmd = f'start "{title}" /D "{Path.cwd()}" "{script_path}" {joined}'
        proc = subprocess.Popen(cmd, shell=True, cwd=str(Path.cwd()))
        return proc

    elif IS_LINUX:
        # Linux: try different terminal emulators
        terminals = [
            ['gnome-terminal', '--', 'bash', '-c'],
            ['xterm', '-hold', '-e'],
            ['konsole', '--hold', '-e'],
            ['xfce4-terminal', '--hold', '-e'],
        ]

        # shlex.quote every component; the emulators below need a shell string.
        command = " ".join(shlex.quote(part) for part in [str(script_path), *args])
        command = f"{command}; exec bash"

        for term in terminals:
            try:
                if subprocess.run(['which', term[0]], capture_output=True).returncode == 0:
                    proc = subprocess.Popen(term + [command], cwd=str(Path.cwd()))
                    return proc
            except (FileNotFoundError, subprocess.SubprocessError):
                continue

        # Fallback: run in background without terminal
        logger.warning("No terminal emulator found, running in background")
        proc = subprocess.Popen([str(script_path), *args], cwd=str(Path.cwd()))
        return proc

    elif IS_MAC:
        # macOS: use Terminal.app. The inner command is a shell string embedded in
        # an AppleScript string literal, so quote for both layers.
        inner = " ".join(shlex.quote(part) for part in [str(script_path), *args])
        command = f"cd {shlex.quote(str(Path.cwd()))} && {inner}"
        script = f'tell application "Terminal" to do script "{command}"'
        proc = subprocess.Popen(['osascript', '-e', script], cwd=str(Path.cwd()))
        return proc

    else:
        raise OSError(f"Unsupported platform: {platform.system()}")


def create_layout():
    """Create agent control tab layout"""
    return dbc.Container([
        # Control Panel
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🎮 Pipeline Control Panel")),
                    dbc.CardBody([
                        dbc.Row([
                            # Full Pipeline
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.H6("🚀 Full MVP Pipeline", className="text-primary"),
                                        html.P("Run all 8 agents sequentially", className="text-muted small"),
                                        dbc.Button(
                                            "Run Full Pipeline",
                                            id="btn-run-full-pipeline",
                                            color="primary",
                                            className="w-100 mb-2"
                                        ),
                                        html.Small("~15 minutes", className="text-muted")
                                    ])
                                ], className="h-100")
                            ], width=4),

                            # Quick Test
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.H6("⚡ Quick Test", className="text-success"),
                                        html.P("Process 3 articles (fast test)", className="text-muted small"),
                                        dbc.Button(
                                            "Run Quick Test",
                                            id="btn-run-quick-test",
                                            color="success",
                                            className="w-100 mb-2"
                                        ),
                                        html.Small("~2 minutes", className="text-muted")
                                    ])
                                ], className="h-100")
                            ], width=4),

                            # Single Agent
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.H6("🎯 Single Agent", className="text-info"),
                                        html.P("Run individual agent", className="text-muted small"),
                                        dcc.Dropdown(
                                            id="agent-selector",
                                            options=[
                                                {"label": "Agent 1: Ingestion", "value": "ingestion"},
                                                {"label": "Agent 1.5: Data Quality", "value": "quality"},
                                                {"label": "Agent 2: Content Understanding", "value": "content"},
                                                {"label": "Agent 3: Entity Mapping", "value": "entity"},
                                                {"label": "Agent 4: Impact Scoring", "value": "impact"},
                                                {"label": "Agent 4.5: Surprise Quantification", "value": "surprise"},
                                                {"label": "Agent 5: Regime Detection", "value": "regime"},
                                                {"label": "Agent 6: Predictions", "value": "predictions"},
                                                {"label": "Agent 7: Fact Verification", "value": "fact_verification"},
                                                {"label": "Agent 8: Correlation Analysis", "value": "correlation"},
                                                {"label": "Agent 9: Signal Decay", "value": "signal_decay"},
                                                {"label": "Agent 10: Scenario Generation", "value": "scenarios"},
                                                {"label": "Agent 11: Confidence Calibration", "value": "calibration"},
                                                {"label": "Agent 12: Meta Strategy", "value": "meta_strategy"},
                                                {"label": "Agent 13: Model Performance", "value": "performance"},
                                                {"label": "Agent 14: A/B Testing", "value": "ab_testing"}
                                            ],
                                            placeholder="Select agent...",
                                            className="mb-2"
                                        ),
                                        dbc.Button(
                                            "Run Selected Agent",
                                            id="btn-run-single-agent",
                                            color="info",
                                            className="w-100",
                                            disabled=True
                                        )
                                    ])
                                ], className="h-100")
                            ], width=4)
                        ])
                    ])
                ])
            ], width=12)
        ], className="mb-3"),

        # Backfill Operations Section
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🔄 Backfill Operations")),
                    dbc.CardBody([
                        html.P("Process existing articles for missing analyses", className="text-muted mb-3"),
                        dbc.Row([
                            # Full Backfill
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.H6("🔄 Full Backfill", className="text-warning"),
                                        html.P("Complete all missing analyses", className="text-muted small"),
                                        dbc.Button(
                                            "Run Full Backfill",
                                            id="btn-run-full-backfill",
                                            color="warning",
                                            className="w-100 mb-2"
                                        ),
                                        html.Small("All phases", className="text-muted")
                                    ])
                                ], className="h-100")
                            ], width=3),

                            # Selective Backfill
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.H6("🎯 Selective Backfill", className="text-info"),
                                        html.P("Choose specific analyses", className="text-muted small"),
                                        dbc.Checklist(
                                            id="check-backfill-phases",
                                            options=[
                                                {"label": " Quality Assessment", "value": "quality"},
                                                {"label": " Content Understanding", "value": "content"},
                                                {"label": " Entity Mapping", "value": "entities"},
                                                {"label": " Fact Verification", "value": "facts"},
                                                {"label": " Surprise Scoring", "value": "surprises"},
                                                {"label": " Impact Scoring", "value": "impact"},
                                                {"label": " Predictions", "value": "predictions"}
                                            ],
                                            value=["facts", "surprises", "predictions"],
                                            className="small"
                                        ),
                                        dbc.Button(
                                            "Run Selected Phases",
                                            id="btn-run-selective-backfill",
                                            color="info",
                                            className="w-100 mt-2",
                                            size="sm"
                                        )
                                    ])
                                ], className="h-100")
                            ], width=5),

                            # Backfill Options
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.H6("⚙️ Backfill Settings", className="text-secondary"),
                                        dbc.Label("Batch Size:", className="small"),
                                        dcc.Slider(
                                            id="slider-backfill-batch",
                                            min=10,
                                            max=100,
                                            step=10,
                                            value=50,
                                            marks={10: "10", 50: "50", 100: "100"},
                                            tooltip={"placement": "bottom", "always_visible": True}
                                        ),
                                        html.Small("Articles per batch", className="text-muted d-block mb-2"),
                                        dbc.Checklist(
                                            id="check-backfill-openai",
                                            options=[{"label": " Use OpenAI (faster)", "value": "openai"}],
                                            value=["openai"],
                                            className="small"
                                        )
                                    ])
                                ], className="h-100")
                            ], width=4)
                        ])
                    ])
                ])
            ], width=12)
        ], className="mb-3"),

        # Pipeline Options
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H6("⚙️ Pipeline Options")),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Articles to Process:"),
                                dcc.Slider(
                                    id="slider-article-limit",
                                    min=1,
                                    max=50,
                                    step=1,
                                    value=10,
                                    marks={1: "1", 10: "10", 25: "25", 50: "50"},
                                    tooltip={"placement": "bottom", "always_visible": True}
                                )
                            ], width=4),
                            dbc.Col([
                                dbc.Checklist(
                                    id="check-force-refresh",
                                    options=[{"label": " Force Refresh (ignore cache)", "value": "force"}],
                                    value=[],
                                    className="mt-4"
                                )
                            ], width=4),
                            dbc.Col([
                                dbc.Checklist(
                                    id="check-verbose",
                                    options=[{"label": " Verbose Logging", "value": "verbose"}],
                                    value=["verbose"],
                                    className="mt-4"
                                )
                            ], width=4)
                        ])
                    ])
                ])
            ], width=12)
        ], className="mb-3"),

        # Status Display
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H6("📊 Execution Status", className="d-inline"),
                        dbc.Badge("Idle", id="badge-pipeline-status", color="secondary", className="ms-2")
                    ]),
                    dbc.CardBody([
                        html.Div(id="pipeline-status-display", children=[
                            html.P("No pipeline running. Select an option above to start.", className="text-muted")
                        ])
                    ])
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H6("📝 Execution Log")),
                    dbc.CardBody([
                        dcc.Textarea(
                            id="pipeline-log",
                            value="Waiting for pipeline execution...\n",
                            style={"width": "100%", "height": "300px", "fontFamily": "monospace", "fontSize": "12px"},
                            readOnly=True
                        )
                    ])
                ])
            ], width=6)
        ], className="mb-3"),

        # Recent Executions
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H6("📜 Recent Executions")),
                    dbc.CardBody([
                        html.Div(id="recent-executions")
                    ])
                ])
            ], width=12)
        ]),

        # Hidden stores for state management
        dcc.Store(id="store-pipeline-state", data={"running": False, "process_id": None}),
        dcc.Store(id="store-execution-history", data=[]),
        dcc.Interval(id="interval-pipeline-monitor", interval=2000, disabled=True)  # 2 seconds when active

    ], fluid=True)


def get_recent_executions():
    """Get recent execution history"""
    # This would be loaded from a database or log file in production
    # For now, return placeholder
    return html.Div([
        html.Small("Execution history will appear here", className="text-muted")
    ])


def format_pipeline_status(status):
    """Format pipeline status display"""
    if not status or not status.get("running"):
        return html.Div([
            html.P("No pipeline running.", className="text-muted"),
            html.Small("Use the control panel above to start a pipeline.", className="text-muted")
        ])

    return html.Div([
        dbc.Progress(value=status.get("progress", 0), className="mb-2"),
        html.P([
            html.Strong("Current Phase: "),
            html.Span(status.get("phase", "Unknown"), className="text-primary")
        ]),
        html.P([
            html.Strong("Started: "),
            html.Span(status.get("start_time", "Unknown"))
        ]),
        html.P([
            html.Strong("Articles Processed: "),
            html.Span(f"{status.get('processed', 0)}/{status.get('total', 0)}")
        ])
    ])


def run_pipeline_command(command_type, options=None):
    """
    Execute pipeline command
    
    Args:
        command_type: 'full', 'quick', 'backfill', 'backfill_selective', or agent name
        options: dict with limit, force, verbose flags, backfill phases, batch_size
    """
    options = options or {}

    # Get Python executable path
    python_exe = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")

    # Build command based on type
    if command_type == "full":
        script = os.path.join(PROJECT_ROOT, "scripts", "run_mvp_pipeline.py")
        cmd = [python_exe, script]
    elif command_type == "quick":
        script = os.path.join(PROJECT_ROOT, "scripts", "run_mvp_pipeline.py")
        cmd = [python_exe, script, "--quick"]
    elif command_type == "backfill":
        # Full backfill - all phases
        script = os.path.join(PROJECT_ROOT, "scripts", "backfill_all_agents.py")
        cmd = [python_exe, script]
        if options.get("batch_size"):
            cmd.extend(["--batch-size", str(options["batch_size"])])
    elif command_type == "backfill_selective":
        # Selective backfill - skip phases not selected
        script = os.path.join(PROJECT_ROOT, "scripts", "backfill_all_agents.py")
        cmd = [python_exe, script]

        # Add skip flags for unselected phases
        all_phases = ["quality", "content", "entities", "facts", "surprises", "impact", "predictions"]
        selected_phases = options.get("phases", [])
        for phase in all_phases:
            if phase not in selected_phases:
                cmd.append(f"--skip-{phase}")

        if options.get("batch_size"):
            cmd.extend(["--batch-size", str(options["batch_size"])])
    elif command_type == "ingestion":
        script = os.path.join(PROJECT_ROOT, "scripts", "run_ingestion.py")
        cmd = [python_exe, script]
    else:
        # For other agents, we'd need individual scripts or parameters
        return None, "Agent-specific scripts not yet implemented"

    # Add options
    if options.get("limit"):
        cmd.extend(["--limit", str(options["limit"])])
    if options.get("force"):
        cmd.append("--force")
    if options.get("verbose"):
        cmd.append("--verbose")

    try:
        # Start process (non-blocking)
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=PROJECT_ROOT
        )
        return process, None
    except Exception as e:
        return None, str(e)


def get_process_output(process):
    """Get output from running process"""
    if not process:
        return ""

    try:
        # Non-blocking read
        output = []
        while True:
            line = process.stdout.readline()
            if not line:
                break
            output.append(line)
        return "".join(output)
    except Exception:
        return ""


def register_callbacks(app):
    """Register control tab callbacks (continuous pipeline, RSS fetch, status)."""

    @app.callback(
        [
            Output("continuous-pipeline-state", "data"),
            Output("btn-start-continuous", "disabled"),
            Output("btn-stop-continuous", "disabled"),
        ],
        [Input("btn-start-continuous", "n_clicks"), Input("btn-stop-continuous", "n_clicks")],
        State("continuous-pipeline-state", "data"),
        prevent_initial_call=True,
    )
    def control_continuous_pipeline(start_clicks, stop_clicks, current_state):
        ctx = dash.callback_context
        if not ctx.triggered:
            return dash.no_update
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if button_id == "btn-start-continuous":
            logger.info("Starting continuous pipeline with Python: %s", sys.executable)

            # Use platform-specific wrapper
            if IS_WINDOWS:
                wrapper_script = Path("scripts/run_continuous_pipeline_wrapper.bat").absolute()
            else:
                wrapper_script = Path("scripts/run_continuous_pipeline_wrapper.sh").absolute()

            if not wrapper_script.exists():
                error_msg = f"Wrapper script not found: {wrapper_script}"
                activity_logger.log_activity(error_msg, "ERROR")
                logger.error(error_msg)
                return dash.no_update
            try:
                process = open_terminal_with_command(wrapper_script, ["--interval", "300"], "ANPS-TradeMeUp Pipeline")
                logger.info("Started pipeline with PID: %s", process.pid)
                activity_logger.log_activity(
                    "Continuous Pipeline console opened - Check the new terminal window",
                    "SUCCESS",
                )
                logger.info("Pipeline console started with PID: %s", process.pid)
                return ({"running": True, "pid": process.pid}, True, False)
            except Exception as e:
                activity_logger.log_activity(f"Failed to start continuous pipeline: {e}", "ERROR")
                logger.error("Failed to start: %s", e, exc_info=True)
                return dash.no_update
        if button_id == "btn-stop-continuous":
            resolved_state = _resolve_continuous_pipeline_state(current_state)
            stop_pid = resolved_state.get("pid")
            stop_message = None

            if stop_pid:
                success, message = stop_process(stop_pid)
                if success:
                    stop_message = message
                    activity_logger.log_activity(f"Continuous Pipeline STOPPED: {message}", "INFO")
                else:
                    activity_logger.log_activity(f"Warning stopping pipeline: {message}", "WARNING")
            _request_continuous_pipeline_stop()
            if stop_message is None:
                activity_logger.log_activity(
                    "Continuous Pipeline stop requested via shared control signal",
                    "INFO",
                )
            return ({"running": False, "pid": None}, False, True)
        return dash.no_update

    @app.callback(
        [
            Output("continuous-pipeline-state", "data", allow_duplicate=True),
            Output("btn-start-continuous", "disabled", allow_duplicate=True),
            Output("btn-stop-continuous", "disabled", allow_duplicate=True),
        ],
        Input("interval-component", "n_intervals"),
        State("continuous-pipeline-state", "data"),
        prevent_initial_call=True,
    )
    def sync_continuous_pipeline_state(n, current_state):
        state = _resolve_continuous_pipeline_state(current_state)
        return state, state["running"], False

    @app.callback(
        Output("rss-fetch-status-store", "data"),
        Input("btn-fetch-rss-only", "n_clicks"),
        prevent_initial_call=True,
    )
    def fetch_rss_only(n_clicks):
        if not n_clicks:
            return dash.no_update
        try:
            # Use platform-specific wrapper
            if IS_WINDOWS:
                wrapper_script = Path("scripts/run_rss_fetch_wrapper.bat").absolute()
            else:
                wrapper_script = Path("scripts/run_rss_fetch_wrapper.sh").absolute()

            if not wrapper_script.exists():
                error_msg = f"RSS fetch script not found: {wrapper_script}"
                activity_logger.log_activity(error_msg, "ERROR")
                logger.error(error_msg)
                return {"status": "error", "message": str(error_msg)}

            process = open_terminal_with_command(wrapper_script, [], "ANPS-TradeMeUp RSS Fetch")
            logger.info("RSS fetch terminal opened with PID: %s", process.pid)
            activity_logger.log_activity(
                "RSS Feed Fetch: Terminal window opened - Check the new window",
                "INFO",
            )
            return {"status": "success", "message": "RSS fetch started in new terminal"}
        except Exception as e:
            logger.error("Error opening RSS fetch terminal: %s", e, exc_info=True)
            activity_logger.log_activity(f"RSS Fetch Error: {e}", "ERROR")
            return {"status": "error", "message": str(e)}

    @app.callback(
        Output("continuous-status", "children"),
        Input("interval-component", "n_intervals"),
        State("continuous-pipeline-state", "data"),
    )
    def update_continuous_status(n, state):
        resolved_state = _resolve_continuous_pipeline_state(state)
        if resolved_state.get("running"):
            return html.Div([
                html.Span("🔄 ", className="text-success"),
                html.Small("Auto Mode", className="text-success fw-bold"),
            ])
        return html.Div([
            html.Span("⏸️ ", className="text-muted"),
            html.Small("Manual Mode", className="text-muted"),
        ])

    @app.callback(
        Output("btn-run-single-agent", "disabled"),
        Input("agent-selector", "value"),
    )
    def toggle_single_agent_button(selected_agent):
        return selected_agent is None

    @app.callback(
        [
            Output("pipeline-log", "value", allow_duplicate=True),
            Output("badge-pipeline-status", "children", allow_duplicate=True),
            Output("badge-pipeline-status", "color", allow_duplicate=True),
        ],
        Input("interval-component", "n_intervals"),
        State("store-pipeline-state", "data"),
        prevent_initial_call=True,
    )
    def update_pipeline_log(n, state):
        if not state or not state.get("running"):
            return dash.no_update
        try:
            output_file = Path("logs") / "pipeline_output.log"
            if output_file.exists():
                with open(output_file, encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    recent = "".join(lines[-100:])
                if "PIPELINE COMPLETE" in recent or "COMPLETED SUCCESSFULLY" in recent:
                    return recent, "COMPLETED", "success"
                if "ERROR" in recent and "Traceback" in recent:
                    return recent, "ERROR", "danger"
                return recent, "RUNNING", "warning"
            log_file = Path("logs") / "pipeline_activity.log"
            if log_file.exists():
                with open(log_file, encoding="utf-8", errors="ignore") as f:
                    recent = "".join(f.readlines()[-50:])
                return recent, "RUNNING", "warning"
        except Exception:
            pass
        return dash.no_update

    @app.callback(
        [
            Output("store-pipeline-state", "data", allow_duplicate=True),
            Output("pipeline-log", "value", allow_duplicate=True),
            Output("badge-pipeline-status", "children", allow_duplicate=True),
            Output("badge-pipeline-status", "color", allow_duplicate=True),
        ],
        Input("btn-run-full-pipeline", "n_clicks"),
        [State("slider-article-limit", "value"), State("check-force-refresh", "value"), State("check-verbose", "value")],
        prevent_initial_call=True,
    )
    def run_full_pipeline(n_clicks, limit, force, verbose):
        if not n_clicks:
            return dash.no_update
        activity_logger.log_activity("User initiated Full MVP Pipeline from GUI", "INFO")
        activity_logger.log_pipeline_start("ANPS-TradeMeUp MVP Pipeline (GUI)")

        # Use platform-specific wrapper
        if IS_WINDOWS:
            wrapper = Path("scripts/run_mvp_pipeline_wrapper.bat").absolute()
        else:
            wrapper = Path("scripts/run_mvp_pipeline_wrapper.sh").absolute()

        if not wrapper.exists():
            msg = f"Wrapper script not found: {wrapper}"
            activity_logger.log_activity(msg, "ERROR")
            return {"running": False}, msg, "ERROR", "danger"
        try:
            proc = open_terminal_with_command(wrapper, [], "ANPS-TradeMeUp MVP Pipeline")
        except Exception as e:
            activity_logger.log_agent_error("Full Pipeline (GUI)", str(e))
            return {"running": False}, str(e), "ERROR", "danger"
        state = {"running": True, "process_id": proc.pid, "start_time": datetime.now().strftime("%H:%M:%S"), "type": "full_pipeline"}
        log = f"[{datetime.now().strftime('%H:%M:%S')}] Full MVP Pipeline console opened\nProcess ID: {proc.pid}\nArticles: {limit}\n" + "-" * 60 + "\nCheck the new terminal window for live progress!\n"
        activity_logger.log_activity(f"Pipeline process started (PID: {proc.pid})", "SUCCESS")
        return state, log, "RUNNING", "warning"

    @app.callback(
        [
            Output("store-pipeline-state", "data", allow_duplicate=True),
            Output("pipeline-log", "value", allow_duplicate=True),
            Output("badge-pipeline-status", "children", allow_duplicate=True),
            Output("badge-pipeline-status", "color", allow_duplicate=True),
        ],
        Input("btn-run-quick-test", "n_clicks"),
        prevent_initial_call=True,
    )
    def run_quick_test(n_clicks):
        if not n_clicks:
            return dash.no_update
        activity_logger.log_activity("User initiated Quick Test from GUI", "INFO")

        # Use platform-specific wrapper
        if IS_WINDOWS:
            wrapper = Path("scripts/run_mvp_pipeline_wrapper.bat").absolute()
        else:
            wrapper = Path("scripts/run_mvp_pipeline_wrapper.sh").absolute()

        if not wrapper.exists():
            msg = f"Wrapper script not found: {wrapper}"
            activity_logger.log_activity(msg, "ERROR")
            return {"running": False}, msg, "ERROR", "danger"

        try:
            proc = open_terminal_with_command(wrapper, ["--quick"], "ANPS-TradeMeUp Quick Test")
        except Exception as e:
            activity_logger.log_agent_error("Quick Test (GUI)", str(e))
            return {"running": False}, str(e), "ERROR", "danger"
        state = {"running": True, "process_id": proc.pid, "start_time": datetime.now().strftime("%H:%M:%S"), "type": "quick_test"}
        log = f"[{datetime.now().strftime('%H:%M:%S')}] Quick Test console opened\nProcess ID: {proc.pid}\n" + "-" * 60 + "\nCheck the new terminal window for live progress!\n"
        activity_logger.log_activity(f"Quick test started (PID: {proc.pid})", "SUCCESS")
        return state, log, "RUNNING", "warning"

    @app.callback(
        [
            Output("store-pipeline-state", "data", allow_duplicate=True),
            Output("pipeline-log", "value", allow_duplicate=True),
            Output("badge-pipeline-status", "children", allow_duplicate=True),
            Output("badge-pipeline-status", "color", allow_duplicate=True),
        ],
        Input("btn-run-full-backfill", "n_clicks"),
        State("slider-backfill-batch", "value"),
        prevent_initial_call=True,
    )
    def run_full_backfill(n_clicks, batch_size):
        if not n_clicks:
            return dash.no_update
        activity_logger.log_activity("User initiated Full Backfill from GUI", "INFO")

        # Use platform-specific wrapper
        if IS_WINDOWS:
            wrapper = Path("scripts/run_backfill_wrapper.bat").absolute()
        else:
            wrapper = Path("scripts/run_backfill_wrapper.sh").absolute()

        if not wrapper.exists():
            msg = f"Wrapper script not found: {wrapper}"
            activity_logger.log_activity(msg, "ERROR")
            return {"running": False}, msg, "ERROR", "danger"
        try:
            proc = open_terminal_with_command(wrapper, ["--batch-size", str(_coerce_batch_size(batch_size))], "ANPS-TradeMeUp Backfill")
        except Exception as e:
            activity_logger.log_agent_error("Backfill (GUI)", str(e))
            return {"running": False}, str(e), "ERROR", "danger"
        state = {"running": True, "process_id": proc.pid, "start_time": datetime.now().strftime("%H:%M:%S"), "type": "full_backfill"}
        log = f"[{datetime.now().strftime('%H:%M:%S')}] Full Backfill console opened\nProcess ID: {proc.pid}\nBatch: {batch_size}\n" + "-" * 60 + "\nCheck the new terminal window for live progress!\n"
        activity_logger.log_activity(f"Full backfill started (PID: {proc.pid})", "SUCCESS")
        return state, log, "RUNNING", "warning"

    @app.callback(
        [
            Output("store-pipeline-state", "data", allow_duplicate=True),
            Output("pipeline-log", "value", allow_duplicate=True),
            Output("badge-pipeline-status", "children", allow_duplicate=True),
            Output("badge-pipeline-status", "color", allow_duplicate=True),
        ],
        Input("btn-run-selective-backfill", "n_clicks"),
        [State("check-backfill-phases", "value"), State("slider-backfill-batch", "value")],
        prevent_initial_call=True,
    )
    def run_selective_backfill(n_clicks, selected_phases, batch_size):
        if not n_clicks or not selected_phases:
            return dash.no_update
        activity_logger.log_activity("User initiated Selective Backfill from GUI", "INFO")

        # Use platform-specific wrapper
        if IS_WINDOWS:
            wrapper = Path("scripts/run_backfill_wrapper.bat").absolute()
        else:
            wrapper = Path("scripts/run_backfill_wrapper.sh").absolute()

        if not wrapper.exists():
            msg = f"Wrapper script not found: {wrapper}"
            activity_logger.log_activity(msg, "ERROR")
            return {"running": False}, msg, "ERROR", "danger"
        all_phases = ["quality", "content", "entities", "facts", "surprises", "impact", "predictions"]
        args = ["--batch-size", str(_coerce_batch_size(batch_size))]
        for p in all_phases:
            if p not in selected_phases:
                args.append(f"--skip-{p}")
        try:
            proc = open_terminal_with_command(wrapper, args, "ANPS-TradeMeUp Backfill")
        except Exception as e:
            activity_logger.log_agent_error("Backfill (GUI)", str(e))
            return {"running": False}, str(e), "ERROR", "danger"
        state = {"running": True, "process_id": proc.pid, "start_time": datetime.now().strftime("%H:%M:%S"), "type": "selective_backfill"}
        phase_names = {"quality": "Quality Assessment", "content": "Content Understanding", "entities": "Entity Mapping", "facts": "Fact Verification", "surprises": "Surprise Scoring", "impact": "Impact Scoring", "predictions": "Predictions"}
        log = f"[{datetime.now().strftime('%H:%M:%S')}] Selective Backfill started\nProcess ID: {proc.pid}\nBatch: {batch_size}\n"
        for ph in selected_phases:
            log += f"  ✓ {phase_names.get(ph, ph)}\n"
        log += "-" * 60 + "\n"
        activity_logger.log_activity(f"Selective backfill started (PID: {proc.pid})", "SUCCESS")
        return state, log, "RUNNING", "warning"

    @app.callback(
        Output("recent-executions", "children"),
        Input("interval-component", "n_intervals"),
    )
    def update_recent_executions_cb(n):
        return get_recent_executions()
