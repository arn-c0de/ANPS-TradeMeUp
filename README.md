# TradeMeUp - AI Multi-Agent News-Based Market Prediction System

An advanced AI-powered system that transforms unstructured financial news into probabilistic market forecasts using a multi-agent architecture.

## 🎯 Project Status

**Current Phase:** Phase 1 - MVP Core Development 🚀
**Progress:** 16 of 17 Agents Implemented (94%)
**Next Milestone:** Finalize remaining integrations, populate DB with pipeline data, and production hardening

### Implementation Progress
- ✅ Project structure & infrastructure setup
- ✅ Database schema & migrations (SQLite + PostgreSQL ready)
- ✅ **TIER 1: Data Ingestion** (2/2 agents) ✅
  - Agent 1: Feed & Data Ingestion
  - Agent 1.5: Data Quality
- ✅ **TIER 2: Understanding** (3/3 agents) ✅
  - Agent 2: Content Understanding (LLM)
  - Agent 2.5: Fact Verification
  - Agent 3: Entity & Sector Mapping
- ✅ **TIER 3: Analysis** (5/5 agents) ✅
  - Agent 4: Impact & Relevance Scoring
  - Agent 4.5: Surprise Quantification
  - Agent 5: Market Regime Detection
  - Agent 5.5: Signal Decay Modeling
  - Agent 5.6: Correlation Analysis
- ✅ **TIER 4: Prediction** (4/4 agents) ✅
  - Agent 6: Market Prediction & Ensemble (XGBoost baseline)
  - Agent 6.5: Confidence Calibration
  - Agent 7: Meta-Strategy
  - Agent 7.5: Scenario Generation
- ⚠️ **TIER 6: Learning** (2/3 agents) - Partial
  - Agent 12: Backtesting & Learning (basic)
  - Agent 12.5: Model Performance Monitor (basic)
- ✅ **Pipeline Orchestration** - Continuous & One-Shot modes
- ✅ **FastAPI Backend** - Basic endpoints
- ✅ **GUI Dashboard** - Dash with improved error handling and full agent support
- ⬜ Remaining agents: Risk & Execution and Observability features (Phase 3)
- ⬜ Advanced features & production hardening

**Recent Updates:**
- **GUI:** Added support for new agents, user-friendly empty states, and central error handling module (`src/gui/error_handling.py`).
- **Tests:** Added `tests/test_agent_init.py` to verify agent initialization; run with `python tests/test_agent_init.py` or `pytest`.
- **Database:** Alembic migrations applied; use `alembic upgrade head` if needed.

## 🏗️ Architecture

The system consists of 17 specialized agents organized in 7 tiers (8 implemented, 9 planned):

1. **Data Ingestion** (2 agents) ✅ **COMPLETE**
   - RSS feeds, News APIs, quality checks, duplicate detection
2. **Understanding** (3 agents) ⚠️ **2 of 3**
   - LLM-based NLP, entity extraction, sentiment analysis
   - Missing: Fact verification
3. **Analysis** (5 agents) ⚠️ **3 of 5**
   - Impact scoring, regime detection, surprise quantification
   - Missing: Signal decay, correlation analysis
4. **Prediction** (4 agents) ⚠️ **1 of 4**
   - XGBoost baseline, ensemble framework ready
   - Missing: Confidence calibration, meta-strategy, scenarios
5. **Risk & Execution** (4 agents) ⬜ **Planned**
   - Position sizing, portfolio monitoring (Phase 3)
6. **Learning** (3 agents) ⚠️ **1 of 3**
   - Basic backtesting implemented
   - Missing: Performance monitoring, A/B testing
7. **Observability** (4 agents) ⬜ **Planned**
   - Health monitoring, audit trails, compliance (Phase 3)

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Poetry (for dependency management)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd TradeMeUp
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start infrastructure services**
   ```bash
   docker-compose up -d
   ```

