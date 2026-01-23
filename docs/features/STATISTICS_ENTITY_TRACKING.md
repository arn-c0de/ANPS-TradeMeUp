# Statistics Tab - Entity & Sentiment Tracking

## Übersicht
Die Statistics-Seite wurde massiv erweitert mit umfangreichen Entity/Firmen-Tracking und Sentiment-Analyse-Features, die eine vollständige Nachverfolgung aller von Agents in die DB geschriebenen Daten ermöglichen.

---

## Neue Features ✨

### 1. **Entity Sentiment Analysis Chart** 📊
Interaktives Balkendiagramm zeigt durchschnittliche Sentiment-Scores pro Entity über verschiedene Zeiträume:
- **Zeitfilter**: 7 Tage, 30 Tage, 90 Tage, All Time
- **Farbcodierung**: 
  - 🟢 Grün = Positive Sentiment (> 0.2)
  - 🔴 Rot = Negative Sentiment (< -0.2)
  - ⚪ Grau = Neutral (-0.2 bis 0.2)
- **Top 15 Entities** werden angezeigt
- Automatische Sortierung nach Sentiment

### 2. **Top Positive Entities (Last 30 Days)** 📈
Liste der Firmen mit den meisten positiven Nachrichten:
- Anzeige von Positive/Neutral/Negative News-Counts
- Durchschnittlicher Sentiment-Score
- Top 10 Ranking mit Badges
- Live-Update alle 5 Sekunden

### 3. **Top Negative Entities (Last 30 Days)** 📉
Liste der Firmen mit den meisten negativen Nachrichten:
- Identisch zur Positive-Liste, aber umgekehrt sortiert
- Wichtig für Risiko-Monitoring
- Hilft bei Short-Kandidaten-Identifikation

### 4. **Entity Details Table** 🏢
Umfassende Detailtabelle mit allen tracked Entities:
- **Suchfunktion**: Live-Suche nach Name oder ID/Ticker
- **Spalten**:
  - Entity Name
  - Type (company, sector, index, etc.)
  - ID/Ticker
  - Mentions (Anzahl News-Erwähnungen)
  - Impact Scores (Anzahl berechneter Impact-Scores)
  - Average Impact (Durchschnittlicher Impact-Score mit Farbcodierung)
  - Metadata (Industrie, Market Cap, etc.)
- **Top 50 Entities** nach Mentions sortiert
- Responsive Design mit Striped/Hover-Effekten

### 5. **Erweiterte Metrics** 📊
Die Overall Metrics-Sektion zeigt jetzt zusätzlich:
- Total Entities
- Total Impact Scores
- Total Surprises
- Total Fact Checks
- Total Regimes
- Average Quality Score

---

## Datenbank-Struktur (Genutzte Tabellen)

### **Entities** (`entities`)
```sql
- entity_id: Ticker oder Code (Primary Key)
- entity_type: company, sector, index, person
- entity_name: Firmenname
- metadata_: JSON mit Zusatzinfos (Industry, Market Cap)
- created_at: Timestamp
```

### **News-Entity-Mapping** (`news_entity_mapping`)
```sql
- mapping_id: UUID (Primary Key)
- news_id: Foreign Key zu raw_news
- entity_id: Foreign Key zu entities
- exposure_type: direct, indirect, supply_chain
- confidence: 0-1 Score
- mention_count: Anzahl Erwähnungen im Artikel
- created_at: Timestamp
```

### **Impact Scores** (`impact_scores`)
```sql
- score_id: UUID (Primary Key)
- news_id: Foreign Key zu raw_news
- entity_id: Foreign Key zu entities
- impact_score: 0-1 Score (Auswirkung auf Entity)
- impact_breakdown: JSON mit Details
- confidence: 0-1 Score
- time_horizon: short_term, medium_term, long_term
- expected_volatility_impact: Float
- created_at: Timestamp
```

