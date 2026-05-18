# ngomarketplace

## Database

This app now uses PostgreSQL instead of SQLite.

- Install dependencies: `pip install -r requirements.txt`
- Provide a PostgreSQL connection URL with `DATABASE_URL`
- Example: `postgresql://postgres:postgres@localhost:5432/ngomarketplace`
- Or create a `.env` file in the project root with the connection string

### .env support

Create a `.env` file with:

```text
DATABASE_URL="postgresql://postgres:yourpassword@db.abc123.supabase.co:5432/postgres?sslmode=require"
```

### Supabase

If you use Supabase, set `DATABASE_URL` or `SUPABASE_DB_URL` to your Supabase database connection string.
You can find this in the Supabase dashboard under Settings > Database > Connection string.

Example Supabase URL:

```text
postgresql://postgres:yourpassword@db.abc123.supabase.co:5432/postgres?sslmode=require
```

If you want to run locally, ensure Postgres or Supabase-compatible hosting is reachable with the configured URL.
