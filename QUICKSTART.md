# TradeMeUp - Quickstart Guide

**Quick Start in 5 Minutes**

## Voraussetzungen

- Python 3.11+
- **Docker & Docker Compose** (für PostgreSQL)
- **Ollama** (lokal) ODER **OpenAI API Key**

## Installation

```bash
# 1. PostgreSQL mit pgvector starten
docker-compose up -d

# 2. Virtual Environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Ollama starten (wenn lokal)
ollama serve
ollama pull mistral  # oder llama2
```

## Konfiguration

Erstelle `.env.local`:

```bash
# Database (PostgreSQL required)
DATABASE_URL=postgresql://trademeup_user:trademeup_pass@localhost:5432/trademeup

# Für Ollama (lokal, kostenlos)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# Für OpenAI (schneller, kostet $)
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-...
```

## Database Setup

```bash
# Migrations ausführen (erstellt alle Tabellen + Indexes)
alembic upgrade head

# Optional: Daten von SQLite migrieren (falls vorhanden)
python scripts/migrate_sqlite_to_postgresql.py
```

## Database Management

```bash
# PostgreSQL stoppen
docker-compose down

# Logs anzeigen
docker-compose logs -f postgres

# Backup erstellen
docker exec trademeup_postgres pg_dump -U trademeup_user trademeup > backup.sql

# Backup wiederherstellen
docker exec -i trademeup_postgres psql -U trademeup_user trademeup < backup.sql

# Performance Benchmark
python scripts/benchmark_postgresql.py
```

## Pipeline ausführen

```bash
# CONTINUOUS PIPELINE (Production Mode)
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

## Continuous Pipeline - Performance Features

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

## Dashboard

```bash
# Starte das GUI Dashboard
.\start_gui.bat  # Windows
# python run_dashboard.py  # Alternative

# Dashboard öffnen im Browser:
# http://localhost:8050

# Features:
# - Live Agent Activity Monitor
# - Real-time Server Logs
# - Metrics & Statistics
# - News Feed
# - Predictions with Task Queue
# - Agent Control Panel
# - Task Queue System (prevents server blocking)
```

### Task Queue System

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

1. **Agent 1**: Fetch news (RSS, APIs)
2. **Agent 1.5**: Quality check (duplicates, validation)
3. **Agent 2**: NLP analysis (sentiment, events) - LLM
4. **Agent 3**: Extract entities (tickers) - LLM
5. **Agent 5**: Detect market regime (VIX, trends)
6. **Agent 4.5**: Quantify surprises (earnings beats)
7. **Agent 4**: Calculate impact score
8. **Agent 6**: Generate predictions

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

### PostgreSQL Fehler
```bash
# Database neu erstellen:
docker-compose down -v  # Löscht auch Volumes
docker-compose up -d
alembic upgrade head
```

### Import Fehler
```bash
# Neu installieren:
pip install --upgrade -r requirements.txt
```

## Performance-Tipps

### LLM Performance
- **Ollama**: ~30-60 Sek pro Artikel (lokal, kostenlos)
- **OpenAI gpt-3.5**: ~5-10 Sek pro Artikel (~$0.002/Artikel)
- **OpenAI gpt-4**: ~10-20 Sek pro Artikel (~$0.02/Artikel)

### Database Performance
- **PostgreSQL mit JSONB**: 30-50% schneller als SQLite bei komplexen Queries
- **pgvector**: Native Vektor-Suche für Embeddings (10-20x schneller als JSON-Array-Vergleiche)
- **GIN Indexes**: Schnelle JSON-Feld-Abfragen
- **Connection Pooling**: Optimiert für gleichzeitige Agent-Zugriffe

**Für Tests: Pipeline mit limit=3 laufen lassen (ca. 3-5 Min)**

## Next Steps

1. Run the pipeline
2. Test the API
3. Fetch more news (increase limit)
4. Implement Agent 12: Backtesting
5. Build GUI with Dash

## Support

- Logs prüfen (Console Output)
- `.env.local` Konfiguration prüfen
- Ollama/LLM testen: `scripts/test_llm.py` (wenn erstellt)

**Status:** MVP with 8 of 17 agents (47% Complete)
