# Live Monitoring

## Overview

The dashboard includes live activity monitoring and log views for pipeline execution.

## Start the dashboard

```bash
python scripts/runtime/run_dashboard.py
```

Windows wrapper:

```powershell
scripts\runtime\start_gui.bat
```

## Run a pipeline in a second terminal

```bash
python scripts/run_mvp_pipeline.py
python scripts/run_continuous_pipeline.py
python scripts/run_ingestion.py
```

## Log files

- `logs/pipeline_activity.log`
- `logs/dashboard.log`

## Related docs

- `docs/features/GUI_README.md`
- `docs/features/AGENT_CONTROL_TAB.md`
- `docs/setup/QUICKSTART.md`
