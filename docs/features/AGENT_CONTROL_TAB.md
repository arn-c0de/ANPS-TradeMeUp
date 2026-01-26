# Agent Control Tab - Documentation

## 🎮 Overview

The Agent Control Tab allows you to control the TradeMeUp pipeline directly from the GUI.

**Tab:** 🎮 Agent Control  
**File:** `src/gui/tabs/control.py`  
**URL:** http://localhost:8050 → Tab "Agent Control"

---

## 🚀 Features

### 1. Pipeline Control Panel

Three main options to run the pipeline:

#### **🚀 Full MVP Pipeline**
- Runs all 8 agents sequentially
- Processes all available articles
- Duration: ~15 minutes
- Button: "Run Full Pipeline" (Blue)

**What it does:**
1. Agent 1: Data Ingestion (RSS Feeds)
2. Agent 1.5: Data Quality Assessment
3. Agent 2: Content Understanding (LLM)
4. Agent 3: Entity Mapping
5. Agent 4.5: Surprise Quantification
6. Agent 5: Market Regime Detection
7. Agent 4: Impact Scoring
8. Agent 6: Predictions

#### **⚡ Quick Test**
- Fast test using 3 articles
- All agents are exercised
- Duration: ~2 minutes
- Button: "Run Quick Test" (Green)

**Ideal for:**
- Quick functional checks
- After code changes
- Debugging

#### **🎯 Single Agent**
- Runs only the selected agent
- Agent selection via dropdown
- Run button is enabled only after selecting an agent

**Available agents:**
- Agent 1: Ingestion
- Agent 1.5: Quality
- Agent 2: Content Understanding
- Agent 3: Entity Mapping
- Agent 4: Impact Scoring
- Agent 4.5: Surprise
- Agent 5: Regime Detection
- Agent 6: Predictions

---

### 2. Pipeline Options

#### **Articles to Process** (Slider)
- Range: 1–50 articles
- Default: 10
- Limits how many articles proceed to the LLM phase

#### **Force Refresh** (Checkbox)
- Ignores cache
- Reloads all data
- Useful for testing

#### **Verbose Logging** (Checkbox)
- Detailed logs
- Default: ON
- Shows full debug information

---

### 3. Execution Status

**Status Badge:**
- 🟢 Idle (Gray) — No pipeline running
- 🟡 Running (Yellow/Green) — Pipeline active
- 🔴 Error (Red) — An error occurred

**Status Display:**
- Current Phase (which agent is running)
- Started (start time)
- Articles Processed (progress)
- Progress Bar

---

### 4. Execution Log

**Live Log Output:**
- Real-time logs from the running pipeline
- Monospace font for improved readability
- Read-only textarea
- Shows:
  - Timestamps
  - Agent status
  - Errors and warnings
  - Processing progress

**Log Format:**
```
[HH:MM:SS] Starting Full MVP Pipeline...
Process ID: 12345
Articles to process: 10
------------------------------------------------------------
[HH:MM:SS] Phase 1: Data Ingestion
[HH:MM:SS] Fetched 45 articles from Yahoo Finance
...
```

---

### 5. Recent Executions

History of recent pipeline runs:
- Timestamp
- Pipeline type
- Status (Success/Failed)
- Duration
- Articles processed

---

## 🔧 Technical Implementation

### Backend (`control.py`)

**Main functions:**

```python
create_layout()
# Builds the tab layout with all controls

run_pipeline_command(command_type, options)
# Starts the pipeline as a subprocess
# command_type: 'full', 'quick', or agent name
# options: dict containing limit, force, verbose

get_process_output(process)
# Reads output from the running process

format_pipeline_status(status)
# Formats the status display

get_recent_executions()
# Loads execution history
```

### Process Management

**Subprocess Execution:**
```python
process = subprocess.Popen(
    [python_exe, script],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    cwd=PROJECT_ROOT
)
```

**Non-blocking behavior:**
- Pipeline runs in the background
- Dashboard remains responsive
- Status updates every 2 seconds

---

## 🎯 Callbacks in `app.py`

### 1. Toggle Single Agent Button
```python
@app.callback(
    Output("btn-run-single-agent", "disabled"),
    Input("agent-selector", "value")
)
```
Enables the button only when an agent is selected.

### 2. Run Full Pipeline
```python
@app.callback(
    [Output("store-pipeline-state", "data"),
     Output("pipeline-log", "value"),
     Output("badge-pipeline-status", "children"),
     Output("badge-pipeline-status", "color")],
    Input("btn-run-full-pipeline", "n_clicks"),
    State(...)
)
```
Starts the full pipeline and updates status/logs.

