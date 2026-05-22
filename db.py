import os
import datetime
import random
import hashlib
import requests
from dotenv import load_dotenv
from supabase import create_client

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
        if "Could not find the table" in message or "PGRST205" in message or "PGRST204" in message:
            return response # Let caller handle missing table
        raise RuntimeError(f"Supabase error: {message}")
    return response


def hash_password(password):
    """Simple SHA256 hashing for the PostgreSQL fallback. 
    In production, use bcrypt or Supabase Auth.
    """
    return hashlib.sha256(password.encode()).hexdigest()


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
            registration_id TEXT UNIQUE,
            description TEXT,
            website TEXT,
            contact TEXT,
            verification_status TEXT,
            trust_score REAL,
            last_updated TEXT
        );

        -- Migration: Ensure registration_id exists if table was created earlier
        ALTER TABLE ngos ADD COLUMN IF NOT EXISTS registration_id TEXT UNIQUE;

        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT,
            provider TEXT DEFAULT 'email',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Migration: Add ngo_id to users to support NGO persona
        ALTER TABLE users ADD COLUMN IF NOT EXISTS ngo_id INTEGER REFERENCES ngos(id);

        CREATE TABLE IF NOT EXISTS interactions (
            id SERIAL PRIMARY KEY,
            ngo_id INTEGER REFERENCES ngos(id),
            user_type TEXT,
            action_type TEXT,
            details TEXT,
            timestamp TEXT
        );

        CREATE TABLE IF NOT EXISTS requests (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            ngo_id INTEGER REFERENCES ngos(id),
            category TEXT,
            details TEXT,
            status TEXT DEFAULT 'Pending',
            timestamp TEXT
        );
    '''
    _attempt_supabase_sql(ddl)


def _ensure_supabase_tables():
    if not is_supabase_enabled():
        return
    
    tables_to_check = ["ngos", "users", "interactions", "requests"]
    missing_table = False
    
    for table in tables_to_check:
        try:
            # Check if table exists
            supabase.from_(table).select("id").limit(1).execute()
        except Exception as e:
            missing_table = True
            break
            
    if missing_table:
            if SUPABASE_SERVICE_ROLE:
                try:
                    _create_tables_via_service_role()
                    return
                except Exception:
                    pass # Fall back to letting the app run with empty data
            print("Note: Supabase tables missing. Setup DATABASE_URL or SUPABASE_SERVICE_ROLE to auto-create.")


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
                        registration_id TEXT UNIQUE,
                        description TEXT,
                        website TEXT,
                        contact TEXT,
                        verification_status TEXT,
                        trust_score REAL,
                        last_updated TEXT
                    )
                ''')
                # Migration for existing tables
                cursor.execute("ALTER TABLE ngos ADD COLUMN IF NOT EXISTS registration_id TEXT UNIQUE")
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        password TEXT,
                        provider TEXT DEFAULT 'email',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS requests (
                        id SERIAL PRIMARY KEY,
                        user_email TEXT,
                        ngo_id INTEGER REFERENCES ngos(id),
                        category TEXT,
                        details TEXT,
                        status TEXT DEFAULT 'Pending',
                        timestamp TEXT
                    )
                ''')
        conn.close()
        return
    if is_supabase_enabled():
        _ensure_supabase_tables()
        return


def register_user(email, password, provider='email'):
    """Register a new user via Supabase Auth or PostgreSQL."""
    if is_supabase_enabled() and provider == 'email':
        try:
            res = supabase.auth.sign_up({"email": email, "password": password})
            # Ensure metadata record exists in public.users for NGO linking
            try:
                supabase.from_("users").upsert({"email": email, "provider": provider}).execute()
            except:
                pass
            return {"success": True, "user": res.user}
        except Exception as e:
            return {"success": False, "msg": str(e)}

    if is_supabase_enabled():
        try:
            hashed = hash_password(password) if password else None
            supabase.from_("users").insert({
                "email": email,
                "password": hashed,
                "provider": provider
            }).execute()
            return {"success": True, "email": email}
        except Exception as e:
            if "unique constraint" in str(e).lower():
                return {"success": False, "msg": "Email already registered."}
            if not use_direct_db():
                return {"success": False, "msg": str(e)}

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cursor:
                hashed = hash_password(password) if password else None
                cursor.execute(
                    "INSERT INTO users (email, password, provider) VALUES (%s, %s, %s) RETURNING id",
                    (email, hashed, provider)
                )
                return {"success": True, "email": email}
    except Exception as e:
        if "unique constraint" in str(e).lower():
            return {"success": False, "msg": "Email already registered."}
        return {"success": False, "msg": str(e)}
    finally:
        conn.close()


def authenticate_user(email, password):
    """Authenticate user via Supabase Auth or PostgreSQL."""
    if is_supabase_enabled():
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if res.user:
                # Fetch additional info from our public.users table
                response = supabase.from_("users").select("*").eq("email", email).execute()
                if response.data:
                    return {"success": True, "user": response.data[0]}
                return {"success": True, "user": {"email": email}}
        except Exception as e:
            # Fallback check for manual DB users if Supabase Auth fails
            try:
                hashed = hash_password(password)
                response = supabase.from_("users").select("*").eq("email", email).eq("password", hashed).eq("provider", "email").execute()
                if response.data:
                    return {"success": True, "user": response.data[0]}
            except:
                pass
        if not use_direct_db():
            return {"success": False, "msg": "Invalid email or password."}

    if not use_direct_db():
        return {"success": False, "msg": "Authentication failed; database not configured."}

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, email, password, ngo_id FROM users WHERE email = %s AND provider = 'email'", (email,))
                row = cursor.fetchone()
                if row and row[2] == hash_password(password):
                    return {"success": True, "user": {"id": row[0], "email": row[1], "ngo_id": row[3]}}
                return {"success": False, "msg": "Invalid email or password."}
    except Exception as e:
        return {"success": False, "msg": str(e)}
    finally:
        conn.close()


def login_with_google_simulated(email):
    """Simulate or handle Google Login entry in the DB."""
    if is_supabase_enabled():
        try:
            res = supabase.from_("users").select("*").eq("email", email).execute()
            if not res.data:
                ins_res = supabase.from_("users").insert({"email": email, "provider": "google"}).execute()
                return {"success": True, "user": ins_res.data[0] if ins_res.data else {"email": email}}
            return {"success": True, "user": res.data[0]}
        except Exception as e:
            if not use_direct_db():
                return {"success": False, "msg": str(e)}

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, email, ngo_id FROM users WHERE email = %s", (email,))
                row = cursor.fetchone()
                if not row:
                    cursor.execute(
                        "INSERT INTO users (email, provider) VALUES (%s, %s) RETURNING id, email, ngo_id",
                        (email, 'google')
                    )
                    row = cursor.fetchone()
                return {"success": True, "user": {"id": row[0], "email": row[1], "ngo_id": row[2]}}
    except Exception as e:
        return {"success": False, "msg": str(e)}
    finally:
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
            if "disconnected" in msg:
                print("Seeding skipped: Server disconnected. Check Supabase connection.")
                return
            if "could not find the table" in msg or "pgrst205" in msg or "pgrst204" in msg:
                return
            # Suppress duplicate key errors to prevent console noise during frequent reruns
            if "23505" in msg or "duplicate key" in msg:
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
        "registration_id": f"REG-{random.randint(10000, 99999)}",
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
                INSERT INTO ngos (name, category, subcategory, country, registration_id, description, website, contact, verification_status, trust_score, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (name, category, subcategory, country, payload["registration_id"], description, website, contact, verification_status, trust_score, last_updated))
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
            # Standard Postgres error code for unique violation is 23505
            code = getattr(e, "code", None)
            if code == "23505" or "duplicate key" in msg or "23505" in msg:
                return {"success": False, "msg": "Duplicate entity found."}
            if "could not find the table" in msg or "pgrst205" in msg or "pgrst204" in msg or "registration_id" in msg:
                # Attempt migration if service role is available
                if SUPABASE_SERVICE_ROLE:
                    try:
                        _create_tables_via_service_role()
                    except:
                        pass
                raise RuntimeError(
                    "Supabase client is configured, but required tables or columns are missing. "
                    "Set DATABASE_URL or SUPABASE_DB_URL and run init_db(), or create the tables in Supabase."
                )
            raise

    return {"success": False, "msg": "Database configuration missing."}


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
            if "Could not find the table" in message or "PGRST205" in message or "PGRST204" in message:
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


def submit_request(user_email, category, details, ngo_id=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = {
        "user_email": user_email,
        "category": category,
        "details": details,
        "ngo_id": ngo_id,
        "status": "Pending",
        "timestamp": timestamp
    }
    
    if use_direct_db():
        conn = get_connection()
        with conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO requests (user_email, category, details, ngo_id, status, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (user_email, category, details, ngo_id, "Pending", timestamp))
        conn.close()
        return {"success": True}

    if is_supabase_enabled():
        try:
            supabase.from_("requests").insert(payload).execute()
            return {"success": True}
        except Exception as e:
            return {"success": False, "msg": str(e)}
            
    return {"success": False, "msg": "DB not configured"}


def fetch_ngo_requests(ngo_id):
    if is_supabase_enabled():
        try:
            response = supabase.from_("requests").select("*").eq("ngo_id", ngo_id).order("id", desc=True).execute()
            return response.data or []
        except Exception as e:
            return []

    if not use_direct_db():
        return []

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM requests WHERE ngo_id = %s ORDER BY id DESC", (ngo_id,))
            cols = [desc[0] for desc in cursor.description]
            return [dict(zip(cols, record)) for record in cursor.fetchall()]
    finally:
        conn.close()


def update_request_status(request_id, status):
    if use_direct_db():
        conn = get_connection()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE requests SET status = %s WHERE id = %s", (status, request_id))
            return {"success": True}
        except Exception as e:
            return {"success": False, "msg": str(e)}
        finally:
            conn.close()

    if is_supabase_enabled():
        try:
            supabase.from_("requests").update({"status": status}).eq("id", request_id).execute()
            return {"success": True}
        except Exception as e:
            return {"success": False, "msg": str(e)}
            
    return {"success": False, "msg": "DB not configured"}


def fetch_user_requests(email):
    if is_supabase_enabled():
        try:
            # Join logic simplified: fetch and then map NGO names if needed
            response = supabase.from_("requests").select("*").eq("user_email", email).order("id", desc=True).execute()
            return response.data or []
        except Exception as e:
            return []

    if not use_direct_db():
        return []

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT r.*, n.name as ngo_name 
                FROM requests r LEFT JOIN ngos n ON r.ngo_id = n.id 
                WHERE r.user_email = %s ORDER BY r.id DESC
            """, (email,))
            cols = [desc[0] for desc in cursor.description]
            return [dict(zip(cols, record)) for record in cursor.fetchall()]
    finally:
        conn.close()


def fetch_ngos(category=None, subcategory=None, country=None, search=None, min_trust=0.0):
    rows = []
    if is_supabase_enabled():
        try:  
            response =supabase.table("ngos").select("*").execute()
            rows = response.data or []
        except Exception as e:
            message = str(e)
            if "Could not find the table" in message or "PGRST205" in message or "PGRST204" in message:
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
            if "Could not find the table" in message or "PGRST205" in message or "PGRST204" in message:
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
            if "Could not find the table" in message or "PGRST205" in message or "PGRST204" in message:
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
