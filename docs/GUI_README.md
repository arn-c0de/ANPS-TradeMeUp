# TradeMeUp Dashboard - GUI Documentation

## 🚀 Quick Start

```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Start dashboard
python run_dashboard.py
```

**Dashboard URL:** http://localhost:8050

---

## 📊 Dashboard Overview

Die TradeMeUp GUI ist eine modulare Dash-Anwendung mit 6 Haupttabs:

### 1. 🏠 **Dashboard** (Home)
**Datei:** `src/gui/tabs/dashboard.py`

**Features:**
- Live Metriken (Total Articles, LLM Processed, Avg Quality, Last 24h)
- Recent News Table (letzte 10 Artikel)
- Current Market Regime (Volatility, Trend, Risk, Liquidity)
- Model Performance Chart (30-Tage Rolling Accuracy)

**Funktionen:**
- `create_layout()` - Layout erstellen
- `get_metrics(engine)` - Metriken aus DB holen
- `get_recent_news(engine)` - Neueste Artikel
- `get_market_regime(engine)` - Aktuelles Market Regime

---

### 2. 🎯 **Predictions** 
**Datei:** `src/gui/tabs/predictions.py`

**Features:**
- Filter Bar (Entity, Date Range, Min Confidence)
- Predictions Table mit:
  - Timestamp
  - Entity Name
  - Direction (🔼 Up, 🔽 Down, ➡️ Flat)
  - Confidence Score
  - Forecast Horizon

**Funktionen:**
- `create_layout()` - Layout mit Filtern
- `get_predictions_table(engine)` - Predictions aus DB

**Status:** 
- ⚠️ Aktuell 0 Predictions (Entity Mapping muss erst Ticker finden)

---

### 3. 📰 **News Feed**
**Datei:** `src/gui/tabs/news.py`

**Features:**
- Filter Bar:
  - Source (multi-select)
  - Event Type (earnings, M&A, guidance, product, regulatory)
  - Sentiment (positive/neutral/negative)
  - Search (keywords)
- News Cards mit:
  - Title (clickable link zu Originalquelle)
  - Sentiment Badge (😊 😐 😟)
  - Event Type Badge
  - Source & Timestamp
  - LLM Summary (200 Zeichen)

**Funktionen:**
- `create_layout()` - Layout mit Filtern
- `get_news_feed(engine, sources, events, sentiment, search)` - Gefilterter Feed

**Live Data:** 73 Artikel verfügbar, 7 mit LLM-Analysen

---

### 4. 📊 **Statistics**
**Datei:** `src/gui/tabs/statistics.py`

**Features:**
- Overall Metrics Cards:
  - Total Articles
  - Processed
  - Entities
  - Predictions
  - Impact Scores
  - Avg Quality
- Event Type Distribution (Bar Chart)
- Quality Distribution (Histogram)
- News Volume Over Time (Placeholder)

**Funktionen:**
- `create_layout()` - Layout mit Charts
- `get_statistics_metrics(engine)` - Overall Stats
- `get_event_distribution_chart(engine)` - Event Type Chart
- `get_quality_distribution_chart(engine)` - Quality Histogram

**Charts:** Plotly Dark Theme, transparent backgrounds

---

### 5. 📈 **Live Charts**
**Datei:** `src/gui/tabs/charts.py`

**Features:**
- Market Data & Predictions Chart (Placeholder)
- Sentiment Heatmap (Placeholder)
- Impact Distribution (Placeholder)
- Entity Selector Dropdown

**Status:** 🚧 Placeholder Charts - werden mit echten Daten gefüllt wenn Market Data vorhanden

**Funktionen:**
- `create_layout()` - Layout
- `get_placeholder_chart()` - Placeholder für Charts

---

### 6. 🔧 **System Health**
**Datei:** `src/gui/tabs/system.py`

**Features:**
- Agent Pipeline Status Table:
  - 8 Agents mit Status (✅ Running / ⚠️ Needs Tuning)
  - Agent ID, Name, Status
- Database Statistics:
  - Row counts für alle Tabellen
  - Raw News, Processed, Entities, Predictions, Impact Scores
- Processing Pipeline:
  - Processing Completion Rate (%)
  - Progress Bar
  - X of Y articles processed

**Funktionen:**
- `create_layout()` - Layout
- `get_agent_status()` - Agent Status Table
- `get_db_statistics(engine)` - DB Stats
- `get_pipeline_stats(engine)` - Processing Rate

**Status:** Alle 8 MVP Agents sichtbar

---

## 🏗️ Architektur

```
src/gui/
├── app.py              # Haupt-App mit Callbacks
├── components.py       # Wiederverwendbare Komponenten
├── __init__.py
└── tabs/
    ├── __init__.py
    ├── dashboard.py    # Tab 1: Dashboard
    ├── predictions.py  # Tab 2: Predictions
    ├── news.py         # Tab 3: News Feed
    ├── statistics.py   # Tab 4: Statistics
    ├── charts.py       # Tab 5: Live Charts
    └── system.py       # Tab 6: System Health
```