4. **Install dependencies** (when Poetry is ready)
   ```bash
   poetry install
   poetry shell
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Run the complete pipeline**
   ```bash
   # Continuous mode (recommended - runs indefinitely)
   python scripts/run_continuous_pipeline.py
   
   # One-shot mode (single run through all 8 agents)
   python scripts/run_mvp_pipeline.py
   
   # With custom settings
   python scripts/run_continuous_pipeline.py --interval 120 --max-memory 4096
   ```

7. **Start the GUI Dashboard**
   ```bash
   # Windows
   .\start_gui.bat
   
   # Linux/Mac
   python run_dashboard.py
   
   # Then open: http://localhost:8050
   ```

8. **Start the API (optional)**
   ```bash
   uvicorn src.api.main:app --reload
   # API docs: http://localhost:8000/docs
   ```

## 📊 Current Features

### ✅ Fully Implemented (8 Agents)

#### TIER 1: Data Ingestion
- **Agent 1: Feed & Data Ingestion Agent**
  - RSS feed parsing (Reuters, Yahoo Finance, MarketWatch, Bloomberg, CNBC)
  - Configurable feed sources via JSON
  - Rate limiting and politeness policies
  - Duplicate detection via SHA-256 content hashing
  - Database storage with full metadata
  
- **Agent 1.5: Data Quality Agent**
  - Content validation (word count, structure, language)
  - Duplicate detection across sources
  - Quality scoring (0-1 scale)
  - Source reliability tracking
  - Automatic filtering of low-quality articles

#### TIER 2: Understanding
- **Agent 2: Content Understanding Agent**
  - LLM integration (OpenAI GPT / Ollama)
  - Multi-label event classification (earnings, M&A, macro, etc.)
  - Fine-grained sentiment analysis (-1 to +1)
  - Key facts extraction
  - Sentence-transformer embeddings (768-dim)
  - Prompt engineering for financial context
  
- **Agent 3: Entity & Sector Mapping Agent**
  - LLM-based Named Entity Recognition
  - Company-to-ticker mapping with validation
  - Sector classification (GICS-style)
  - Exposure type detection (direct/indirect)
  - Yahoo Finance integration for ticker validation
  - Entity confidence scoring

#### TIER 3: Analysis
- **Agent 4: Impact & Relevance Scoring Agent**
  - Multi-factor impact calculation
  - Source authority weighting
  - Event severity assessment
  - Market regime adjustment
  - Surprise magnitude integration
  - Confidence-weighted scoring
  
- **Agent 4.5: Surprise Quantification Agent**
  - Consensus data integration
  - Surprise calculation (standardized deviations)
  - Historical context analysis
  - Support for earnings, revenue, guidance
  - Market expectation modeling
  
- **Agent 5: Market Regime Detection Agent**
  - Multi-dimensional regime classification
  - VIX-based volatility assessment
  - Trend detection (bull/bear/sideways)
  - Risk appetite measurement
  - Liquidity regime analysis
  - Real-time regime updates

#### TIER 4: Prediction
- **Agent 6: Market Prediction & Ensemble Agent**
  - XGBoost baseline model
  - Multi-horizon predictions (1d, 5d, 20d)
  - Feature engineering pipeline
  - Direction probability forecasts
  - Expected return estimation
  - Confidence scoring
  - Ensemble framework (ready for multi-model)

#### TIER 6: Learning (Partial)
- **Agent 12: Backtesting & Learning Agent** ⚠️
  - Prediction outcome tracking
  - Performance metrics calculation
  - Basic accuracy reporting
  - Missing: Advanced analytics, model retraining

### 🚀 Pipeline & Infrastructure
- **Continuous Pipeline Mode**
  - Runs indefinitely, checks every 5 minutes
  - Dynamic batch sizing (auto-optimization)
  - Memory management with auto-GC
  - Graceful shutdown (SIGINT/SIGTERM)
  - Exponential backoff error recovery
  - Performance metrics tracking
  - CLI: `python scripts/run_continuous_pipeline.py`
  
- **One-Shot Pipeline Mode**
  - Complete 8-agent pipeline execution
  - CLI: `python scripts/run_mvp_pipeline.py`
  
- **Database**
  - SQLite (development) / PostgreSQL (production)
  - Alembic migrations
  - 15+ tables with full schema
  - Optimized indexes

- **FastAPI Backend**
  - RESTful API with 10+ endpoints
  - OpenAPI/Swagger documentation
  - CORS support for GUI
  - Health check endpoint
  - Pagination & filtering
  
- **Dash GUI Dashboard**
  - 10 tabs: Dashboard, Predictions, News, Entities, Statistics, Charts, History, System, Testing, Settings
  - Live agent activity monitor
  - Real-time metrics & charts
  - News feed with filters
  - Entity database browser
  - System health monitoring

### 🔄 In Development
- Agent 2.5: Fact Verification
- Agent 5.5: Signal Decay Modeling
- Agent 5.6: Correlation Analysis
- Agent 6.5: Confidence Calibration
- Agent 7: Meta-Strategy
- Advanced GUI features
- Production deployment automation

## 🗂️ Project Structure

```
TradeMeUp/
├── src/
│   ├── agents/          # All 17 agent implementations
│   ├── api/             # FastAPI application
│   ├── models/          # SQLAlchemy database models
│   ├── services/        # Business logic
│   ├── ml/              # Machine learning models
│   ├── config/          # Configuration management
│   └── utils/           # Utility functions
├── tests/               # Unit and integration tests
├── scripts/             # Utility scripts
├── migrations/          # Alembic database migrations
├── config/              # Configuration files
├── docs/                # Documentation
└── docker-compose.yml   # Infrastructure setup
```

## 🔑 API Keys Required

- **Anthropic/OpenAI**: For LLM-based content understanding
- **News API**: For additional news sources (optional)
- **Alpha Vantage**: For market data (optional in MVP)

## 📖 Documentation

### Core Documentation
- [Quickstart Guide](./QUICKSTART.md) - Get started in 5 minutes
- [Complete Implementation Checklist](./COMPLETE_IMPLEMENTATION_CHECKLIST.md) - Detailed progress tracker
- [Complete Technical Specification](./Comprehensive_Technical_Specification_v2.0.md) - Full system design

### Performance & Operations
- [Continuous Pipeline Performance Guide](./docs/CONTINUOUS_PIPELINE_PERFORMANCE.md)
- [Performance Improvements Summary](./PERFORMANCE_IMPROVEMENTS_SUMMARY.md)
- [GUI Documentation](./docs/GUI_README.md)
- [Live Monitoring Setup](./docs/LIVE_MONITORING.md)

### Development
- [Agent Control Tab](./docs/AGENT_CONTROL_TAB.md)
- [Local Setup Guide](./docs/SETUP_LOCAL.md)
- [MVP Status](./docs/MVP_STATUS.md)

## 🧪 Testing

```bash
# Run unit tests
pytest tests/unit

