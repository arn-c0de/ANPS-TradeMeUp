# TradeMeUp - Quickstart Guide

**Schnellstart in 5 Minuten** 🚀

## Voraussetzungen

- Python 3.11+
- **Ollama** (lokal) ODER **OpenAI API Key**

## Installation

```bash
# 1. Virtual Environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 2. Dependencies installieren
pip install -r requirements.txt

# 3. Ollama starten (wenn lokal)
ollama serve
ollama pull mistral  # oder llama2
```

## Konfiguration

Erstelle `.env.local`:

```bash
# Für Ollama (lokal, kostenlos)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# Für OpenAI (schneller, kostet $)
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=sqlite:///./trademeup.db
```

## Database Setup

```bash
# Alembic initialisieren
alembic init migrations  # Falls noch nicht vorhanden

# Migration erstellen
alembic revision --autogenerate -m "Initial schema"

# Migration ausführen
alembic upgrade head
```

## Pipeline ausführen

```bash
# CONTINUOUS PIPELINE (Production Mode - NEU! ⚡)
python scripts/run_continuous_pipeline.py
# Läuft dauerhaft, prüft alle 5 Minuten auf neue Daten
# Dynamische Batch-Größen, Auto-Retry, Memory Management
# Ctrl+C für graceful shutdown

# Mit Custom-Settings:
python scripts/run_continuous_pipeline.py --interval 120 --max-memory 4096

# KOMPLETTE MVP PIPELINE (One-Shot Mode)
python scripts/run_mvp_pipeline.py

# Nur einzelne Agents testen:
python scripts/run_ingestion.py  # Nur News holen
python scripts/run_full_pipeline.py  # Agents 1-3

# Live Logging testen (für Dashboard):
python test_live_logging.py
```

## 🔥 Continuous Pipeline - Performance Features

### Basic Usage
```bash
# Standard (5min interval, 2GB memory limit)
python scripts/run_continuous_pipeline.py

# Development (2min checks, schnellerer Feedback)
python scripts/run_continuous_pipeline.py --interval 120

# Production (4GB memory, optimiert für Durchsatz)
python scripts/run_continuous_pipeline.py --max-memory 4096
```

### Features
- **Automatische Batch-Anpassung**: System optimiert sich selbst
- **Memory Management**: GC bei Überschreitung, Memory-Tracking
- **Graceful Shutdown**: Ctrl+C beendet sauber nach aktueller Iteration
- **Error Recovery**: Exponential Backoff bei Fehlern
- **Performance Metrics**: Avg Time, Memory Delta, Batch Sizes

### Output Example
```
=============================================================
Pipeline Iteration #3 - 2026-01-23 04:30:15
Memory: 892.3MB | Avg Time: 124.5s | Batch Sizes: {'quality': 60, 'content': 12}
=============================================================

Iteration #3 completed in 118.2s (avg: 124.5s)
Memory delta: +12.3MB (now: 904.6MB)
```

Details: [Continuous Pipeline Performance Guide](docs/CONTINUOUS_PIPELINE_PERFORMANCE.md)

## Dashboard starten (NEU!)

```bash
# Starte das GUI Dashboard
.\start_gui.bat  # Windows
# python run_dashboard.py  # Alternative

# Dashboard öffnen im Browser:
# http://localhost:8050

# Features:
# - 🔴 Live Agent Activity Monitor
# - 📋 Real-time Server Logs
# - 📊 Metrics & Statistics
# - 📰 News Feed
# - 🎯 Predictions mit Task Queue
# - 🎮 Agent Control Panel
# - ⚡ Task Queue System (verhindert Server-Blockierung)
```

### Task Queue System (NEU!)

Das Dashboard verwendet ein modernes Task-Queue-System für alle Server-Aktionen:

- **Automatische Warteschlange**: Mehrere Klicks werden nacheinander abgearbeitet
- **Keine Server-Blockierung**: Tasks werden asynchron im Hintergrund ausgeführt  
- **Status-Feedback**: Toast-Benachrichtigungen zeigen Queue-Position und Fortschritt
- **Priorisierung**: User-initiierte Aktionen haben höchste Priorität
- **Fehlerbehandlung**: Automatische Wiederholungen bei Fehlern

