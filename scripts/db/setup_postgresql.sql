-- ==========================================
-- PostgreSQL Setup Script für TradeMeUp
-- ==========================================
-- Führen Sie dieses Skript als PostgreSQL-Superuser aus
-- 
-- Windows: Öffnen Sie SQL Shell (psql) als Administrator
-- Oder: psql -U postgres -f setup_postgresql.sql
-- ==========================================

-- 1. Datenbank erstellen
DROP DATABASE IF EXISTS trademeup;
CREATE DATABASE trademeup
    WITH 
    ENCODING = 'UTF8'
    LC_COLLATE = 'German_Germany.1252'
    LC_CTYPE = 'German_Germany.1252'
    TEMPLATE = template0;

-- 2. Benutzer erstellen (optional - Sie können auch 'postgres' verwenden)
-- Kommentieren Sie die nächsten Zeilen aus, wenn Sie den Benutzer 'postgres' verwenden
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'trademeup_user') THEN
        CREATE USER trademeup_user WITH PASSWORD 'trademeup_pass';
    END IF;
END
$$;

-- 3. Berechtigungen vergeben
GRANT ALL PRIVILEGES ON DATABASE trademeup TO trademeup_user;

-- 4. Mit der neuen Datenbank verbinden
\c trademeup

-- 5. Erweiterungen aktivieren
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 6. Schema-Berechtigungen (für trademeup_user)
GRANT ALL ON SCHEMA public TO trademeup_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trademeup_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO trademeup_user;

-- 7. Standard-Berechtigungen für zukünftige Objekte
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO trademeup_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO trademeup_user;

-- Fertig!
\echo '============================================================'
\echo 'PostgreSQL Setup abgeschlossen!'
\echo '============================================================'
\echo 'Datenbank: trademeup'
\echo 'Erweiterungen: uuid-ossp, vector (pgvector)'
\echo ''
\echo 'Nächste Schritte:'
\echo '  1. Aktualisieren Sie .env.local mit den richtigen Zugangsdaten'
\echo '  2. Führen Sie Alembic-Migrationen aus: alembic upgrade head'
\echo '  3. Starten Sie die Anwendung'
\echo '============================================================'
