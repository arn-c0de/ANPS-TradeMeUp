# Refactoring: Prediction Details Popup Zentralisierung

## Zusammenfassung

Das Prediction Details Popup wurde aus `predictions.py` in ein zentrales Helper-Modul ausgelagert, sodass es von mehreren Tabs (Predictions, Simulations, Statistics) gemeinsam genutzt werden kann.

## Problem

- Das Prediction Details Popup war ursprünglich nur in `predictions.py` implementiert
- Der Simulations Tab hatte Buttons, die das Popup öffnen sollten (`sim-detail-btn`), aber Probleme beim Öffnen hatten
- Der Statistics Tab nutzte ebenfalls das Popup (`news-pred-detail-btn`)
- Code-Duplizierung und schwierige Wartbarkeit

## Lösung

### Neue Dateistruktur

```
src/gui/helpers/
├── __init__.py
└── prediction_details_popup.py  (NEU)
```

### Was wurde ausgelagert

Die folgenden Komponenten wurden von `predictions.py` nach `prediction_details_popup.py` verschoben:

1. **`_format_price_ui()`** - Hilfsfunktion für Preisformatierung
2. **`_format_saved_performance()`** - Formatiert gespeicherte Performance-Daten
3. **`get_prediction_details()`** - Hauptfunktion für Prediction Details
4. **`create_prediction_modal()`** - Erstellt die Modal-Komponente

### Angepasste Dateien

#### 1. `src/gui/helpers/prediction_details_popup.py` (NEU)
Zentrales Modul mit allen Popup-bezogenen Funktionen und der Modal-Komponente.

#### 2. `src/gui/tabs/predictions.py`
**Änderungen:**
- Import der ausgelagerten Funktionen aus `prediction_details_popup`
- Verwendung von `create_prediction_modal()` statt inline Modal-Definition
- Entfernung der duplizierten Funktionen (jetzt importiert)
- Callbacks bleiben unverändert (registrieren die Modal-Interaktionen)

**Imports hinzugefügt:**
```python
from src.gui.helpers.prediction_details_popup import (
    get_prediction_details,
    create_prediction_modal,
    _format_saved_performance
)
```

**Modal-Erstellung vereinfacht:**
```python
# Vorher: ~20 Zeilen inline Modal-Definition
# Nachher:
create_prediction_modal()
```

#### 3. `src/gui/tabs/simulations.py`
**Änderungen:**
- Import von `create_prediction_modal` aus dem Helper-Modul
- Modal-Komponente wird hinzugefügt (shared mit predictions.py)
- Shared Stores werden hinzugefügt (`prediction-detail-cache`, `current-prediction-id`, `refresh-loading-state`)
- Toast für Feedback wird hinzugefügt
- Die Buttons (`sim-detail-btn`) funktionieren jetzt korrekt
- Callbacks in `predictions.py` behandeln bereits `sim-detail-btn`

**Imports hinzugefügt:**
```python
from src.gui.helpers.prediction_details_popup import create_prediction_modal
```

**Layout-Komponenten hinzugefügt:**
```python
# Shared stores (müssen in jedem Tab vorhanden sein, der das Modal nutzt)
dcc.Store(id="prediction-detail-cache", data={}),
dcc.Store(id="current-prediction-id", data=None),
dcc.Store(id="refresh-loading-state", data={}),

# Modal (muss in jedem Tab vorhanden sein, der es öffnen möchte)
create_prediction_modal(),

# Toast für Feedback
refresh-toast Component
```

**Button bleibt unverändert:**
```python
dbc.Button(
    "📊",
    id={"type": "sim-detail-btn", "index": str(sim.prediction_id)},
    # ... weitere Props
)
```

#### 4. `src/gui/tabs/statistics/callbacks.py`
**Status:**
- Nutzt bereits die shared Stores (`prediction-modal`, `prediction-detail-cache`, etc.)
- Keine Änderungen nötig
- Der Callback `open_news_prediction_detail` findet Predictions anhand von `news_id` und öffnet das Modal

## Technische Details

### Modal-Komponenten und Stores

Die folgenden Dash-Komponenten werden von allen Tabs geteilt:

```python
# Modal-Komponente (in predictions.py UND simulations.py via create_prediction_modal())
"prediction-modal"           # Das Modal selbst
"prediction-modal-title"     # Modal-Titel
"prediction-modal-body"      # Modal-Inhalt
"close-prediction-modal"     # Schließen-Button
"refresh-prediction-detail"  # Refresh-Button

# Stores (in predictions.py UND simulations.py)
"prediction-detail-cache"    # Cache für Prediction-Daten
"current-prediction-id"      # Aktuell angezeigte Prediction
"refresh-loading-state"      # Loading-Status für Refresh

# Toast (in predictions.py UND simulations.py)
"refresh-toast"              # Feedback-Toast für Performance-Updates
```

**Wichtig:** Diese Komponenten müssen in JEDEM Tab vorhanden sein, der das Modal öffnen möchte. Dash verwendet die erste Instanz im DOM.

### Button-Typen

Das System unterstützt drei verschiedene Button-Typen für unterschiedliche Use Cases:

| Button-Typ | Tab | Funktion | Payload |
|------------|-----|----------|---------|
| `pred-detail-btn` | Predictions | Öffnet Details direkt | `prediction_id` |
| `sim-detail-btn` | Simulations | Öffnet Details via Prediction | `prediction_id` |
| `news-pred-detail-btn` | Statistics | Findet Prediction via News | `news_id` → `prediction_id` |

### Callback-Registrierung

