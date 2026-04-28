# PostgreSQL Setup

The recommended setup uses Docker and the bundled `pgvector` image.

## Recommended: Docker

```bash
cp .env.example .env.local
docker compose up -d postgres
python scripts/db/test_db_connection.py
alembic upgrade head
```

Default local database values:

- host: `localhost`
- port: `5432`
- database: `trademeup`
- user: `trademeup_user`
- password: `trademeup_pass`

## Native PostgreSQL

If you run PostgreSQL outside Docker:

1. Install PostgreSQL 16+
2. Install `pgvector`
3. Create the `trademeup` database
4. Enable:
   - `uuid-ossp`
   - `vector`
5. Set `DATABASE_URL` in `.env.local`
6. Run:

```bash
python scripts/db/test_db_connection.py
alembic upgrade head
```

## SQL helper

If you need the SQL bootstrap file directly:

- `scripts/db/setup_postgresql.sql`

## Validation

```bash
python scripts/db/test_db_connection.py
python tests/checks/check_tables.py
```

## Legacy SQLite migration

The old SQLite migration helpers were intentionally removed from the default setup path and archived here:

- `archive/legacy/sqlite/migrate_sqlite_to_postgres.py`
- `archive/legacy/sqlite/remigrate_boolean_tables.py`

Only use them for one-time migration or recovery scenarios.
