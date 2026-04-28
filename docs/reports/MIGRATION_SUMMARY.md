# SQLite zu PostgreSQL Migration - Zusammenfassung

> Historical snapshot from the SQLite-to-PostgreSQL migration. The referenced migration helpers now live under `archive/legacy/sqlite/`, and the current runtime/docs entrypoints live under `scripts/` and `docs/setup/`.

## Datum: 2026-02-04

## ✅ Erfolgreich abgeschlossene Aufgaben

### 1. PostgreSQL Installation
- PostgreSQL-Client (postgresql-client-16) installiert
- Docker-Container mit pgvector/pgvector:pg18 Image gestartet
- Volume-Konfiguration für PostgreSQL 18 angepasst (`/var/lib/postgresql` statt `/var/lib/postgresql/data`)

### 2. Datenbank-Einrichtung
- PostgreSQL-Container läuft auf Port 5432
- Datenbank: `trademeup`
- Benutzer: `trademeup_user`
- Docker-Container: `trademeup_postgres`

### 3. Schema-Initialisierung
- Alle Tabellen erfolgreich mit `scripts/db/init_database.py` erstellt
- Migrations-Skripte `migrations/init.sql` angewendet
- 17 Tabellen erstellt

### 4. Daten-Migration
- Migrationsskript erstellt: `archive/legacy/sqlite/migrate_sqlite_to_postgres.py`
- Spezielles Skript für Boolean-Konvertierung: `archive/legacy/sqlite/remigrate_boolean_tables.py`
- SQLite-Datenbank: `trademeup.db`

#### Migrierte Daten:
| Tabelle | SQLite | PostgreSQL | Status |
|---------|--------|------------|--------|
| raw_news | 3625 | 3625 | ✅ 100% |
| processed_news | 3625 | 3625 | ✅ 100% |
| data_quality_scores | 3625 | 3625 | ✅ 100% |
| predictions | 1224 | 1224 | ✅ 100% |
| trading_simulations | 1210 | 1210 | ✅ 100% |
| prediction_outcomes | 1164 | 1154 | ⚠️ 99.1% (10 FK-Fehler) |
| entities | 539 | 539 | ✅ 100% |
| impact_scores | 747 | 747 | ✅ 100% |
| news_entity_mapping | 747 | 747 | ✅ 100% |
| fact_verifications | 517 | 517 | ✅ 100% |
| market_regimes | 200 | 200 | ✅ 100% |
| chart_overlays | 1 | 1 | ✅ 100% |
| surprise_scores | 1 | 1 | ✅ 100% |

**Gesamt: 16.225 Zeilen migriert, 10 fehlgeschlagen (0,06% Fehlerrate)**

### 5. Datentyp-Konvertierungen
- **Boolean-Felder**: SQLite Integer (0/1) → PostgreSQL Boolean (true/false)
- **Timestamps**: Korrekt übernommen mit Timezone-Support
- **JSON-Felder**: JSONB-Format beibehalten
- **UUID-Felder**: Korrekt übernommen

### 6. Verifizierung
- ✅ Row-Counts überprüft und stimmen überein
- ✅ Stichproben aus allen Haupttabellen geprüft
- ✅ Datenintegrität verifiziert (neueste Artikel, Predictions, Simulations)
- ✅ Foreign-Key-Constraints funktionieren

## 📝 Bekannte Probleme

### Foreign-Key-Verletzungen (10 Zeilen)
- **Tabelle**: `prediction_outcomes`
- **Ursache**: 10 prediction_ids existieren nicht in der `predictions`-Tabelle
- **Impact**: Minimal (0,86% von prediction_outcomes)
- **Empfehlung**: Datenbereinigung in der Quelle (SQLite) durchführen

## 🔧 Technische Details

### Docker-Setup
```yaml
Service: postgres
Image: pgvector/pgvector:pg18
Container: trademeup_postgres
Port: 5432:5432
Volume: postgres_data:/var/lib/postgresql
```

### Verbindungsdetails
```
Host: localhost
Port: 5432
Database: trademeup
User: trademeup_user
Password: trademeup_pass
Connection String: postgresql://trademeup_user:trademeup_pass@localhost:5432/trademeup
```

### Installierte Tools
- PostgreSQL Client 16.11
- psycopg2-binary 2.9.11
- SQLite3 3.45.1

## 📊 Stichproben-Verifizierung

### Neueste Artikel (raw_news)
```
- "Trump Threatens Canada With 100% Tariffs" (2026-01-26 17:29:55)
- "Why this airline stock is hurt the most..." (2026-01-26 17:28:00)
- "Brazil Leader Urged Trump by Phone..." (2026-01-26 17:24:43)
```

### Predictions
```
- JBLU predictions für 1d, 5d, 20d Horizonte
- Confidence: ~0.71
- Expected Returns: ~1.7% (mean)
```

### Trading Simulations
```
- AGYS: buy, expected 1.62%, actual -0.0000085%
- NESN.SW: buy, expected 1.47%, actual 0.0000021%
```

## ✅ Nächste Schritte

1. **Backup der SQLite-Datenbank**:
   ```bash
   cp trademeup.db trademeup.db.backup
   ```

2. **.env-Datei anpassen** (falls noch nicht gemacht):
   ```
   DATABASE_URL=postgresql://trademeup_user:trademeup_pass@localhost:5432/trademeup
   ```

3. **Anwendung testen**:
   ```bash
   venv/bin/python scripts/db/init_database.py  # Sollte bereits existierende Tabellen erkennen
   venv/bin/python scripts/runtime/run_dashboard.py
   ```

4. **Optional: SQLite-Datenbank archivieren**:
   ```bash
   mv trademeup.db archive/trademeup.db.$(date +%Y%m%d)
   ```

## 🎯 Erfolgsmetriken

- ✅ PostgreSQL läuft stabil
- ✅ 99.94% der Daten erfolgreich migriert
- ✅ Alle Haupttabellen vollständig
- ✅ Datenintegrität verifiziert
- ✅ Performance-Indizes erstellt
- ✅ pgvector-Extension verfügbar für zukünftige Features

## 📞 Support

Bei Problemen:
1. PostgreSQL-Logs prüfen: `sudo docker logs trademeup_postgres`
2. Container-Status: `sudo docker ps -a`
3. Datenbankverbindung testen: `psql -h localhost -U trademeup_user -d trademeup`

---

**Migration erfolgreich abgeschlossen am 2026-02-04 23:32 UTC**