### 3. Run Quick Test
Similar to the full pipeline callback but runs the quick test script.

---

## 📋 Usage

### Scenario 1: Full Pipeline Run

1. Open the dashboard: http://localhost:8050
2. Navigate to the "🎮 Agent Control" tab
3. Optionally adjust "Articles to Process"
4. Click "Run Full Pipeline"
5. Monitor status and logs
6. After completion: check other tabs for results

### Scenario 2: Quick Test after Code Changes

1. Make code changes (e.g., improve an agent)
2. Open the Agent Control tab
3. Click "Run Quick Test"
4. After ~2 minutes: inspect results
5. If failures occur: analyze the logs

### Scenario 3: Test a Single Agent

1. Open the "Select agent..." dropdown
2. Choose e.g. "Agent 2: Content Understanding"
3. "Run Selected Agent" becomes enabled
4. Click and watch the logs
5. Only the selected agent is executed

---

## 🐛 Error Handling

### Pipeline Failed

**Symptom:** Status badge turns red and logs show ERROR

**Possible causes:**
- LLM server offline (Ollama not started)
- Database connection failure
- Python error in agent code
- Network timeout fetching RSS feeds

**Troubleshooting:**
1. Inspect logs for the exact error message
2. Check Ollama: `ollama list`
3. Check the database: `python view_results.py`
4. For code errors: enable debug mode and examine the stack trace

### Process Hangs

**Symptom:** Pipeline runs indefinitely with no progress

**Remediation:**
```powershell
# Find the process
Get-Process python

# Kill the process
Stop-Process -Id <PID> -Force
```

### Buttons Disabled

**Symptom:** Buttons are unresponsive

**Possible causes:**
- No agent selected (Single Agent)
- A pipeline run is already in progress
- Browser cache

**Solutions:**
- Select an agent from the dropdown
- Wait for the current pipeline to finish
- Reload the browser (Ctrl+R)

---

## 🚀 Enhancements (TODO)

### Short term
- [ ] Live log streaming (WebSocket instead of polling)
- [ ] Stop/Cancel button (ability to kill the process)
- [ ] Progress bar with real percentage values
- [ ] Pipeline scheduling (cron-style jobs via GUI)

### Medium term
- [ ] Multi-pipeline support (parallel runs)
- [ ] Persist execution history to the database
- [ ] Export logs as .txt or .json
- [ ] Email/Slack notifications on completion/failure

### Long term
- [ ] Custom pipeline builder (drag & drop agents)
- [ ] Parameter tuning via the GUI
- [ ] A/B testing interface
- [ ] Performance profiling visualizations

---

## 📊 Integration with Other Tabs

**After a pipeline run:**

1. **Dashboard Tab:** Automatically updated
   - New article count
   - Updated quality statistics
   - Market regime changes

2. **News Feed Tab:** Shows new articles
   - LLM summaries
   - Sentiment badges
   - Event tags

3. **Predictions Tab:** New predictions (if entities were found)
   - Direction & confidence
   - Forecast horizon

4. **Statistics Tab:** Updated charts
   - Event distribution
   - Quality histogram

5. **System Health Tab:** Updated agent status
   - Last execution time
   - Success/failure counts

---

## 🎓 Best Practices

### 1. Development
- Always run a "Quick Test" after code changes
- Enable verbose logging while debugging
- Test individual agents for agent-specific changes

### 2. Production
- Use "Full Pipeline" for regular runs
- Disable verbose logging in production (performance)
- Check execution history periodically

### 3. Monitoring
- Keep an eye on the status badge
- For long runs: monitor the logs frequently
- Keep the System Health tab open while monitoring

---

## 📚 Files

```
src/gui/tabs/control.py          # Control Tab implementation
src/gui/app.py                   # Callbacks for Control
scripts/run_mvp_pipeline.py      # Full pipeline script
test_quick.py                    # Quick test script
scripts/run_ingestion.py         # Ingestion-only script
```

---

## 🔗 Related Documentation

- [GUI_README.md](../GUI_README.md) — Complete GUI documentation
- [PIPELINE_RESULTS.md](../PIPELINE_RESULTS.md) — Pipeline results
- [Implementation_Plan.md](../Implementation_Plan.md) — Architecture

---

**Last Updated:** 2026-01-22  
**Version:** 1.0.0  
**Status:** ✅ Functional