**Beispiel**: Klickst du 3x auf "Refresh" → alle 3 Tasks werden nacheinander ausgeführt, ohne den Server zu überlasten.

## API starten

```bash
# FastAPI Server
uvicorn src.api.main:app --reload

# API testen:
# Browser: http://localhost:8000/docs
# curl http://localhost:8000/health
```

## API Endpoints

```bash
# Predictions
GET /api/v1/predictions
GET /api/v1/predictions/{id}
GET /api/v1/predictions/statistics/summary

# News
GET /api/v1/news
GET /api/v1/news/{id}

# Entities
GET /api/v1/entities
GET /api/v1/entities/{id}
GET /api/v1/entities/statistics/summary
```

## Was die Pipeline macht

**8 Agents in 8 Phasen:**

1. **Agent 1**: News holen (RSS, APIs)
2. **Agent 1.5**: Qualität prüfen (Duplikate, Validierung)
3. **Agent 2**: NLP Analyse (Sentiment, Events) 🤖 LLM
4. **Agent 3**: Entities extrahieren (Tickers) 🤖 LLM
5. **Agent 5**: Market Regime erkennen (VIX, Trends)
6. **Agent 4.5**: Surprises quantifizieren (Earnings beats)
7. **Agent 4**: Impact Score berechnen
8. **Agent 6**: Predictions generieren 📈

## Erwartete Ausgabe

```
=== PHASE 1: Data Collection ===
✓ Fetched 25 articles from RSS feeds
✓ 18 new articles saved

=== PHASE 2: Quality Assessment ===
✓ Processed 18 articles
✓ 15 high quality, 2 duplicates

=== PHASE 3: Content Understanding ===
✓ Using LLM: ollama (mistral)
✓ Processed 3 articles with NLP
✓ Event types: earnings(2), macro(1)

=== PHASE 4: Entity Mapping ===
✓ Extracted 5 entities (AAPL, MSFT, TECH, FIN, ...)

=== PHASE 5: Market Regime ===
✓ Current regime: volatility=low, trend=bull, risk=neutral
✓ VIX: 14.2

=== PHASE 6: Surprise Analysis ===
✓ Found 1 surprise: AAPL EPS beat by 1.2 std devs

=== PHASE 7: Impact Scoring ===
✓ Calculated 8 impact scores
✓ 3 high impact (>0.7)

=== PHASE 8: Predictions ===
✓ Generated 5 predictions
✓ 3 bullish, 1 bearish, 1 neutral
✓ Avg confidence: 0.65
```

## Troubleshooting

### Ollama verbindet nicht
```bash
# Prüfen:
curl http://localhost:11434/api/tags

# Neu starten:
ollama serve
```

### SQLite Fehler
```bash
# Database neu erstellen:
rm trademeup.db
alembic upgrade head
```

### Import Fehler
```bash
# Neu installieren:
pip install --upgrade -r requirements.txt
```

## Performance-Tipps

- **Ollama**: ~30-60 Sek pro Artikel (lokal, kostenlos)
- **OpenAI gpt-3.5**: ~5-10 Sek pro Artikel (~$0.002/Artikel)
- **OpenAI gpt-4**: ~10-20 Sek pro Artikel (~$0.02/Artikel)

**Für Tests: Pipeline mit limit=3 laufen lassen (ca. 3-5 Min)**

## Nächste Schritte

1. ✅ Pipeline laufen lassen
2. ✅ API testen
3. 🔄 Mehr News holen (limit erhöhen)
4. 🔄 Agent 12: Backtesting implementieren
5. 🔄 GUI mit Dash bauen

## Support

- Logs prüfen (Console Output)
- `.env.local` Konfiguration prüfen
- Ollama/LLM testen: `scripts/test_llm.py` (wenn erstellt)

**Status:** MVP mit 8 von 17 Agents ✅ (47% Complete)
