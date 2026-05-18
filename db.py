import os
import datetime
import psycopg2

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("SUPABASE_DB_URL", "postgresql://postgres:postgres@localhost:5432/ngomarketplace")
)


def get_connection():
    # Supabase provides a standard PostgreSQL URL that works with psycopg2.
    # If using Supabase, set DATABASE_URL or SUPABASE_DB_URL in your environment.
    return psycopg2.connect(DATABASE_URL)


def init_db():
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
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            mock_ngos = [
                ("Feeding America", "Food Supply", "Meals Distribution", "USA", "A massive network of food banks securing and distributing meals to families nationwide.", "https://www.feedingamerica.org", "info@feedingamerica.org", "Verified", 9.5),
                ("Akshaya Patra Foundation", "Food Supply", "Nutrition Programs", "India", "Runs the world's largest NGO-led midday meal programme for school children.", "https://www.akshayapatra.org", "infotech@akshayapatra.org", "Verified", 9.8),
                ("No Kid Hungry", "Food Supply", "Food Security", "USA", "Working to end child hunger in America by ensuring all children get healthy food daily.", "https://www.nokidhungry.org", "info@nokidhungry.org", "Verified", 8.9),
                ("Pratham Education Foundation", "Education & Scholarships", "Learning Centers", "India", "Focuses on high-quality, low-cost, and replicable interventions to address gaps in education.", "https://www.pratham.org", "info@pratham.org", "Verified", 9.2),
                ("Scholarship America", "Education & Scholarships", "Scholarships", "USA", "Helps students break down financial barriers, gain access to college, and succeed.", "https://scholarshipamerica.org", "support@scholarshipamerica.org", "Verified", 9.0),
                ("Vidya Helpline", "Education & Scholarships", "Career Guidance", "India", "Provides critical career guidance and academic scholarship tracking to rural students.", "http://www.vidyahelpline.org", "support@vidyahelpline.org", "Pending Review", 6.5),
                ("MedicAid Collective", "Medical Support & Health", "Mobile Clinics", "India", "Deploys mobile clinics to underserved communities and delivers preventive health services.", "https://www.medicaidcollective.org", "contact@medicaidcollective.org", "Verified", 9.1),
                ("Warm Threads", "Clothing & Shelter", "Clothing Drives", "USA", "Organizes clothing donation events and shelter kit distribution for families in need.", "https://www.warmthreads.org", "help@warmthreads.org", "Verified", 8.6),
                ("Green Earth Initiative", "Environment & Tree Planting", "Reforestation", "India", "Plants urban trees and restores degraded land through community-led greening programs.", "https://www.greenearthinitiative.org", "info@greenearthinitiative.org", "Verified", 8.3),
                ("Temple Trust Network", "Community & Culture", "Temple Support", "India", "Supports temple restoration, community outreach, and local welfare programs.", "https://www.templetrustnetwork.org", "support@templetrustnetwork.org", "Pending Review", 7.2)
            ]
            for ngo in mock_ngos:
                cursor.execute('''
                    INSERT INTO ngos (name, category, subcategory, country, description, website, contact, verification_status, trust_score, last_updated)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (name) DO NOTHING
                ''', (*ngo, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.close()


def log_interaction(ngo_id, user_type, action_type, details):
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO interactions (ngo_id, user_type, action_type, details, timestamp)
                VALUES (%s, %s, %s, %s, %s)
            ''', (ngo_id, user_type, action_type, details, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.close()
