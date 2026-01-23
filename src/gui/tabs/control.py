"""
Agent Control Tab - Start, Stop and Monitor Agents
"""

from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from datetime import datetime
import subprocess
import os
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


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
    except:
        return ""
