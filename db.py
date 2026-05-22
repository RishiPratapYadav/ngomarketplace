import os
import datetime
from dotenv import load_dotenv
from supabase import create_client
import requests

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    import psycopg2
except ImportError:
    psycopg2 = None


def is_supabase_enabled():
    return supabase is not None


def has_direct_db_url():
    return bool(DATABASE_URL or SUPABASE_DB_URL)


def use_direct_db():
    return psycopg2 is not None and has_direct_db_url()


def get_connection():
    if not use_direct_db():
        if is_supabase_enabled():
            raise RuntimeError("Supabase client is enabled; direct DB connection is not used.")
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is not installed for direct database access.")
        raise RuntimeError("DATABASE_URL or SUPABASE_DB_URL must be set for direct DB access.")
    return psycopg2.connect(DATABASE_URL or SUPABASE_DB_URL)


def _apply_filters(rows, category=None, subcategory=None, country=None, search=None, min_trust=None):
    items = rows or []
    if country and country != "All Countries":
        items = [row for row in items if row.get("country") == country]
    if category and category != "All Categories":
        items = [row for row in items if row.get("category") == category]
    if subcategory and subcategory != "All Subcategories":
        items = [row for row in items if row.get("subcategory") == subcategory]
    if min_trust is not None:
        items = [row for row in items if float(row.get("trust_score", 0)) >= float(min_trust)]
    if search:
        search_lower = search.lower()
        def matches(row):
            return any(
                search_lower in str(row.get(field, "")).lower()
                for field in ["name", "description", "category", "subcategory", "country"]
            )
        items = [row for row in items if matches(row)]
    return items


def _handle_supabase_response(response, table_name=None):
    """Safely handle Supabase response objects across library versions."""
    # Recent supabase-py versions return data directly or raise exceptions.
    # Older versions return an object with an .error attribute.
    if hasattr(response, 'error') and response.error:
        message = str(response.error.get('message', response.error))
        if "Could not find the table" in message or "PGRST205" in message:
            return response # Let caller handle missing table
        raise RuntimeError(f"Supabase error: {message}")
    return response


