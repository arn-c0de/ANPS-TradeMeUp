# Live Agent Activity Monitoring

## Overview

The TradeMeUp Dashboard now includes **real-time agent activity monitoring** and **live server logs**, allowing you to track exactly what each agent is doing at any moment during pipeline execution.

## Features

### 🔴 Live Agent Activity Monitor
- Real-time status updates for all running agents
- Visual indicators for different states:
  - 🔄 **PROCESSING** - Agent actively working (blue)
  - ▶️ **STARTING** - Agent initializing (cyan)
  - ✅ **SUCCESS** - Successful completion (green)
  - ❌ **ERROR** - Failures and errors (red)
  - ● **INFO** - General information (gray)

### 📋 Live Server Logs
- Last 20 lines of detailed server logs
- Monospace terminal-style display
- Auto-scrolling to show latest activity
- Full pipeline execution details

### ⚡ Auto-Refresh
- Updates every **5 seconds**
- No manual refresh needed
- Minimal performance impact

## Usage

### 1. Start the Dashboard

```bash
# Windows
.\start_gui.bat

# Linux/Mac or alternative
python run_dashboard.py
```

The dashboard will be available at: **http://localhost:8050**

### 2. Run a Pipeline

In a **separate terminal**, run any pipeline:

```bash
# Full MVP Pipeline (8 agents)
python scripts/run_mvp_pipeline.py

# Quick Test (demo logging)
python test_live_logging.py

# Single agents
python scripts/run_ingestion.py
```

### 3. Monitor Live Activity

1. Open the **Dashboard** tab in your browser
2. Watch the **"🔴 Live Agent Activity"** section for real-time updates
3. View **"📋 Server Logs"** for detailed output
4. Logs update every 5 seconds automatically

## How It Works

### Architecture

```
Pipeline Script
    ↓
Activity Logger
    ↓
Log Files (logs/*.log)
    ↓
Dashboard (reads files)
    ↓
Browser (auto-updates)
```

### Log Files

Located in `logs/` directory:

- **pipeline_activity.log** - Structured activity messages (used by live display)
- **dashboard.log** - Full detailed logs (used by log viewer)

### Activity Logger API

The `ActivityLogger` class provides these methods:

```python
from src.utils.activity_logger import activity_logger

# Pipeline lifecycle
activity_logger.log_pipeline_start("Pipeline Name")
activity_logger.log_pipeline_complete("Pipeline Name", duration)

# Phase tracking
activity_logger.log_phase(1, "Data Collection")

# Agent lifecycle
activity_logger.log_agent_start("Agent Name", "Phase 1")
activity_logger.log_agent_processing("Agent Name", "Item X", current=1, total=10)
activity_logger.log_agent_success("Agent Name", count=10, duration=5.2)
activity_logger.log_agent_error("Agent Name", "Error message")

# Custom messages
activity_logger.log_activity("Message", level="INFO")
```

## Example Pipeline Integration

```python
from src.utils.activity_logger import activity_logger

def run_pipeline():
    start_time = datetime.now()
    
    # Start
    activity_logger.log_pipeline_start("My Pipeline")
    
    # Phase 1
    activity_logger.log_phase(1, "Data Collection")
    activity_logger.log_agent_start("Ingestion Agent", "1")
    
    # Processing
    for i, article in enumerate(articles, 1):
        activity_logger.log_agent_processing(
            "Ingestion Agent",
            article.title,
            current=i,
            total=len(articles)
        )
        process_article(article)
    
    # Complete
    activity_logger.log_agent_success("Ingestion Agent", len(articles))
    
    # End
    duration = (datetime.now() - start_time).total_seconds()
    activity_logger.log_pipeline_complete("My Pipeline", duration)
```

## Dashboard Sections

### Live Agent Activity
- Shows last 10 activity messages
- Color-coded by status
- Updates every 5 seconds
- Auto-shows when pipeline runs

### Server Logs
- Scrollable text area
- Last 20 log lines
- Monospace font (terminal-style)
- Green text on black background

## Testing

### Test Live Logging

Run the test script to see the live monitoring in action:

```bash
python test_live_logging.py
```

This will:
1. Clear old logs
2. Simulate a full pipeline run
3. Show all log levels (INFO, PROCESSING, SUCCESS, ERROR)
4. Take ~25 seconds to complete

**While running**, open http://localhost:8050 to see live updates!

### Expected Output

```
[22:40:08] STARTING: 🚀 Test Pipeline STARTED
[22:40:09] INFO: 📍 PHASE 1: Data Collection
[22:40:10] STARTING: STARTING Ingestion Agent - Phase 1
[22:40:11] PROCESSING: PROCESSING Ingestion Agent: Article 1 (1/5)
[22:40:14] SUCCESS: SUCCESS Ingestion Agent: Processed 5 items in 2.50s
...
[22:40:35] SUCCESS: ✅ Test Pipeline COMPLETED in 25.00s
```

## Troubleshooting

### Logs Not Showing

1. **Check log files exist:**
   ```bash
   ls logs/
   ```

2. **Verify dashboard is running:**
   - Open http://localhost:8050
   - Check terminal for errors

3. **Check file permissions:**
   ```bash
   # Windows
   icacls logs\
   
   # Linux/Mac
   ls -la logs/
   ```

### Updates Not Appearing

1. **Clear browser cache** (Ctrl+F5)
2. **Check interval is running** (should see auto-updates every 5s)
3. **Restart dashboard:**
   ```bash
   # Stop (Ctrl+C)
   # Start again
   .\start_gui.bat
   ```

### Encoding Issues

If you see garbled characters (emojis not displaying):

1. **Windows PowerShell:**
   ```powershell
   $OutputEncoding = [System.Text.Encoding]::UTF8
   [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
   ```

2. **Use Windows Terminal** instead of old CMD/PowerShell

## Performance

- **Log file size:** ~1-2 KB per pipeline run
- **Dashboard refresh:** 5 second intervals
- **Memory usage:** Minimal (reads last N lines only)
- **Network traffic:** None (local files)

## Best Practices

1. **Run pipeline in separate terminal** - Don't block dashboard
2. **Monitor during long runs** - Track progress of LLM processing
3. **Check after errors** - Logs show exact failure point
4. **Clear old logs periodically:**
   ```python
   from src.utils.activity_logger import activity_logger
   activity_logger.clear_logs()
   ```

## Future Enhancements

Planned features:

- [ ] WebSocket-based live streaming (no polling)
- [ ] Historical log viewer with search
- [ ] Agent progress bars with ETA
- [ ] Performance metrics per agent
- [ ] Log export/download functionality
- [ ] Multi-pipeline tracking (parallel runs)

## Related Documentation

- [GUI_README.md](../docs/GUI_README.md) - Dashboard overview
- [AGENT_CONTROL_TAB.md](../docs/AGENT_CONTROL_TAB.md) - Running pipelines from UI
- [QUICKSTART.md](../QUICKSTART.md) - Getting started guide

---

**Status:** ✅ Fully Implemented (Phase 1)  
**Last Updated:** 2026-01-22  
**Author:** TradeMeUp Team