### **Processed News** (`processed_news`)
```sql
- news_id: Foreign Key zu raw_news (Primary Key)
- sentiment: JSON mit Overall & Aspect-based Sentiment
- event_type: earnings, M&A, regulation, etc.
- summary_short: 1-Satz-Zusammenfassung
- key_facts: JSON mit extrahierten Fakten
- confidence: 0-1 Score
```

### **Surprise Scores** (`surprise_scores`)
```sql
- surprise_id: UUID (Primary Key)
- news_id: Foreign Key zu raw_news
- metric: earnings_per_share, revenue, etc.
- actual: Tatsächlicher Wert
- consensus: Erwarteter Wert
- surprise_normalized: In Std-Abweichungen
- true_surprise: Nach Market-Pricing
```

---

## Verwendete Agents

Die folgenden Agents schreiben in die genutzten Tabellen:

### 1. **Entity Mapping Agent**
- Extrahiert Entities aus News (Firmen, Personen, Sektoren)
- Erstellt `Entity`-Einträge
- Mappt Entities zu News via `NewsEntityMapping`
- Berechnet Confidence & Mention-Counts

### 2. **Content Understanding Agent**
- Analysiert Sentiment (Overall & Aspect-based)
- Extrahiert Event-Types und Key Facts
- Schreibt in `ProcessedNews.sentiment`
- Basis für Sentiment-Charts

### 3. **Impact Scoring Agent**
- Berechnet Impact-Scores für Entity-News-Paare
- Schreibt in `ImpactScore` Tabelle
- Berücksichtigt Time-Horizon
- Liefert Daten für Impact-Distribution

### 4. **Surprise Quantification Agent**
- Quantifiziert Überraschungen (Earnings, Revenue)
- Schreibt in `SurpriseScore` Tabelle
- Berechnet True-Surprise nach Market-Pricing

### 5. **Data Quality Agent**
- Bewertet Qualität der News-Artikel
- Schreibt in `DataQualityScore` Tabelle
- Basis für Quality-Distribution-Chart

---

## Queries & Performance

### Entity Sentiment Aggregation
```sql
SELECT 
    e.entity_name,
    AVG(CAST(pn.sentiment->>'overall' AS FLOAT)) as avg_sentiment,
    COUNT(*) as mention_count
FROM entities e
JOIN news_entity_mapping nem ON e.entity_id = nem.entity_id
JOIN processed_news pn ON nem.news_id = pn.news_id
WHERE rn.fetched_at >= NOW() - INTERVAL '30 days'
GROUP BY e.entity_name
ORDER BY avg_sentiment DESC
LIMIT 15
```

### Top Positive Entities
```sql
SELECT 
    e.entity_name,
    SUM(CASE WHEN sentiment->>'overall' > 0.3 THEN 1 ELSE 0 END) as positive_count,
    SUM(CASE WHEN sentiment->>'overall' < -0.3 THEN 1 ELSE 0 END) as negative_count,
    AVG(CAST(sentiment->>'overall' AS FLOAT)) as avg_sentiment
FROM entities e
JOIN news_entity_mapping nem ON e.entity_id = nem.entity_id
JOIN processed_news pn ON nem.news_id = pn.news_id
WHERE fetched_at >= NOW() - INTERVAL '30 days'
GROUP BY e.entity_name
ORDER BY positive_count DESC, avg_sentiment DESC
LIMIT 10
```

---

## UI Components

### Charts
- **Plotly Dark Theme**: Alle Charts nutzen dunkles Theme
- **Responsive**: Auto-Sizing für verschiedene Bildschirmgrößen
- **Interactive**: Hover-Tooltips, Zoom, Pan
- **Live-Updates**: Alle 5 Sekunden via Interval-Component

### Filters & Controls
- **Timeframe Selector**: Dropdown für 7d/30d/90d/All Time
- **Entity Search**: Live-Suche mit SQL ILIKE
- **Color Coding**: Sentiment & Impact via Badge-Colors

### Tables
- **Bootstrap Dark Tables**: Striped, Bordered, Hover
- **Responsive**: Horizontal Scroll auf Mobile
- **Sortierung**: Nach Mentions/Impact standardmäßig
- **Badges**: Farbcodierte Metriken (Success/Danger/Warning)

