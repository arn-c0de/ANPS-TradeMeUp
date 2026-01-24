# Trading Simulation System - Setup & Usage

## Übersicht

Das neue Trading Simulation System implementiert den **E vs R Framework** aus der Architektur-Dokumentation:
- **E (Expected World)**: Predictions von den Agents
- **R (Real World)**: Tatsächliche Marktdaten
- **Δ (Divergence)**: E - R
- **Risk Score**: Composite Risk aus 8 Komponenten
- **Decision**: Buy/Sell/Hold basierend auf Risk & Confidence

## Komponenten

### 1. Risk Calculator (`src/simulations/risk_calculations.py`)
Berechnet Composite Risk Score basierend auf:
- Model Uncertainty (1 - confidence)
- Divergence Magnitude (E - R)
- Volatility Regime (aus Agent 5)
- Liquidity Stress
- Regime Instability
- Transaction Costs
- Market Impact
- Correlation Breakdown

### 2. Trading Simulator (`src/simulations/trading_simulator.py`)
Konvertiert Predictions → Trade Decisions:
- Fetched Live-Marktdaten via yfinance
- Berechnet Transaction Costs (Commission, Spread, Slippage, Impact)
- Evaluiert Risk Score
- Entscheidet: BUY/SELL/HOLD

**Decision Rules**:
- `confidence < 0.55` → HOLD
- `expected_return < 0.75%` → HOLD
- `risk_score > 0.65` → HOLD
- `cost_ratio > 0.70` → HOLD (Kosten fressen Alpha)
- Sonst: BUY (wenn UP & positive) oder SELL (wenn DOWN & negative)

### 3. Database Model (`src/models/trading_simulation.py`)
Tabelle `trading_simulations`:
- decision (buy/sell/hold)
- expected_return_pct, actual_return_pct, divergence_pct
- risk_score, confidence
- transaction_cost_bps
- cost_breakdown, risk_breakdown (JSON)
- simulation_metadata (JSON)

### 4. Agent Wrapper (`src/agents/trading_simulation_agent.py`)
Integration in Pipeline als **Agent 8.5: Trading Simulation Agent**

## Installation & Setup

### Schritt 1: Tabelle anlegen

**Option A: Schneller Fix (SQL direkt)**
```bash
python add_simulation_table.py
```

**Option B: Alembic Migration**
```bash
alembic upgrade head
```

**Option C: Fresh Database (löscht alles!)**
```bash
# Backup erstellen falls nötig
copy trademeup.db trademeup.db.backup

# Neu initialisieren
python init_database.py
```

### Schritt 2: Simulationen generieren

**Einmal alle bestehenden Predictions simulieren:**
```bash
python test_simulation.py
```

**Pipeline mit Simulation laufen lassen:**
```bash
# MVP Pipeline (einmalig)
python scripts/run_mvp_pipeline.py

# Continuous Pipeline (dauerhaft)
python scripts/run_continuous_pipeline.py
```

## GUI Integration

### Predictions Tab
Zeigt jetzt 2 zusätzliche Spalten:
- **Decision**: Buy/Sell/Hold Badge (farbcodiert)
- **Risk**: Risk Score 0-1 (rot/gelb/grün)

### Neuer Simulations Tab (🧪)
Eigener Tab mit:
- Filter: Entity, Datum, Horizon, Decision
- Tabelle mit allen Simulationen
- Spalten: Decision, Risk, Expected, Actual, Δ (E-R), Cost (bps)

## Testing

```bash
# 1. Tabelle anlegen
python add_simulation_table.py

# 2. Simulationen testen
python test_simulation.py

# 3. Dashboard starten
python run_dashboard.py

# 4. Im Browser:
#    - Predictions Tab: Decision/Risk Spalten prüfen
#    - Simulations Tab: Alle Simulationen anzeigen
```

## Konfiguration

Thresholds anpassen in `TradingSimulationEngine`:
```python
MIN_CONFIDENCE = 0.55          # Minimum confidence für Trade
MIN_EXPECTED_RETURN_PCT = 0.75  # Minimum expected return (%)
MAX_RISK_SCORE = 0.65          # Maximum risk score
MAX_COST_RATIO = 0.70          # Maximum cost/return ratio
```

## Beispiel Output

```json
{
  "simulation_id": "uuid...",
  "decision": "buy",
  "expected_return_pct": 2.5,
  "actual_return_pct": 1.8,
  "divergence_pct": 0.7,
  "risk_score": 0.42,
  "transaction_cost_bps": 15.2,
  "cost_breakdown": {
    "commission_bps": 0.5,
    "spread_bps": 8.0,
    "slippage_bps": 5.0,
    "market_impact_bps": 6.0,
    "total_bps": 19.5
  },
  "risk_breakdown": {
    "model_uncertainty": 0.35,
    "divergence_magnitude": 0.07,
    "volatility_regime": 0.50,
    "liquidity_stress": 0.50,
    "regime_instability": 0.30,
    "transaction_cost": 0.45,
    "market_impact": 0.12,
    "correlation_breakdown": 0.00
  }
}
```

## Architektur-Konformität

Das System implementiert:
- ✅ **E vs R Framework** (Expected vs Observed World)
- ✅ **Δ = E - R** (Divergence Calculation)
- ✅ **Risk-First Mentality** (High risk → Don't trade)
- ✅ **Cost Awareness** (Signal > 2-3x costs)
- ✅ **Regime-Dependent Decisions** (Volatility affects costs)

Aus `1.0.3-TradeMeUp_Complete_System_Architecture.md` L66-82:
```
Expected World (E)          Observed World (R)
─────────────────          ─────────────────
• News analysis              • Actual prices
• Sentiment models           • Volume patterns
• Macro models               • Volatility
• Analyst consensus          • Order flow
• Historical patterns        • Liquidity

             Δ = E - R (Divergence)
                    ↓
         Risk Score + Opportunity Signal
```

## Troubleshooting

### "no such table: trading_simulations"
→ Run `python add_simulation_table.py`

### "No module named 'sqlalchemy'"
→ Activate venv: `.venv\Scripts\activate` (Windows) oder `source .venv/bin/activate` (Linux/Mac)

### Simulations zeigen alle "hold"
→ Confidence oder Expected Return zu niedrig, oder Risk Score zu hoch
→ Thresholds in `TradingSimulationEngine` anpassen

### Keine Live-Marktdaten
→ yfinance braucht Internet-Zugriff
→ Firewall/Proxy prüfen

## Next Steps

- [ ] Modal-Detail-Ansicht im Simulations-Tab
- [ ] Simulation-Details im Prediction-Modal
- [ ] Portfolio-View (aggregierte Simulations)
- [ ] Backtesting über historische Predictions
- [ ] Performance-Tracking (PnL über Zeit)
