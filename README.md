# ANPS-TradeMeUp

<div align="center">
  <img src="images/ANPS-LOGO.png" alt="ANPS Logo" height="80px">
</div>

**ANPS (AI News Prediction System) - Multi-Agent News-Based Market Prediction System**

![Main Dashboard](images/screenshots/trademeup-1.0.2-maindash.png)
![Live Charts](images/screenshots/trademeup-1.0.2-livecharts.png)
![Statistics](images/screenshots/trademeup-1.0.2-statistics.png)
![Testing](images/screenshots/trademeup-1.0.2-testingsuite.png)

---

## Quick Start

TradeMeUp converts financial news into probabilistic market predictions using a modular multi-agent pipeline. Start the GUI quickly with `start_gui.bat` (Windows) and explore dashboards and live charts. For development and production setup, follow the **Installation** section below.

---

## What is ANPS-TradeMeUp?

ANPS-TradeMeUp (AI News Prediction System) is an MVP-grade pipeline that ingests news, extracts events/entities using LLMs, scores impact and surprise, and produces short-to-medium term market predictions. It includes a Dash GUI for real-time monitoring and a FastAPI backend.

## Features

- Modular multi-agent architecture (ingest → understand → analyse → predict)
- LLM-based content understanding and entity/ticker mapping
- Impact, surprise, and regime scoring
- XGBoost prediction baseline with multi-horizon forecasts
- Dash GUI: Dashboard, Live Charts, Agent Control, System Health

---

## Screenshots

- Main dashboard (news, metrics, market regime)
- Live charts (multi-ticker, multi-horizon)
- Statistics and health pages

See images in `images/screenshots/`

---

## Quick Start
1. Clone:
   ```bash
   git clone https://github.com/arn-c0de/ANPS-TradeMeUp.git
   cd ANPS-TradeMeUp
   ```
2. Create an environment file and add API keys:
   ```bash
   cp .env.example .env
   # edit .env
   ```
3. Start the GUI (Windows):
   ```powershell
   .\start_gui.bat
   # open http://localhost:8050
   ```

That's enough to explore the GUI and view sample dashboards. For a full development environment and pipeline run, continue with the Installation below.

---

## Installation & Full Setup
Prerequisites:
- Python 3.11+
- Docker & Docker Compose
- Poetry (recommended)

Full steps:
1. Start infra services (optional, but recommended for full functionality):
   ```bash
   docker-compose up -d
   ```
2. Install Python dependencies (using Poetry):
   ```bash
   poetry install
   poetry shell
   ```
3. Copy environment template and configure keys:
   ```bash
   cp .env.example .env
   # add Anthropic/OpenAI, AlphaVantage or other keys
   ```
4. Run DB migrations:
   ```bash
   alembic upgrade head
   ```
5. Run the pipeline:
   - Continuous mode (recommended):
     ```bash
     python scripts/run_continuous_pipeline.py
     ```
   - One-shot (single pass):
     ```bash
     python scripts/run_mvp_pipeline.py
     ```
6. Start the API (optional):
   ```bash
   uvicorn src.api.main:app --reload
   # open http://localhost:8000/docs
   ```

---

## Development Notes & Project Status
- **Phase:** Phase 1 - MVP Core
- **Progress:** 16 of 17 agents implemented (active development)
- Recent: GUI improvements, central error handling, and added agent init tests.

Full implementation details, architecture, and agent breakdown are available deeper in this README and in `docs/`.

---

## Documentation & Guides
- Quickstart: `QUICKSTART.md`
- GUI docs: `docs/GUI_README.md`
- Local setup: `docs/SETUP_LOCAL.md`
- Performance: `docs/CONTINUOUS_PIPELINE_PERFORMANCE.md`

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

**Last Updated:** January 25, 2026
**Version:** 1.0.3

Developer note: When updating the project version, please also update the `VERSION` constant in `src/config/settings.py` so the GUI and documentation reflect the correct version.
