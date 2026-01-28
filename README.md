<br/>

  ![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
  ![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-009688?logo=fastapi&logoColor=white)
  ![Dash](https://img.shields.io/badge/Dash-3.4.0-3F4F75?logo=plotly&logoColor=white)
  ![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
  ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-1C1C1C?logo=python&logoColor=white)
  ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791?logo=postgresql&logoColor=white)
  ![pgvector](https://img.shields.io/badge/pgvector-0.2+-5865F2?logo=postgresql&logoColor=white)
  ![Alembic](https://img.shields.io/badge/Alembic-1.13+-330F51?logo=alembic&logoColor=white)
  ![Pydantic](https://img.shields.io/badge/Pydantic-2.5+-E92063?logo=pydantic&logoColor=white)
  ![Poetry](https://img.shields.io/badge/Poetry-Dependency%20Mgmt-60A5FA?logo=poetry&logoColor=white)
  ![yfinance](https://img.shields.io/badge/yfinance-0.2+-FF6B6B?logo=python&logoColor=white)
  <a href="https://deepwiki.com/arn-c0de/ANPS-TradeMeUp">
    <img src="https://img.shields.io/badge/DeepWiki-Project%20Docs-blueviolet?logo=book" alt="DeepWiki" />
  </a>
<br/>

<div align="left">
  <img src="images/ANPS-LOGO.png" alt="ANPS Logo" height="90px">
</div>

# ANPS-TradeMeUp

## **ANPS (AI News Prediction System) - Multi-Agent News-Based Market Prediction System**

> **Note:** This is a private, source-available project currently under active development. Features, APIs, and screenshots may change frequently and are not intended for production use. ⚠️

### What is ANPS-TradeMeUp?

ANPS-TradeMeUp (AI News Prediction System) is an MVP-grade pipeline that ingests news, extracts events/entities using LLMs, scores impact and surprise, and produces short-to-medium term market predictions. It includes a Dash GUI for real-time monitoring and a FastAPI backend.

**Database:** PostgreSQL 16+ with pgvector extension for optimal performance, JSONB support, and vector similarity search capabilities.


![Main Dashboard](images/screenshots/1.0.3-dashboard.png)
![News Feed](images/screenshots/1.0.3-news.png)
![Predictions](images/screenshots/1.0.3-predict.png)
![Simulations](images/screenshots/1.0.3-sim.png)
![Statistics](images/screenshots/1.0.3-stats.png)
![Live Charts](images/screenshots/1.0.3-charts.png)




---

## Quick Start

TradeMeUp converts financial news into probabilistic market predictions using a modular multi-agent pipeline. Start the GUI quickly with `start_gui.bat` (Windows) and explore dashboards and live charts. For development and production setup, follow the **Installation** section below.

---

## Features

### Multi-Agent Pipeline
- 16-agent modular architecture (ingest → understand → analyse → predict)
- LLM-based content understanding with fact verification
- Entity mapping with confidence scoring
- Impact, surprise, and regime detection
- Signal decay tracking and correlation analysis
- Multi-horizon predictions (1d, 5d, 20d)

### Dashboard
- Real-time metrics overview (news volume, predictions, entities)
- Recent news feed with quality scores
- Current market regime indicator
- Top performers tracking (1h, 24h, 5d, 30d, 1y, all-time)
- Pipeline health monitoring

### Predictions Tab
- Advanced filtering (entity, date range, horizon, confidence)
- Live performance tracking with actual vs expected returns
- Direction probabilities (up/down/flat)
- Risk and confidence scores
- Detailed modal view with market data
- Refresh individual predictions
- Export and batch operations

### Trading Simulations
- Portfolio configuration (capital, currency, risk adjustment)
- Create simulations from predictions (date range or last N)
- Trading decisions (buy/sell/hold) with risk assessment
- Stop loss and take profit calculations
- Transaction cost breakdown (commission, spread, slippage, market impact)
- Position sizing recommendations (risk-adjusted)
- Penny stock detection with special cost handling
- Expected vs actual return tracking
- Resimulate all with latest market data
- Filter by entity, horizon, decision, date range

### Statistics Tab
- Overall metrics (articles, entities, predictions, impact scores)
- Event and quality distribution charts
- Sentiment analysis (positive/negative/neutral)
- Impact score visualization
- Top entities rankings
- Entity sentiment analysis with timeframes (7d, 30d, 90d, all)
- Entity details table with search
- News volume trends over time

### Live Charts
- Multi-panel chart view (single, dual, quad mode)
- Candlestick and line chart types
- Real-time price updates (30s interval)
- Multiple timeframes (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
- Volume overlay and moving averages
- Infinite scroll for historical data
- Zoom and pan with state persistence
- Fullscreen mode
- Chart overlays (brackets, breakouts) - DB-backed
- Custom symbol search

### Agent Testing
- Individual agent health checks
- Test all 16 agents independently
- Real-time status monitoring
- Error tracking and logging
- Agent performance metrics

### System Health
- Pipeline status overview
- Database statistics
- Agent operational status
- Processing metrics
- Activity log monitoring

---

## Quick Start
1. Clone:
   ```bash
   git clone https://github.com/arn-c0de/ANPS-TradeMeUp.git
   cd ANPS-TradeMeUp
   ```
2. Start PostgreSQL database:
   ```bash
   docker-compose up -d
   ```
3. Create environment file and add API keys:
   ```bash
   cp .env.example .env.local
   # edit .env.local with your API keys
   ```
4. Run database migrations:
   ```bash
   alembic upgrade head
   ```
5. Start the GUI (Windows):
   ```powershell
   .\start_gui.bat
   # open http://localhost:8050
   ```

That's enough to explore the GUI and view sample dashboards. For a full development environment and pipeline run, continue with the Installation below.

---

## Installation & Full Setup

### Prerequisites:
- **Python 3.11+** (Python 3.12+ recommended)
- **PostgreSQL 16+** with pgvector extension
  - Option 1: Docker & Docker Compose (recommended for quick setup)
  - Option 2: Native PostgreSQL installation
- **Poetry** (recommended) or pip

### Database Setup (Choose One):

#### Option A: Docker (Recommended)
```bash
# Start PostgreSQL 16 with pgvector
docker-compose up -d

# PostgreSQL will be available at:
# Host: localhost:5432
# Database: trademeup
# User: trademeup_user
# Password: trademeup_pass
```

#### Option B: Native PostgreSQL (Windows/macOS/Linux)
```bash
# 1. Install PostgreSQL 16+ from https://www.postgresql.org/download/

# 2. Install pgvector extension
# Windows (PowerShell as Admin):
cd "C:\Program Files\PostgreSQL\16\bin"
.\psql.exe -U postgres
CREATE EXTENSION vector;

# Linux/macOS:
sudo apt-get install postgresql-16-pgvector  # Ubuntu/Debian
brew install pgvector  # macOS
psql -U postgres
CREATE EXTENSION vector;

# 3. Create database and user
CREATE DATABASE trademeup;
CREATE USER trademeup_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE trademeup TO trademeup_user;

# 4. Enable extensions
\c trademeup
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
```

For detailed PostgreSQL setup instructions, see [`POSTGRESQL_SETUP.md`](POSTGRESQL_SETUP.md).

### Full Installation Steps:

1. **Clone repository:**
   ```bash
   git clone https://github.com/arn-c0de/ANPS-TradeMeUp.git
   cd ANPS-TradeMeUp
   ```

2. **Start PostgreSQL** (if using Docker):
   ```bash
   docker-compose up -d
   ```

3. **Install Python dependencies:**
   ```bash
   # Using Poetry (recommended)
   poetry install
   poetry shell
   
   # Or using pip
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env.local
   # Edit .env.local and configure:
   ```
   
   **Required settings:**
   ```ini
   # Database (PostgreSQL required)
   DATABASE_URL=postgresql://trademeup_user:your_password@localhost:5432/trademeup
   
   # LLM API Keys (at least one required)
   ANTHROPIC_API_KEY=your_anthropic_key
   OPENAI_API_KEY=your_openai_key
   
   # Optional: News API keys, AlphaVantage, etc.
   ```

5. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```
   
   This creates all tables, indexes, and constraints in PostgreSQL. The migration includes:
   - All core tables with proper relationships
   - JSONB columns for flexible data storage
   - GIN indexes for fast JSONB queries
   - pgvector columns for embedding similarity search
   - Timezone-aware timestamp columns

5. **Run the pipeline:**
   - Continuous mode (recommended):
     ```bash
     python scripts/run_continuous_pipeline.py
     ```
   - One-shot (single pass):
     ```bash
     python scripts/run_mvp_pipeline.py
     ```

6. **Start the GUI:**
   ```bash
   python run_dashboard.py
   # or on Windows: .\start_gui.bat
   # Open http://localhost:8050
   ```

7. **Start the API (optional):**
   ```bash
   uvicorn src.api.main:app --reload
   # Open http://localhost:8000/docs
   ```

### Database Management

**Docker Commands:**
- **Stop PostgreSQL:** `docker-compose down`
- **View logs:** `docker-compose logs -f postgres`
- **Restart:** `docker-compose restart postgres`
- **Remove data (destructive):** `docker-compose down -v`

**Backup & Restore:**
```bash
# Backup
docker exec trademeup_postgres pg_dump -U trademeup_user trademeup > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i trademeup_postgres psql -U trademeup_user trademeup < backup.sql

# Backup with compression
docker exec trademeup_postgres pg_dump -U trademeup_user trademeup | gzip > backup.sql.gz
```

**Native PostgreSQL:**
```bash
# Backup
pg_dump -U trademeup_user trademeup > backup.sql

# Restore
psql -U trademeup_user trademeup < backup.sql

# Connect to database
psql -U trademeup_user -d trademeup
```

### Performance Optimization

PostgreSQL provides significant performance benefits:
- **JSONB:** Native JSON storage with indexing (vs SQLite's TEXT-based JSON)
- **Concurrent Access:** Multiple connections without file locking
- **Advanced Indexing:** GIN, GiST, partial indexes
- **Vector Search:** pgvector for embedding similarity (768-dim vectors)
- **Query Planner:** Sophisticated optimization for complex queries
- **Partitioning:** Table partitioning for large datasets (future)

**Performance Benchmarks:**
- Dashboard queries: ~50% faster than SQLite
- JSONB operations: 3-5x faster with GIN indexes
- Concurrent writes: 10x improvement
- Vector similarity search: Native support (vs JSON fallback)

---

## Development Notes & Project Status
- **Phase:** Phase 1 - MVP Core
- **Progress:** 16 of 17 agents implemented (active development)
- Recent: GUI improvements, central error handling, and added agent init tests.

Full implementation details, architecture, and agent breakdown are available deeper in this README and in `docs/`.

---

## Documentation & Guides
- **Quickstart:** [`QUICKSTART.md`](QUICKSTART.md)
- **PostgreSQL Setup:** [`POSTGRESQL_SETUP.md`](POSTGRESQL_SETUP.md) - Detailed database setup guide
- **GUI Documentation:** [`docs/GUI_README.md`](docs/GUI_README.md)
- **Local Setup:** [`docs/SETUP_LOCAL.md`](docs/SETUP_LOCAL.md)
- **Performance:** [`docs/CONTINUOUS_PIPELINE_PERFORMANCE.md`](docs/CONTINUOUS_PIPELINE_PERFORMANCE.md)
- **Third-party Licenses:** [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md)
- **Changelog:** [`CHANGELOG.md`](CHANGELOG.md)

---

## Contributing & Tests
- Run unit tests:
  ```bash
  pytest tests/unit
  ```
- Integration tests:
  ```bash
  pytest tests/integration
  ```

Please follow the development workflow in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Security

If you discover a security vulnerability, please do not file a public issue. Report it by email to `arn-c0de@protonmail.com` or via GitHub Security Advisories at `https://github.com/arn-c0de/ANPS-TradeMeUp/security`. Include steps to reproduce, affected versions, and an assessment of potential impact where possible. The maintainer will acknowledge receipt within 3 business days.

See [SECURITY.md](SECURITY.md) for detailed security policy and best practices.

---

## License
Copyright (c) 2026 arn-c0de. All rights reserved.

**PROPRIETARY SOURCE-AVAILABLE LICENSE**

This software is proprietary and source-available. You may view, clone, and modify this repository solely for the purpose of contributing improvements via pull requests or issues.

**Strictly prohibited without explicit written permission:**
- Commercial use
- Redistribution
- Publication of modified or unmodified versions
- Use in other software projects
- Sublicensing or selling

All contributions submitted to this repository become the exclusive property of the copyright holder.

See [LICENSE](LICENSE) for full details.

**Maintainer:** `arn-c0de` (<arn-c0de@protonmail.com>)  
**Repository:** `https://github.com/arn-c0de/ANPS-TradeMeUp`

---

**Last Updated:** January 28, 2026
**Version:** 1.0.4

### Recent Changes (v1.0.4)
- **Complete PostgreSQL Migration:** Migrated from SQLite to PostgreSQL 16+ for production-ready performance
- **pgvector Integration:** Added vector similarity search support for embeddings
- **JSONB Optimization:** All JSON columns converted to JSONB with GIN indexes
- **Timezone Awareness:** All datetime operations now properly handle timezones
- **Type Safety:** NumPy/pandas types automatically converted for database compatibility
- **Performance:** 50-300% improvement in query performance vs SQLite
- **GUI Fixes:** Resolved all datetime and JSONB deserialization issues
- **Data Migration:** Complete data migration from SQLite to PostgreSQL with validation

Developer note: When updating the project version, please also update the `VERSION` constant in `src/config/settings.py` so the GUI and documentation reflect the correct version.