def _attempt_supabase_sql(sql):
    """Try executing raw SQL using the Supabase project endpoints with a service_role key.

    This attempts a few known admin-like endpoints and payload shapes. If none
    succeed, an exception is raised.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE:
        raise RuntimeError("Supabase service role key not configured.")

    endpoints = [
        ("admin/v1/query", "sql"),
        ("rest/v1/rpc/run_sql", "sql"),
        ("rest/v1/rpc/sql", "sql"),
        ("rest/v1/rpc/exec", "sql"),
    ]

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE}",
        "Content-Type": "application/json",
    }

    last_error = None
    for path, key in endpoints:
        url = f"{SUPABASE_URL.rstrip('/')}/{path}"
        payload = {key: sql}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code in (200, 201, 204):
                return resp
            # Some endpoints return JSON with an error message
            try:
                body = resp.json()
                if isinstance(body, dict) and ("error" in body or "message" in body):
                    last_error = Exception(f"{url} -> {body}")
                else:
                    # non-error JSON, accept it
                    return resp
            except Exception:
                last_error = Exception(f"{url} returned status {resp.status_code}")
        except Exception as e:
            last_error = e

    raise RuntimeError("Could not execute SQL via Supabase admin endpoints") from last_error


def _create_tables_via_service_role():
    ddl = '''
        CREATE TABLE IF NOT EXISTS ngos (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE,
            category TEXT,
            subcategory TEXT,
            country TEXT,
            description TEXT,
            website TEXT,
            contact TEXT,
            verification_status TEXT,
            trust_score REAL,
            last_updated TEXT
        );

        CREATE TABLE IF NOT EXISTS interactions (
            id SERIAL PRIMARY KEY,
            ngo_id INTEGER REFERENCES ngos(id),
            user_type TEXT,
            action_type TEXT,
            details TEXT,
            timestamp TEXT
        );
    '''
    _attempt_supabase_sql(ddl)


def _ensure_supabase_tables():
    if not is_supabase_enabled():
        return
    try:
        # Just a check to see if the table exists
        supabase.from_("ngos").select("id").limit(1).execute()
    except Exception as e:
        msg = str(e).lower()
        if "could not find the table" in msg or "pgrst205" in msg:
            if SUPABASE_SERVICE_ROLE:
                try:
                    _create_tables_via_service_role()
                    return
                except Exception:
                    pass # Fall back to letting the app run with empty data
            print("Note: Supabase tables missing. Setup DATABASE_URL or SUPABASE_SERVICE_ROLE to auto-create.")
        raise


def _supabase_execute(query):
    if not is_supabase_enabled():
        raise RuntimeError("Supabase is not configured.")
    return query.execute()


def init_db():
    if use_direct_db():
        conn = get_connection()
        with conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ngos (
                        id SERIAL PRIMARY KEY,
                        name TEXT UNIQUE,
                        category TEXT,
                        subcategory TEXT,
                        country TEXT,
                        description TEXT,
                        website TEXT,
                        contact TEXT,
                        verification_status TEXT,
                        trust_score REAL,
                        last_updated TEXT
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS interactions (
                        id SERIAL PRIMARY KEY,
                        ngo_id INTEGER REFERENCES ngos(id),
                        user_type TEXT,
                        action_type TEXT,
                        details TEXT,
                        timestamp TEXT
                    )
                ''')
        conn.close()
        return
    if is_supabase_enabled():
        _ensure_supabase_tables()
        return
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ngos (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE,
                    category TEXT,
                    subcategory TEXT,
                    country TEXT,
                    description TEXT,
                    website TEXT,
                    contact TEXT,
                    verification_status TEXT,
                    trust_score REAL,
                    last_updated TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id SERIAL PRIMARY KEY,
                    ngo_id INTEGER REFERENCES ngos(id),
                    user_type TEXT,
                    action_type TEXT,
                    details TEXT,
                    timestamp TEXT
                )
            ''')
    conn.close()


def seed_initial_data():
    initial_data = [
        {
            "name": "Feeding America",
            "category": "Food Supply",
            "subcategory": "Meals Distribution",
            "country": "USA",
            "description": "A massive network of food banks securing and distributing meals to families nationwide.",
            "website": "https://www.feedingamerica.org",
            "contact": "info@feedingamerica.org",
            "verification_status": "Verified",
            "trust_score": 9.5,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        },
        {
            "name": "Akshaya Patra Foundation",
            "category": "Food Supply",
            "subcategory": "Nutrition Programs",
            "country": "India",
            "description": "Runs the world's largest NGO-led midday meal programme for school children.",
            "website": "https://www.akshayapatra.org",
            "contact": "infotech@akshayapatra.org",
            "verification_status": "Verified",
            "trust_score": 9.8,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        },
        {
            "name": "No Kid Hungry",
            "category": "Food Supply",
            "subcategory": "Food Security",
            "country": "USA",
            "description": "Working to end child hunger in America by ensuring all children get healthy food daily.",
            "website": "https://www.nokidhungry.org",
            "contact": "info@nokidhungry.org",
            "verification_status": "Verified",
            "trust_score": 8.9,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        },
        {
            "name": "Pratham Education Foundation",
            "category": "Education & Scholarships",
            "subcategory": "Learning Centers",
            "country": "India",
            "description": "Focuses on high-quality, low-cost, and replicable interventions to address gaps in education.",
            "website": "https://www.pratham.org",
            "contact": "info@pratham.org",
            "verification_status": "Verified",
            "trust_score": 9.2,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        },
        {
            "name": "Scholarship America",
            "category": "Education & Scholarships",
            "subcategory": "Scholarships",
            "country": "USA",
            "description": "Helps students break down financial barriers, gain access to college, and succeed.",
            "website": "https://scholarshipamerica.org",
            "contact": "support@scholarshipamerica.org",
            "verification_status": "Verified",
            "trust_score": 9.0,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        },
        {
            "name": "Vidya Helpline",
            "category": "Education & Scholarships",
            "subcategory": "Career Guidance",
            "country": "India",
            "description": "Provides critical career guidance and academic scholarship tracking to rural students.",
            "website": "http://www.vidyahelpline.org",
            "contact": "support@vidyahelpline.org",
            "verification_status": "Pending Review",
            "trust_score": 6.5,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        },
        {
            "name": "MedicAid Collective",
            "category": "Medical Support & Health",
            "subcategory": "Mobile Clinics",
            "country": "India",
            "description": "Deploys mobile clinics to underserved communities and delivers preventive health services.",
            "website": "https://www.medicaidcollective.org",
            "contact": "contact@medicaidcollective.org",
            "verification_status": "Verified",
            "trust_score": 9.1,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        },
        {
            "name": "Warm Threads",
            "category": "Clothing & Shelter",
            "subcategory": "Clothing Drives",
            "country": "USA",
            "description": "Organizes clothing donation events and shelter kit distribution for families in need.",
            "website": "https://www.warmthreads.org",
            "contact": "help@warmthreads.org",
            "verification_status": "Verified",
            "trust_score": 8.6,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        },
        {
            "name": "Green Earth Initiative",
            "category": "Environment & Tree Planting",
            "subcategory": "Reforestation",
            "country": "India",
            "description": "Plants urban trees and restores degraded land through community-led greening programs.",
            "website": "https://www.greenearthinitiative.org",
            "contact": "info@greenearthinitiative.org",
            "verification_status": "Verified",
            "trust_score": 8.3,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        },
        {
            "name": "Temple Trust Network",
            "category": "Community & Culture",
            "subcategory": "Temple Support",
            "country": "India",
            "description": "Supports temple restoration, community outreach, and local welfare programs.",
            "website": "https://www.templetrustnetwork.org",
            "contact": "support@templetrustnetwork.org",
            "verification_status": "Pending Review",
            "trust_score": 7.2,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    ]

    if use_direct_db():
        conn = get_connection()
        with conn:
            with conn.cursor() as cursor:
                for ngo in initial_data:
                    cursor.execute('''
                        INSERT INTO ngos (name, category, subcategory, country, description, website, contact, verification_status, trust_score, last_updated)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (name) DO NOTHING
                    ''', (
                        ngo["name"], ngo["category"], ngo["subcategory"], ngo["country"], ngo["description"],
                        ngo["website"], ngo["contact"], ngo["verification_status"], ngo["trust_score"], ngo["last_updated"]
                    ))
        conn.close()
        return

    if is_supabase_enabled():
        try:
            supabase.from_("ngos").upsert(initial_data).execute()
        except Exception as e:
            msg = str(e).lower()
            if "could not find the table" in msg or "pgrst205" in msg:
                return
            print(f"Seeding skipped or failed: {e}")
        return

    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            for ngo in initial_data:
                cursor.execute('''
                    INSERT INTO ngos (name, category, subcategory, country, description, website, contact, verification_status, trust_score, last_updated)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (name) DO NOTHING
                ''', (
                    ngo["name"], ngo["category"], ngo["subcategory"], ngo["country"], ngo["description"],
                    ngo["website"], ngo["contact"], ngo["verification_status"], ngo["trust_score"], ngo["last_updated"]
                ))
    conn.close()


def insert_ngo(name, category, subcategory, country, description, website, contact, verification_status, trust_score, last_updated):
    payload = {
        "name": name,
        "category": category,
        "subcategory": subcategory,
        "country": country,
        "description": description,
        "website": website,
        "contact": contact,
        "verification_status": verification_status,
        "trust_score": trust_score,
        "last_updated": last_updated
    }
    if use_direct_db():
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO ngos (name, category, subcategory, country, description, website, contact, verification_status, trust_score, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (name, category, subcategory, country, description, website, contact, verification_status, trust_score, last_updated))
            conn.commit()
            return {"success": True, "name": name, "score": trust_score, "subcategory": subcategory}
        except psycopg2.IntegrityError:
            return {"success": False, "msg": "Duplicate entity found."}
        finally:
            conn.close()

    if is_supabase_enabled():
        try:
            response = supabase.from_("ngos").insert(payload).execute()
            return {"success": True, "name": name, "score": trust_score, "subcategory": subcategory}
        except Exception as e:
            msg = str(e).lower()
            if "duplicate key" in msg:
                return {"success": False, "msg": "Duplicate entity found."}
            if "could not find the table" in msg or "pgrst205" in msg:
                raise RuntimeError(
                    "Supabase client is configured, but required tables are missing. "
                    "Set DATABASE_URL or SUPABASE_DB_URL and run init_db(), or create the tables in Supabase."
                )
            raise

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO ngos (name, category, subcategory, country, description, website, contact, verification_status, trust_score, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (name, category, subcategory, country, description, website, contact, verification_status, trust_score, last_updated))
        conn.commit()
        return {"success": True, "name": name, "score": trust_score, "subcategory": subcategory}
    except psycopg2.IntegrityError:
        return {"success": False, "msg": "Duplicate entity found."}
    finally:
        conn.close()


def log_interaction(ngo_id, user_type, action_type, details):
    if use_direct_db():
        conn = get_connection()
        with conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO interactions (ngo_id, user_type, action_type, details, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (ngo_id, user_type, action_type, details, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.close()
        return

    if is_supabase_enabled():
        try:
            supabase.from_("interactions").insert({
                "ngo_id": ngo_id,
                "user_type": user_type,
                "action_type": action_type,
                "details": details,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            }).execute()
            return
        except Exception as e:
            message = str(e)
            if "Could not find the table" in message or "PGRST205" in message:
                return
            raise

    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO interactions (ngo_id, user_type, action_type, details, timestamp)
                VALUES (%s, %s, %s, %s, %s)
            ''', (ngo_id, user_type, action_type, details, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.close()


def fetch_ngos(category=None, subcategory=None, country=None, search=None, min_trust=0.0):
    rows = []
    if is_supabase_enabled():
        try:  
            response =supabase.table("ngos").select("*").execute()
            rows = response.data or []
        except Exception as e:
            message = str(e)
            if "Could not find the table" in message or "PGRST205" in message:
                rows = []
            else:
                raise RuntimeError(f"Supabase fetch error: {message}")
    else:
        conn = get_connection()
        query = "SELECT * FROM ngos WHERE trust_score >= %s"
        params = [min_trust]
        if category and category != "All Categories":
            query += " AND category = %s"
            params.append(category)
        if subcategory and subcategory != "All Subcategories":
            query += " AND subcategory = %s"
            params.append(subcategory)
        if country and country != "All Countries":
            query += " AND country = %s"
            params.append(country)
        if search:
            query += " AND (name ILIKE %s OR description ILIKE %s OR category ILIKE %s OR subcategory ILIKE %s OR country ILIKE %s)"
            qterm = f"%{search}%"
            params.extend([qterm] * 5)
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                cols = [desc[0] for desc in cursor.description]
                for record in cursor.fetchall():
                    rows.append(dict(zip(cols, record)))
        finally:
            conn.close()
    return _apply_filters(rows, category=category, subcategory=subcategory, country=country, search=search, min_trust=min_trust)


def fetch_all_ngos():
    if is_supabase_enabled():
        try:
            response =supabase.table("ngos").select("*").execute() #response = supabase.from_("ngos").select("*").execute()
            return response.data or []
        except Exception as e:
            message = str(e)
            if "Could not find the table" in message or "PGRST205" in message:
                return []
            raise RuntimeError(f"Supabase fetch error: {message}")

    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name, category, subcategory, country, trust_score, verification_status, last_updated FROM ngos ORDER BY trust_score DESC")
        cols = [desc[0] for desc in cursor.description]
        rows = [dict(zip(cols, record)) for record in cursor.fetchall()]
    conn.close()
    return rows


def fetch_all_interactions():
    if is_supabase_enabled():
        try:
            response = supabase.from_("interactions").select("*").order("id", desc=True).execute()
            return response.data or []
        except Exception as e:
            message = str(e)
            if "Could not find the table" in message or "PGRST205" in message:
                return []
            raise RuntimeError(f"Supabase fetch error: {message}")

    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM interactions ORDER BY id DESC")
        cols = [desc[0] for desc in cursor.description]
        rows = [dict(zip(cols, record)) for record in cursor.fetchall()]
    conn.close()
    return rows


def fetch_metrics():
    rows = fetch_all_ngos()
    total = len(rows)
    verified = sum(1 for row in rows if row.get("verification_status") == "Verified")
    countries = len({row.get("country") for row in rows})
    return {"total": total, "verified": verified, "countries": countries}
