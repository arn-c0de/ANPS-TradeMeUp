# Agent Control Tab - Documentation

## 🎮 Overview

Der Agent Control Tab ermöglicht es, die TradeMeUp Pipeline direkt über die GUI zu steuern.

**Tab:** 🎮 Agent Control  
**Datei:** `src/gui/tabs/control.py`  
**URL:** http://localhost:8050 → Tab "Agent Control"

---

## 🚀 Features

### 1. Pipeline Control Panel

Drei Hauptoptionen zum Starten der Pipeline:

#### **🚀 Full MVP Pipeline**
- Führt alle 8 Agents sequenziell aus
- Verarbeitet alle verfügbaren Artikel
- Dauer: ~15 Minuten
- Button: "Run Full Pipeline" (Blau)

**Was wird gemacht:**
1. Agent 1: Data Ingestion (RSS Feeds)
2. Agent 1.5: Data Quality Assessment
3. Agent 2: Content Understanding (LLM)
4. Agent 3: Entity Mapping
5. Agent 4.5: Surprise Quantification
6. Agent 5: Market Regime Detection
7. Agent 4: Impact Scoring
8. Agent 6: Predictions

#### **⚡ Quick Test**
- Schneller Test mit 3 Artikeln
- Alle Agents werden getestet
- Dauer: ~2 Minuten
- Button: "Run Quick Test" (Grün)

**Ideal für:**
- Schnelle Funktionstests
- Nach Code-Änderungen
- Debugging

#### **🎯 Single Agent**
- Führt nur einen ausgewählten Agent aus
- Dropdown zur Agent-Auswahl
- Button wird erst nach Auswahl aktiv

**Verfügbare Agents:**
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
- Range: 1-50 Artikel
- Default: 10
- Limitiert wie viele Artikel durch die LLM-Phase gehen

#### **Force Refresh** (Checkbox)
- Ignoriert Cache
- Lädt alle Daten neu
- Nützlich für Tests

#### **Verbose Logging** (Checkbox)
- Detaillierte Logs
- Default: AN
- Zeigt alle Debug-Informationen

---

### 3. Execution Status

**Status Badge:**
- 🟢 Idle (Grau) - Keine Pipeline läuft
- 🟡 Running (Gelb/Grün) - Pipeline aktiv
- 🔴 Error (Rot) - Fehler aufgetreten

**Status Display:**
- Current Phase (welcher Agent läuft)
- Started (Startzeit)
- Articles Processed (Fortschritt)
- Progress Bar

---

### 4. Execution Log

**Live Log Output:**
- Echtzeit-Logs der laufenden Pipeline
- Monospace Font für bessere Lesbarkeit
- Read-only Textarea
- Zeigt:
  - Timestamps
  - Agent-Status
  - Fehler und Warnungen
  - Verarbeitungsfortschritt

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

Historie der letzten Pipeline-Läufe:
- Timestamp
- Pipeline Type
- Status (Success/Failed)
- Duration
- Articles Processed

---

## 🔧 Technische Implementierung

### Backend (control.py)

**Hauptfunktionen:**

```python
create_layout()
# Erstellt das Tab-Layout mit allen Controls

run_pipeline_command(command_type, options)
# Startet Pipeline als subprocess
# command_type: 'full', 'quick', oder agent name
# options: dict mit limit, force, verbose

get_process_output(process)
# Liest Output vom laufenden Process

format_pipeline_status(status)
# Formatiert Status-Display

get_recent_executions()
# Lädt Execution History
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

**Non-Blocking:**
- Pipeline läuft im Hintergrund
- Dashboard bleibt responsive
- Status-Updates alle 2 Sekunden

---

## 🎯 Callbacks in app.py

### 1. Toggle Single Agent Button
```python
@app.callback(
    Output("btn-run-single-agent", "disabled"),
    Input("agent-selector", "value")
)
```
Aktiviert Button nur wenn Agent ausgewählt ist.

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
Startet Full Pipeline und updated Status/Logs.

### 3. Run Quick Test
Analog zu Full Pipeline, aber mit Quick Test Script.

---

## 📋 Verwendung

### Scenario 1: Full Pipeline Run

1. Öffne Dashboard: http://localhost:8050
2. Navigiere zu Tab "🎮 Agent Control"
3. Optional: Passe "Articles to Process" an
4. Klicke "Run Full Pipeline"
5. Beobachte Status und Logs
6. Nach Abschluss: Wechsle zu anderen Tabs um Ergebnisse zu sehen

### Scenario 2: Quick Test nach Code-Änderung

1. Code geändert (z.B. Agent verbessert)
2. Agent Control Tab öffnen
3. "Run Quick Test" klicken
4. Nach ~2 Minuten: Ergebnisse prüfen
5. Bei Fehler: Logs analysieren

### Scenario 3: Einzelnen Agent testen

1. Dropdown "Select agent..." öffnen
2. z.B. "Agent 2: Content Understanding" wählen
3. "Run Selected Agent" wird aktiv
4. Klicken und Logs beobachten
5. Nur dieser Agent wird ausgeführt

---

## 🐛 Error Handling

### Pipeline Failed

**Symptom:** Status Badge wird rot, Log zeigt ERROR

**Ursachen:**
- LLM Server offline (Ollama nicht gestartet)
- Datenbank-Verbindung fehlgeschlagen
- Python-Fehler im Agent-Code
- Netzwerk-Timeout bei RSS Feeds

**Lösung:**
1. Log analysieren für genaue Fehlermeldung
2. Ollama prüfen: `ollama list`
3. Database prüfen: `python view_results.py`
4. Bei Code-Fehler: Debug mode, Stack trace prüfen

### Process Hangs

**Symptom:** Pipeline läuft ewig, kein Fortschritt

**Lösung:**
```powershell
# Process finden
Get-Process python