# Run integration tests
pytest tests/integration

# Run all tests with coverage
pytest --cov=src tests/
```

## 📝 Development Workflow

1. Pick a task from the Implementation Checklist
2. Create a feature branch
3. Implement the feature
4. Write tests
5. Run linting and formatting
6. Create pull request
7. After review, merge to main

## 🛠️ Tech Stack

- **Backend**: Python 3.11+, FastAPI
- **Database**: PostgreSQL + TimescaleDB
- **Cache**: Redis
- **Storage**: MinIO (S3-compatible)
- **ML**: XGBoost, LightGBM, PyTorch, sentence-transformers
- **LLM**: Anthropic Claude / OpenAI GPT
- **Orchestration**: Prefect
- **GUI**: Dash (Plotly)
- **Monitoring**: Prometheus + Grafana

## 🎯 Roadmap

### ✅ Phase 1: MVP Core (Weeks 1-4) - 90% Complete
- ✅ Core data pipeline (Agents 1, 1.5, 2, 3)
- ✅ Basic analysis (Agents 4, 4.5, 5)
- ✅ Single prediction model (XGBoost)
- ✅ Basic backtesting (Agent 12)
- ✅ FastAPI backend (10+ endpoints)
- ✅ Dash GUI (10 tabs)
- ✅ Continuous pipeline with performance optimization
- ⬜ Complete API documentation
- ⬜ Unit test coverage >80%

### 🔄 Phase 2: Expansion (Weeks 5-8) - In Progress
- ⬜ Advanced agents (2.5, 5.5, 5.6, 6.5, 7, 7.5)
- ⬜ Multi-model ensemble (LSTM, LightGBM, sentiment model)
- ⬜ Enhanced GUI features
- ⬜ WebSocket live updates
- ⬜ Advanced analytics & reporting
- ⬜ Model performance monitoring (Agent 12.5)
- ⬜ A/B testing framework (Agent 13)

### ⬜ Phase 3: Production (Weeks 9-12) - Planned
- ⬜ Risk & execution agents (8-11)
- ⬜ Observability agents (14-17)
- ⬜ Security & authentication (OAuth2, RBAC)
- ⬜ Monitoring & alerting (Prometheus, Grafana)
- ⬜ CI/CD pipeline
- ⬜ Docker production deployment
- ⬜ Load testing & optimization
- ⬜ Documentation completion

## 📄 License

[Add your license here]

## 🤝 Contributing

[Add contribution guidelines]

## 📧 Contact

[Add contact information]

---

**Last Updated:** January 23, 2026  
**Version:** 0.6.0 (MVP - 16 Agents)  
**Status:** Production-Ready Pipeline, GUI Dashboard Operational  
**Next Release:** v0.6.0 - Advanced Analysis Agents (Phase 2)
