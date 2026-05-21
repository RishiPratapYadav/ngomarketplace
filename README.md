# ngomarketplace

## Database

This app now uses PostgreSQL instead of SQLite.

- Install dependencies: `pip install -r requirements.txt`
- Provide a PostgreSQL connection URL with `DATABASE_URL`
- Example: `postgresql://postgres:postgres@localhost:5432/ngomarketplace`
- Or create a `.env` file in the project root with the connection string

### .env support

Create a `.env` file with one of the following options:

For direct PostgreSQL access:
```text
DATABASE_URL="postgresql://postgres:yourpassword@db.abc123.supabase.co:5432/postgres?sslmode=require"
```

For Supabase client access (recommended):
```text
SUPABASE_URL="https://your-project-ref.supabase.co"
SUPABASE_KEY="your-supabase-api-key"
```

If you have a Supabase `service_role` key and want the app to create tables remotely
when they are missing, add:

```text
SUPABASE_SERVICE_ROLE="your-service-role-key"
```

### Supabase

If you use Supabase, set `DATABASE_URL` or `SUPABASE_DB_URL` to your Supabase database connection string.
You can find this in the Supabase dashboard under Settings > Database > Connection string.

Example Supabase URL:

```text
postgresql://postgres:yourpassword@db.abc123.supabase.co:5432/postgres?sslmode=require
```

Important:
- If you use `SUPABASE_URL` / `SUPABASE_KEY` only, the Supabase client expects the `ngos` and `interactions` tables to already exist. If they do not yet exist, the app will require `DATABASE_URL` or `SUPABASE_DB_URL` so `init_db()` can create them.
 - If you use `SUPABASE_URL` / `SUPABASE_KEY` only, the Supabase client expects the `ngos` and `interactions` tables to already exist. If they do not yet exist, the app will require `DATABASE_URL` or `SUPABASE_DB_URL` so `init_db()` can create them. Alternatively, if you provide `SUPABASE_SERVICE_ROLE` the app will attempt to create the tables remotely via the Supabase admin endpoints.
- If you provide `DATABASE_URL` or `SUPABASE_DB_URL`, the app can create the tables automatically via `init_db()`.

If you want to run locally, ensure Postgres or Supabase-compatible hosting is reachable with the configured URL.

### StockPad-style helpers

This repository includes a small compatibility layer modeled after `stockpad`:

- `supabase_schema.sql` — SQL DDL you can run in Supabase SQL editor or locally.
- `.streamlit/secrets.toml.example` — example keys file like StockPad's.
- `db_layer.py` — a minimal wrapper with `connect_supabase()`, `init_database()`, `seed()`, and `list_ngos()`.

Use `db_layer.py` for quick scripting or to follow the same patterns used in StockPad.

### Local test helper

A small helper script is provided to initialize the schema, seed sample data, and print a short report.

Run:

```bash
python scripts/local_test.py
```

Notes:
- If you only have `SUPABASE_URL`/`SUPABASE_KEY` configured and the remote tables are missing, the script will instruct you to provide `DATABASE_URL` or `SUPABASE_DB_URL` so it can create the schema.
- If you prefer automatic table creation against Supabase, set `SUPABASE_DB_URL` (the direct Postgres connection string) or `DATABASE_URL` in your `.env`.
