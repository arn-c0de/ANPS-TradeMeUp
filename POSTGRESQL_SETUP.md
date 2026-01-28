# PostgreSQL Setup Anleitung für Windows 11

## Schritt 1: PostgreSQL-Verbindungsdaten herausfinden

Ihre PostgreSQL-Installation läuft bereits. Sie müssen nur:

1. **Ihr PostgreSQL-Passwort kennen** (das Sie bei der Installation gesetzt haben)
2. **Port prüfen** (Standard: 5432)

## Schritt 2: .env.local aktualisieren

Öffnen Sie `.env.local` und aktualisieren Sie die DATABASE_URL:

```env
# Option 1: Mit postgres Benutzer (einfachste)
DATABASE_URL=postgresql://postgres:IHR_PASSWORT@localhost:5432/trademeup

# Option 2: Mit dediziertem Benutzer (empfohlen)
DATABASE_URL=postgresql://trademeup_user:trademeup_pass@localhost:5432/trademeup
```

Ersetzen Sie `IHR_PASSWORT` mit Ihrem tatsächlichen PostgreSQL-Passwort!

## Schritt 3: Datenbank erstellen

### Option A: Mit SQL Shell (psql) - EMPFOHLEN

1. Öffnen Sie **SQL Shell (psql)** aus dem Startmenü
2. Drücken Sie Enter für Server, Database, Port, Username (nutzt Standardwerte)
3. Geben Sie Ihr PostgreSQL-Passwort ein
4. Führen Sie aus:

```sql
-- Datenbank erstellen
CREATE DATABASE trademeup;

-- pgvector Extension aktivieren
\c trademeup
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Berechtigungen für postgres-User (wenn Sie den verwenden)
GRANT ALL PRIVILEGES ON DATABASE trademeup TO postgres;

-- Fertig!
\q
```

### Option B: Mit setup_postgresql.sql Skript

```bash
# Im SQL Shell (psql):
\i D:/Projects/PYTHON - FOLDER/TradeMeUp/setup_postgresql.sql
```

Oder in PowerShell:
```powershell
psql -U postgres -f setup_postgresql.sql
```

## Schritt 4: pgvector Extension in PostgreSQL installieren

Falls pgvector noch nicht verfügbar ist, müssen Sie es installieren:

1. Laden Sie pgvector von: https://github.com/pgvector/pgvector/releases
2. Oder nutzen Sie Stack Builder (kommt mit PostgreSQL)
3. Oder nutzen Sie Docker (einfachste Option): 
   ```bash
   docker pull pgvector/pgvector:pg16
   docker run --name trademeup_postgres -e POSTGRES_PASSWORD=yourpass -p 5432:5432 -d pgvector/pgvector:pg16
   ```

**Hinweis:** Wenn Sie PostgreSQL ohne pgvector installiert haben, ist die Docker-Option am einfachsten!

## Schritt 5: Verbindung testen

```bash
.\venv\Scripts\activate
python test_postgresql_connection.py
```

Sie sollten sehen:
```
[OK] Connected to PostgreSQL!
[OK] pgvector extension is installed
[OK] uuid-ossp extension is installed
```

## Schritt 6: Tabellen erstellen mit Alembic

```bash
.\venv\Scripts\activate
alembic upgrade head
```

Dies erstellt alle 16+ Tabellen mit:
- Nativen UUID-Typen
- JSONB-Spalten für schnelle JSON-Abfragen
- pgvector-Spalten für Embeddings
- GIN-Indizes
- IVFFlat-Indizes für Vektorsuche

## Schritt 7: Daten migrieren (falls Sie SQLite-Daten haben)

```bash
python scripts/migrate_sqlite_to_postgresql.py
```

## Troubleshooting

### "Extension 'vector' not found"

pgvector ist nicht installiert. Lösungen:
1. Nutzen Sie Docker mit pgvector/pgvector Image (empfohlen)
2. Installieren Sie pgvector manuell: https://github.com/pgvector/pgvector

### "Permission denied" oder "Password authentication failed"

Prüfen Sie:
1. Ist das Passwort in `.env.local` korrekt?
2. Läuft PostgreSQL? (Task Manager → Dienste → postgresql-x64-XX)
3. Ist Port 5432 offen? `netstat -an | findstr 5432`

### "Database does not exist"

Führen Sie Schritt 3 aus, um die Datenbank zu erstellen.

## Empfohlene Einstellung für Windows 11

Wenn Sie noch keine pgvector-Erweiterung haben:

```bash
# 1. Stoppen Sie lokales PostgreSQL (falls vorhanden)
# Dienste → postgresql-x64-XX → Stopp

# 2. Installieren Sie Docker Desktop
# https://www.docker.com/products/docker-desktop/

# 3. Starten Sie PostgreSQL mit pgvector über Docker
docker-compose up -d

# 4. Das wars! Alles ist vorkonfiguriert:
# - Datenbank: trademeup
# - User: trademeup_user
# - Password: trademeup_pass
# - Port: 5432
# - Extensions: vector, uuid-ossp

# 5. Keine Änderung in .env.local nötig (nutzt bereits diese Werte)
```

## Performance-Check

Nach dem Setup:

```bash
python scripts/benchmark_postgresql.py
```

Erwartete Verbesserungen gegenüber SQLite:
- 30-50% schnellere komplexe Queries
- 10-20x schnellerer concurrent access
- Native Vektorsuche mit pgvector
