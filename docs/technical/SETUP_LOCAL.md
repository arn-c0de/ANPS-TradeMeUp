# TradeMeUp - Local Setup Guide (without app containers)

> Status note: this guide now assumes PostgreSQL as the active database backend. Older SQLite instructions are obsolete unless you are working on archived migration tasks.

## Schnellstart für lokale Entwicklung

### 1. Prerequisites

- **Python 3.11+** installiert
- **Ollama** (für lokales LLM) ODER **OpenAI API Key**
- Docker or native PostgreSQL 16+ with `pgvector`

### 2. Ollama Setup (Empfohlen für lokal)

```bash
# Ollama installieren (https://ollama.ai)
# Windows: Download von https://ollama.ai/download

# Nach Installation:
ollama serve  # Server starten

# In neuem Terminal: Model herunterladen
ollama pull llama2
# ODER für bessere Ergebnisse:
ollama pull mistral
```

### 3. Projekt Setup

```bash
# 1. Repository klonen oder in Projekt-Ordner navigieren
cd "D:\Projects\PYTHON - FOLDER\TradeMeUp"

# 2. Virtual Environment erstellen
python -m venv venv

# 3. Virtual Environment aktivieren
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Dependencies installieren
pip install -r requirements.txt

# ODER mit Poetry:
poetry install
poetry shell
```

### 4. Konfiguration

```bash
# .env.local Datei anpassen
# Wichtigste Einstellungen:

# Für Ollama (lokal):
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# Für OpenAI (Cloud):
LLM_PROVIDER=openai
OPENAI_API_KEY=dein-api-key-hier
OPENAI_MODEL=gpt-3.5-turbo

# Für Anthropic Claude (Cloud):
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=dein-api-key-hier

# Database (PostgreSQL required):
DATABASE_URL=postgresql://trademeup_user:trademeup_pass@localhost:5432/trademeup
```

### 5. Datenbank initialisieren

```bash
docker compose up -d postgres

# Migration ausführen
alembic upgrade head
```

### 6. Pipeline testen

```bash
# Einzelne Agents testen:

# Agent 1: Daten holen
python scripts/run_ingestion.py

# Komplette Pipeline (Agents 1, 1.5, 2, 3):
python scripts/run_full_pipeline.py
```

### 7. API starten

```bash
# FastAPI Server starten
uvicorn src.api.main:app --reload

# API testen:
# Browser: http://localhost:8000/docs
# Oder: curl http://localhost:8000/health
```

## Verfügbare Commands

### Pipeline Befehle

```bash
# Nur News holen
python scripts/run_ingestion.py

# Komplette Pipeline
python scripts/run_full_pipeline.py
```

### API Befehle

```bash
# API starten
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Mit auto-reload (für Development)
uvicorn src.api.main:app --reload
```

### Database Befehle

```bash
# Neue Migration erstellen
alembic revision --autogenerate -m "Beschreibung"

# Migrationen ausführen
alembic upgrade head

# Rollback (1 Version zurück)
alembic downgrade -1

# Status anzeigen
alembic current
```

## Troubleshooting

### Ollama verbindet nicht

```bash
# Prüfen ob Ollama läuft:
curl http://localhost:11434/api/tags

# Wenn nicht, Ollama starten:
ollama serve
```

### Database reset

```bash
# Reset PostgreSQL schema:
docker compose down -v
docker compose up -d postgres
alembic upgrade head
```

### Import Fehler

```bash
# Virtual Environment neu erstellen:
deactivate
rm -rf venv
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### LLM API Fehler

```bash
# Prüfen ob API Keys gesetzt sind:
# Für Windows PowerShell:
$env:OPENAI_API_KEY

# Für Linux/Mac:
echo $OPENAI_API_KEY

# Falls nicht gesetzt, in .env.local eintragen
```

## Performance Tipps

### Für schnellere Entwicklung:

1. **Kleinere Batches**: In `run_full_pipeline.py` die `limit` Parameter reduzieren
2. **Lokales LLM**: Ollama ist langsamer aber kostenlos
3. **Cloud LLM**: OpenAI ist schneller aber kostet $
4. **SQLite**: Für Development ausreichend, für Production PostgreSQL

### Empfohlene LLM-Models:

- **Schnell & kostenlos**: Ollama mit `llama2` oder `mistral`
- **Beste Qualität**: OpenAI `gpt-4-turbo` oder Anthropic `claude-3-sonnet`
- **Günstig & gut**: OpenAI `gpt-3.5-turbo`

## Nächste Schritte

Nach erfolgreichem Setup:

1. ✅ Pipeline testen mit `run_full_pipeline.py`
2. ✅ API testen unter http://localhost:8000/docs
3. 🔄 Agent 4: Impact Scoring implementieren
4. 🔄 Agent 5: Regime Detection implementieren
5. 🔄 Agent 6: Prediction Model trainieren

## Status

**Implementiert (4 von 17 Agents):**
- ✅ Agent 1: Data Ingestion (RSS, News API)
- ✅ Agent 1.5: Data Quality (Validierung, Duplikate)
- ✅ Agent 2: Content Understanding (NLP mit LLM)
- ✅ Agent 3: Entity Mapping (Ticker-Erkennung)

**Als Nächstes:**
- ⬜ Agent 4: Impact Scoring
- ⬜ Agent 4.5: Surprise Quantification
- ⬜ Agent 5: Market Regime Detection
- ⬜ Agent 6: Prediction (XGBoost)

## Support

Bei Problemen:
1. Logs prüfen (console output)
2. `.env.local` Konfiguration prüfen
3. Dependencies neu installieren
4. Issue in GitHub erstellen
