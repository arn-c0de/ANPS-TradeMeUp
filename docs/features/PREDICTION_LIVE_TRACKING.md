# Prediction Live Performance Tracking

## Übersicht

Das System validiert jetzt automatisch jede Prediction gegen echte Marktdaten und zeigt live die Performance an.

## Features

### 1. Live Return Tracking
- **Return seit Prediction**: Zeigt die tatsächliche Preisentwicklung seit der Prediction
- **24h Return**: Aktuelle 24-Stunden-Performance
- **Echtzeit-Preis**: Aktueller Live-Preis des Assets

### 2. Strategy Validation
Das System überprüft automatisch, ob die empfohlene Strategie funktioniert hätte:
- ✅ **BUY worked**: Bei UP-Prediction mit positivem Return
- ❌ **BUY failed**: Bei UP-Prediction mit negativem Return
- ✅ **SELL/SHORT worked**: Bei DOWN-Prediction mit negativem Return
- ❌ **SELL/SHORT failed**: Bei DOWN-Prediction mit positivem Return
- ⚪ **FLAT predicted**: Bei FLAT-Prediction

### 3. Erweiterte Metriken
- **Entry Price**: Preis zum Zeitpunkt der Prediction
- **Current Price**: Aktueller Live-Preis
- **High/Low Since Entry**: Höchster/niedrigster Preis seit Prediction
- **Volatility**: Preis-Volatilität während der Prediction-Periode
- **Days Active**: Anzahl Tage seit der Prediction

### 4. Accuracy Tracking
- **Predicted Direction**: Was wurde vorhergesagt (UP/DOWN/FLAT)
- **Actual Direction**: Was tatsächlich passiert ist
- **Accuracy Status**: ✅ Correct oder ❌ Wrong

## Technische Details

### PredictionPerformanceService

Der neue Service ([prediction_performance_service.py](../../src/services/prediction_performance_service.py)) bietet:

```python
from src.services import prediction_performance_service

# Einzelne Prediction Performance
performance = prediction_performance_service.get_prediction_performance(
    prediction=pred,
    entity=entity
)

# Batch Performance für mehrere Predictions
batch_results = prediction_performance_service.get_batch_performance(
    predictions=pred_list,
    db_session=db
)

# Gesamt-Accuracy-Statistiken
stats = prediction_performance_service.get_prediction_accuracy_stats(
    predictions=pred_list,
    db_session=db
)
```

### Datenquellen

- **Marktdaten**: Yahoo Finance via `yfinance` Library
- **Historische Preise**: OHLCV Daten seit Prediction-Zeitpunkt
- **Live-Preise**: Real-time Quote-Daten

### Caching

Der MarketDataProvider cached Preisdaten für 60 Sekunden (Standard) und nutzt bis zu 1-Stunden-alte Daten als Fallback bei API-Fehlern.

## UI Integration

### Predictions-Tabelle

Neue Spalten in der Predictions-Übersicht:
1. **📊 Live Return**: Return seit Prediction (farbcodiert)
2. **✓/✗ Result**: Ob Buy/Sell funktioniert hätte
3. **📈 24h**: 24-Stunden-Performance

### Detail-Modal

Erweiterte Prediction-Details mit:
- Live Performance Card (Return, Strategy Result, 24h, Days Active)
- Preis-Details (Entry, Current, Change, High/Low)
- Accuracy-Analyse (Predicted vs Actual Direction)

## Fehlerbehandlung

- **Keine Marktdaten verfügbar**: Zeigt "N/A" statt Fehler
- **API-Fehler**: Nutzt gecachte Daten wenn verfügbar
- **Ticker nicht gefunden**: Warning-Log, keine UI-Blockierung
- **Geschlossener Markt**: Nutzt letzten verfügbaren Schlusskurs

## Performance-Überlegungen

- **API-Rate-Limits**: yfinance hat keine offizielle Rate-Limit-Dokumentation, aber sollte sparsam genutzt werden
- **Caching**: Reduziert API-Calls erheblich
- **Batch-Processing**: Wenn möglich, mehrere Predictions auf einmal verarbeiten
- **Async Loading**: UI zeigt "⏳ Loading..." während Daten geladen werden

## Zukunft Enhancements

Mögliche zukünftige Features:
- [ ] Chart-Overlay mit Prediction-Marker
- [ ] Historical Performance-Tracking über Zeit
- [ ] Confidence vs Actual-Return Correlation-Analyse
- [ ] Auto-Alert bei großen Abweichungen
- [ ] Portfolio-Simulation basierend auf Predictions
- [ ] Export von Performance-Reports

## Beispiel-Output

```python
{
    'ticker': 'AAPL',
    'current_price': 182.45,
    'prediction_price': 180.00,
    'prediction_date': datetime(2026, 1, 20),
    'total_return_pct': 1.36,
    'return_24h_pct': 0.42,
    'predicted_direction': 'up',
    'actual_direction': 'up',
    'is_correct': True,
    'strategy_result': '✅ BUY worked',
    'days_since_prediction': 3,
    'high_since_prediction': 183.50,
    'low_since_prediction': 179.20,
    'volatility': 1.24,
    'timestamp': datetime(2026, 1, 23, 15, 30)
}
```

## Testing

Um die Funktionalität zu testen:

1. **Dashboard starten**: `python run_dashboard.py`
2. **Predictions Tab öffnen**: Navigiere zu "Predictions"
3. **Live-Daten prüfen**: Tabelle zeigt automatisch Live-Performance
4. **Details öffnen**: Klicke "Details" für erweiterte Performance-Metriken

## Bekannte Limitierungen

- **Nur US-Märkte**: yfinance fokussiert sich auf US-Börsen (NYSE, NASDAQ)
- **Delayed Data**: Einige Daten können 15-20 Minuten verzögert sein
- **Weekend/Holidays**: Keine Echtzeit-Updates wenn Märkte geschlossen
- **API-Stabilität**: yfinance ist ein inoffizielles API-Wrapper

## Dependencies

```txt
yfinance==1.0
pandas>=1.5.0
tenacity>=8.0.0  # Für Retry-Logic
```
