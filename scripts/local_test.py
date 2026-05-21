#!/usr/bin/env python3
"""Local test helper: initialize DB, seed data, and print a short report.

Usage:
  python scripts/local_test.py

This script will:
- load environment variables from .env
- run `init_db()` (creates tables when DATABASE_URL or SUPABASE_DB_URL is set)
- run `seed_initial_data()` to populate sample NGOs
- print a short summary from `fetch_all_ngos()`

If you only have `SUPABASE_URL`/`SUPABASE_KEY` configured and the remote tables
are missing, the script will surface that error and print guidance on next steps.
"""

import os
from dotenv import load_dotenv
load_dotenv()

from db import init_db, seed_initial_data, fetch_all_ngos


def main():
    env = {
        "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
        "SUPABASE_DB_URL": bool(os.getenv("SUPABASE_DB_URL")),
        "SUPABASE_URL": bool(os.getenv("SUPABASE_URL")),
        "SUPABASE_KEY": bool(os.getenv("SUPABASE_KEY")),
    }
    print("Environment:", env)

    try:
        init_db()
        print("init_db: OK")
    except Exception as e:
        print("init_db: ERROR ->", e)
        # If tables are missing on Supabase-only setups, provide actionable guidance
        msg = str(e).lower()
        if "required tables are missing" in msg or "supabase client is configured" in msg:
            print("")
            print("To allow automatic table creation, provide a direct DB URL:")
            print("  - set DATABASE_URL or SUPABASE_DB_URL to your project's connection string")
            print("  - then rerun this script to create tables and seed data")
            print("")
            return

    try:
        seed_initial_data()
        print("seed_initial_data: OK")
    except Exception as e:
        print("seed_initial_data: ERROR ->", e)

    try:
        ngos = fetch_all_ngos()
        print(f"fetch_all_ngos: returned {len(ngos)} rows")
        for ngo in ngos[:5]:
            print(" -", ngo.get("name"))
    except Exception as e:
        print("fetch_all_ngos: ERROR ->", e)


if __name__ == "__main__":
    main()