---

## Callbacks (app.py)

### Standard Updates (alle 5 Sekunden)
```python
@app.callback(
    Output("entity-sentiment-chart", "figure"),
    [Input("interval-component", "n_intervals"),
     Input("sentiment-timeframe-selector", "value")]
)
def update_entity_sentiment_chart(n, timeframe):
    return statistics.get_entity_sentiment_chart(engine, timeframe)
```

### Search-Based Updates (on user input)
```python
@app.callback(
    Output("entity-details-table", "children"),
    [Input("interval-component", "n_intervals"),
     Input("entity-search-input", "value")]
)
def update_entity_details_table(n, search_term):
    return statistics.get_entity_details_table(engine, search_term or "")
```

---

## Verwendung

### 1. Pipeline ausführen
```bash
python scripts/run_mvp_pipeline.py
```
Dies füllt die DB mit:
- Raw News
- Processed News (mit Sentiment)
- Entities & Mappings
- Impact Scores

### 2. Dashboard öffnen
```bash
python run_dashboard.py
```
Navigiere zu: http://localhost:8050

### 3. Statistics Tab öffnen
- Klicke auf **📊 Statistics** Tab
- Alle Charts laden automatisch
- Timeframe anpassen via Dropdown
- Entity-Suche nutzen für Filterung

---

## Beispiel-Insights

### Positives Sentiment erkennen
**Top Positive Entities** zeigt z.B.:
```
#1 Tesla Motors
   ✅ 12 Positive | 3 Neutral | 1 Negative | Avg: 0.67
   
#2 Apple Inc.
   ✅ 10 Positive | 5 Neutral | 2 Negative | Avg: 0.54
```

### Risiko-Monitoring
**Top Negative Entities** zeigt z.B.:
```
#1 Boeing
   ❌ 8 Negative | 4 Neutral | 1 Positive | Avg: -0.45
   
#2 Meta Platforms
   ❌ 6 Negative | 3 Neutral | 2 Positive | Avg: -0.32
```

### Entity-Details durchsuchen
Suche nach "Tesla":
```
Entity        | Type    | ID   | Mentions | Impact | Avg Impact | Metadata
Tesla Motors  | company | TSLA | 15       | 12     | 0.72 🔴    | Industry: Automotive
```

---

## Zukünftige Erweiterungen

### Geplante Features
- [ ] **Sentiment-Trends**: Zeitlicher Verlauf pro Entity
- [ ] **Correlation Matrix**: Sentiment-Korrelationen zwischen Entities
- [ ] **Alert System**: Notifications bei extremen Sentiment-Shifts
- [ ] **Export Funktion**: CSV/Excel Export der Entity-Daten
- [ ] **Drill-Down**: Klick auf Entity zeigt alle Related News
- [ ] **Supply-Chain-Graph**: Visualisierung von Entity-Relationships
- [ ] **Sector-Aggregation**: Sentiment auf Sektor-Ebene
- [ ] **Competitive Analysis**: Side-by-Side Vergleich von Competitors

---

## Troubleshooting

### "No sentiment data available"
**Lösung**: Content Understanding Agent muss laufen
```bash
# Prüfe ob ProcessedNews.sentiment gefüllt ist
SELECT COUNT(*) FROM processed_news WHERE sentiment IS NOT NULL;
```

### "No entities tracked yet"
**Lösung**: Entity Mapping Agent muss laufen
```bash
# Prüfe Entities
SELECT COUNT(*) FROM entities;
```

### Langsame Chart-Ladevorgänge
**Lösung**: DB-Indizes prüfen
```sql
-- Wichtige Indizes
CREATE INDEX idx_mapping_entity_time ON news_entity_mapping(entity_id, created_at);
CREATE INDEX idx_impact_entity_time ON impact_scores(entity_id, created_at);
CREATE INDEX idx_news_fetched ON raw_news(fetched_at);
```

---

**Erstellt**: 23. Januar 2026  
**Version**: 1.2.0  
**Autor**: GitHub Copilot