**Modulare Struktur:**
- Jede Tab-Datei ist eigenständig
- `create_layout()` - Gibt Dash-Layout zurück
- `get_*()` Funktionen - Holen Daten aus DB und erstellen Components
- Callbacks in `app.py` koordinieren Updates

---

## 🎨 Design System

**Theme:** Dash Bootstrap Components - CYBORG (Dark Mode)

**Farben:**
- Primary: Blau (#00d9ff)
- Success: Grün (✅ Status, positive Sentiment)
- Warning: Gelb (⚠️ Warnings)
- Danger: Rot (negative Sentiment)
- Secondary: Grau (neutral)

**Icons:** Unicode Emojis
- 📰 News
- 🧠 LLM Processing
- 🎯 Predictions
- 📊 Statistics
- 🔼🔽➡️ Direction
- ✅⚠️ Status

**Charts:** Plotly Dark Theme
- Transparent backgrounds
- Light colored lines/bars
- No gridlines on dark

---

## 🔄 Live Updates

**Interval Component:** 30 Sekunden Auto-Refresh

**Live Status Indicator:**
- Grüner Punkt ● 
- "Live • Updated HH:MM:SS"
- In Navbar rechts oben

**Callbacks:**
- Alle Callbacks reagieren auf `interval-component.n_intervals`
- Automatische Updates alle 30 Sekunden
- Keine Page Reloads

---

## 📊 Datenquellen

**Database:** SQLite (trademeup.db)

**Models:**
```python
from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.models.data_quality import DataQualityScore
from src.models.entities import Entity
from src.models.predictions import Prediction
from src.models.analysis import MarketRegime, ImpactScore
```

**SQLAlchemy Session:**
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

engine = create_engine(settings.database_url)

with Session(engine) as db:
    results = db.query(Model).all()
```

---

## 🚀 Deployment

**Development:**
```bash
python run_dashboard.py
# Läuft auf http://0.0.0.0:8050
```

**Production:**
```bash
# Mit Gunicorn (TODO)
gunicorn src.gui.app:server -b 0.0.0.0:8050 --workers 4
```

**Docker:**
```dockerfile
# TODO: Docker container für GUI
```

---

## 📝 TODO / Roadmap

### Kurzfristig:
- [ ] Entity Dropdown in Predictions mit echten Entities füllen
- [ ] News Source Dropdown in News Feed mit echten Sources
- [ ] Real-Time Price Charts mit yfinance Integration
- [ ] Sentiment Heatmap mit echten Daten

### Mittelfristig:
- [ ] Prediction Detail Modal (Click auf Prediction)
- [ ] News Detail Modal (Click auf News Card)
- [ ] User Authentication (Login/Logout)
- [ ] User Preferences (Theme, Filters speichern)
- [ ] Export Funktionen (CSV, PDF)

### Langfristig:
- [ ] WebSocket für Live Updates (statt Interval)
- [ ] Custom Alert System
- [ ] Natural Language Query Interface
- [ ] Mobile-optimized responsive Design

---

## 🐛 Known Issues

1. **Predictions Tab:** Zeigt "No predictions available" - Entity Mapping findet keine Ticker
   - **Fix:** Entity extraction prompt verbessern, mehr Artikel durch LLM

2. **Charts Tab:** Alle Placeholder Charts
   - **Fix:** Market Data Agent implementieren, yfinance Integration

3. **Performance:** Bei >1000 Artikeln könnte News Feed langsam werden
   - **Fix:** Pagination implementieren (aktuell LIMIT 50)

---

## 📚 Dependencies

```txt
dash>=2.14.0
dash-bootstrap-components>=1.5.0
plotly>=5.18.0
pandas>=2.1.0
sqlalchemy>=2.0.0
```

Alle bereits installiert in venv ✅

---

## 🎓 Entwickler-Guide

### Neuen Tab hinzufügen:

1. **Erstelle neue Datei:** `src/gui/tabs/mein_tab.py`
```python
def create_layout():
    return html.Div([...])

def get_data(engine):
    with Session(engine) as db:
        return db.query(...).all()
```

2. **Importiere in app.py:**
```python
from src.gui.tabs import mein_tab
```

3. **Füge Tab hinzu:**
```python
dbc.Tab(mein_tab.create_layout(), label="📝 Mein Tab", tab_id="mein_tab")
```

4. **Callback erstellen:**
```python
@app.callback(
    Output("mein-div", "children"),
    Input("interval-component", "n_intervals")
)
def update_mein_tab(n):
    return mein_tab.get_data(engine)
```

---

## 🔧 Troubleshooting

**Dashboard startet nicht:**
```bash
# Check ob Port 8050 frei ist
netstat -an | findstr 8050

# Check Imports
python -c "from src.gui.app import app; print('OK')"
```

**Keine Daten sichtbar:**
```bash
# Check Database
python view_results.py

# Run Pipeline
python scripts/run_mvp_pipeline.py
```

**Callbacks feuern nicht:**
- Check Browser Console (F12)
- Check `suppress_callback_exceptions=True` in app.py
- Check Output ID matches component ID

---

**Last Updated:** 2026-01-22  
**Version:** 1.0.0 MVP  
**Status:** ✅ Functional - 8 Agents, 6 Tabs, Live Updates