# Process killen
Stop-Process -Id <PID> -Force
```

### Button disabled

**Symptom:** Buttons reagieren nicht

**Ursachen:**
- Keine Agent-Auswahl (Single Agent)
- Pipeline läuft bereits
- Browser-Cache

**Lösung:**
- Agent aus Dropdown wählen
- Warten bis aktuelle Pipeline fertig
- Browser-Reload (Ctrl+R)

---

## 🚀 Erweiterungen (TODO)

### Kurzfristig
- [ ] Live Log-Streaming (WebSocket statt Polling)
- [ ] Stop/Cancel Button (Process kill)
- [ ] Progress Bar mit echten Prozentwerten
- [ ] Pipeline Schedule (Cron-Jobs über GUI)

### Mittelfristig
- [ ] Multi-Pipeline Support (mehrere parallel)
- [ ] Execution History in Datenbank speichern
- [ ] Export Logs als .txt oder .json
- [ ] Email/Slack Notifications bei Completion/Failure

### Langfristig
- [ ] Custom Pipeline Builder (Agents per Drag&Drop)
- [ ] Parameter-Tuning über GUI
- [ ] A/B Testing Interface
- [ ] Performance Profiling Visualization

---

## 📊 Integration mit anderen Tabs

**Nach Pipeline-Run:**

1. **Dashboard Tab**: Updated automatisch
   - Neue Artikel-Count
   - Aktualisierte Quality Stats
   - Market Regime Änderungen

2. **News Feed Tab**: Zeigt neue Artikel
   - LLM-Summaries
   - Sentiment Badges
   - Event Tags

3. **Predictions Tab**: Neue Predictions (wenn Entities gefunden)
   - Direction & Confidence
   - Forecast Horizon

4. **Statistics Tab**: Updated Charts
   - Event Distribution
   - Quality Histogram

5. **System Health Tab**: Updated Agent Status
   - Last Execution Time
   - Success/Failure Count

---

## 🎓 Best Practices

### 1. Entwicklung
- Immer erst "Quick Test" nach Code-Änderung
- Verbose Logging aktivieren beim Debugging
- Einzelne Agents testen bei Agent-spezifischen Änderungen

### 2. Produktion
- "Full Pipeline" für regelmäßige Runs
- Verbose Logging deaktivieren (Performance)
- Execution History regelmäßig prüfen

### 3. Monitoring
- Status Badge im Auge behalten
- Bei langen Runs: Log regelmäßig prüfen
- System Health Tab parallel offen halten

---

## 📚 Dateien

```
src/gui/tabs/control.py          # Control Tab Implementation
src/gui/app.py                   # Callbacks für Control
scripts/run_mvp_pipeline.py      # Full Pipeline Script
test_quick.py                    # Quick Test Script
scripts/run_ingestion.py         # Ingestion-only Script
```

---

## 🔗 Related Documentation

- [GUI_README.md](../GUI_README.md) - Komplette GUI Dokumentation
- [PIPELINE_RESULTS.md](../PIPELINE_RESULTS.md) - Pipeline Ergebnisse
- [Implementation_Plan.md](../Implementation_Plan.md) - Architektur

---

**Last Updated:** 2026-01-22  
**Version:** 1.0.0  
**Status:** ✅ Functional
