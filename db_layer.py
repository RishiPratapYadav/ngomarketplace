"""Lightweight DB layer wrapper mirroring StockPad's simple patterns.

Usage:
    from db_layer import connect_supabase, init_database, seed, list_ngos

This module delegates to the main `db.py` implementation but provides a
minimal surface similar to StockPad for convenience.
"""
from dotenv import load_dotenv
load_dotenv()
import os
from supabase import create_client

from db import init_db, seed_initial_data, fetch_all_ngos

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase_client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)


def connect_supabase():
    """Return a Supabase client if configured, else None."""
    return supabase_client


def init_database():
    """Create tables (delegates to `db.init_db()`)."""
    return init_db()


def seed():
    """Seed initial sample data (delegates to `db.seed_initial_data()`)."""
    return seed_initial_data()


def list_ngos():
    """Return all NGOs (delegates to `db.fetch_all_ngos()`)."""
    return fetch_all_ngos()