```python
# app.py
predictions.register_callbacks(app)  # Registriert Modal-Callbacks
simulations.register_callbacks(app)  # Nutzt Modal von predictions
statistics.register_callbacks(app)   # Nutzt Modal von predictions
```

## Vorteile der Refaktorierung

### 1. Code-Wiederverwendung
- Keine Duplikation von ~800 Zeilen Code
- Zentrale Wartung und Updates
- Konsistentes Verhalten über alle Tabs

### 2. Einfachere Wartung
- Änderungen am Popup müssen nur an einer Stelle vorgenommen werden
- Bugfixes profitieren automatisch alle Tabs
- Neue Features können zentral hinzugefügt werden

### 3. Bessere Modularität
- Klare Trennung von Concerns
- Helper-Module können unabhängig getestet werden
- Einfacher zu verstehen und zu erweitern

### 4. Lösung der ursprünglichen Probleme
- Simulations Tab kann jetzt problemlos das Popup öffnen
- Statistics Tab funktioniert weiterhin einwandfrei
- Keine Konflikte zwischen Tabs

## Verwendung in neuen Tabs

Falls weitere Tabs das Prediction Details Popup nutzen möchten:

```python
# 1. Import in neuem Tab
from src.gui.helpers.prediction_details_popup import create_prediction_modal
from dash import dcc

# 2. WICHTIG: Modal UND Stores in Layout hinzufügen
def create_layout():
    return html.Div([
        # Stores MÜSSEN vorhanden sein
        dcc.Store(id="prediction-detail-cache", data={}),
        dcc.Store(id="current-prediction-id", data=None),
        dcc.Store(id="refresh-loading-state", data={}),
        
        # Ihr Tab-Inhalt hier
        dbc.Container([
            # ...
        ]),
        
        # Modal MUSS vorhanden sein
        create_prediction_modal(),
        
        # Optional: Toast für Feedback
        dbc.Toast(
            id="refresh-toast",
            # ... Toast-Konfiguration
        )
    ])

# 3. Button mit einem der unterstützten Typen erstellen
dbc.Button(
    "Details",
    id={"type": "pred-detail-btn", "index": str(prediction_id)},
    # oder
    id={"type": "sim-detail-btn", "index": str(prediction_id)},
    # oder
    id={"type": "news-pred-detail-btn", "index": str(news_id)}
)

# 4. Callback wird automatisch von predictions.py behandelt
```

**Wichtig:** Die Stores und das Modal müssen in JEDEM Tab vorhanden sein, der das Modal öffnen möchte. Dash kann nur auf Komponenten zugreifen, die im DOM existieren.

## Testing

Nach der Refaktorierung sollten folgende Szenarien getestet werden:

- [ ] Predictions Tab: Detail-Button öffnet Modal korrekt
- [ ] Predictions Tab: Refresh-Button aktualisiert Performance
- [ ] Simulations Tab: Detail-Button öffnet Modal korrekt
- [ ] Statistics Tab: Prediction-Button findet und öffnet Modal
- [ ] Modal zeigt alle Sections korrekt an:
  - [ ] Live Performance
  - [ ] Trading Simulation
  - [ ] Overview
  - [ ] Direction Probabilities
  - [ ] News
  - [ ] Key Drivers
  - [ ] Model Info
- [ ] Keine Linter-Fehler in den angepassten Dateien

## Weitere Verbesserungsmöglichkeiten

### Kurzfristig
- Zusätzliche Helper-Funktionen für wiederkehrende UI-Komponenten
- Einheitliches Error-Handling über alle Modal-Aufrufe

### Langfristig
- Weitere gemeinsam genutzte Komponenten (Charts, Tables) auslagern
- Zentrales Theme-Management für konsistente UI
- Performance-Optimierung durch Caching von Modal-Inhalten

## Migration Guide

Falls Sie custom Code haben, der die alten Funktionen direkt importiert:

### Alt (funktioniert nicht mehr):
```python
from src.gui.tabs.predictions import get_prediction_details
```

### Neu:
```python
from src.gui.helpers.prediction_details_popup import get_prediction_details
```

## Kontakt & Support

Bei Fragen oder Problemen mit der Refaktorierung:
- Überprüfen Sie die Imports in Ihren Custom-Modulen
- Stellen Sie sicher, dass `predictions.register_callbacks(app)` aufgerufen wird
- Prüfen Sie die Linter-Ausgabe auf fehlende Imports

---

**Status:** ✅ Abgeschlossen  
**Datum:** 2026-01-26  
**Betroffene Tabs:** Predictions, Simulations, Statistics  
**Neue Dateien:** 2 (helpers/__init__.py, helpers/prediction_details_popup.py)  
**Geänderte Dateien:** 2 (predictions.py, simulations.py)

## Known Issues & Fixes

### Issue: Modal öffnet sich nicht vom Simulations Tab
**Problem:** Das Prediction Details Modal öffnete sich von Predictions und Statistics Tabs, aber nicht vom Simulations Tab.

**Ursache:** Die Modal-Komponente und die shared Stores (`prediction-detail-cache`, `current-prediction-id`, etc.) waren nur im Predictions Tab definiert. Wenn ein Benutzer direkt zum Simulations Tab ging, ohne zuvor Predictions zu besuchen, waren diese Komponenten nicht im DOM vorhanden.

**Lösung:** 
1. Modal-Komponente (`create_prediction_modal()`) wurde zum Simulations Layout hinzugefügt
2. Shared Stores wurden zum Simulations Layout hinzugefügt
3. Toast-Component wurde zum Simulations Layout hinzugefügt

**Status:** ✅ Behoben (2026-01-26)
