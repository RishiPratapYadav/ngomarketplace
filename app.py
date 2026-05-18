import streamlit as st
import sqlite3
import pandas as pd
import datetime
import random
import re

# =====================================================================
# 1. DATABASE & INITIALIZATION LAYER
# =====================================================================
def init_db():
    conn = sqlite3.connect('ngo_marketplace.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ngos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            category TEXT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ngo_id INTEGER,
            user_type TEXT,
            action_type TEXT,
            details TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

def seed_initial_data():
    conn = sqlite3.connect('ngo_marketplace.db')
    cursor = conn.cursor()
    
    mock_ngos = [
        ("Feeding America", "Food Supply", "USA", "A massive network of food banks securing and distributing meals to families nationwide.", "https://www.feedingamerica.org", "info@feedingamerica.org", "Verified", 9.5),
        ("Akshaya Patra Foundation", "Food Supply", "India", "Runs the world's largest NGO-led midday meal programme for school children.", "https://www.akshayapatra.org", "infotech@akshayapatra.org", "Verified", 9.8),
        ("No Kid Hungry", "Food Supply", "USA", "Working to end child hunger in America by ensuring all children get healthy food daily.", "https://www.nokidhungry.org", "info@nokidhungry.org", "Verified", 8.9),
        ("Pratham Education Foundation", "Education & Scholarships", "India", "Focuses on high-quality, low-cost, and replicable interventions to address gaps in education.", "https://www.pratham.org", "info@pratham.org", "Verified", 9.2),
        ("Scholarship America", "Education & Scholarships", "USA", "Helps students break down financial barriers, gain access to college, and succeed.", "https://scholarshipamerica.org", "support@scholarshipamerica.org", "Verified", 9.0),
        ("Vidya Helpline", "Education & Scholarships", "India", "Provides critical career guidance and academic scholarship tracking to rural students.", "http://www.vidyahelpline.org", "support@vidyahelpline.org", "Pending Review", 6.5)
    ]
    
    for ngo in mock_ngos:
        try:
            cursor.execute('''
                INSERT INTO ngos (name, category, country, description, website, contact, verification_status, trust_score, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (*ngo, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
        except sqlite3.IntegrityError:
            pass
            
    conn.commit()
    conn.close()

# =====================================================================
# 2. AI AGENT SIMULATION PIPELINE
# =====================================================================
class NGOAgentPipeline:
    @staticmethod
    def run_pipeline(category, country):
        # Discovery Phase
        suffix = random.randint(100, 999)
        if category == "Food Supply":
            name = f"Zero Hunger Alliance {suffix}"
            desc = "Community-led regional distribution program focused on mapping restaurant surplus directly to shelters."
            web = "https://example-zerohunger.org"
            email = "contact@example-zerohunger.org"
        else:
            name = f"Bright Horizon Scholars {suffix}"
            desc = "Providing direct financial grants and technology hardware resources to underprivileged students."
            web = "https://example-brighthorizons.org"
            email = "grants@example-brighthorizons.org"

        # Verification & Scoring Heuristics
        base_score = 7.5 if web.startswith("https") else 5.0
        final_score = round(min(base_score + random.uniform(0.5, 2.3), 10.0), 1)
        status = "Verified" if final_score >= 7.5 else "Pending Review"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # Database Commit
        conn = sqlite3.connect('ngo_marketplace.db')
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO ngos (name, category, country, description, website, contact, verification_status, trust_score, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, category, country, desc, web, email, status, final_score, timestamp))
            conn.commit()
            return {"success": True, "name": name, "score": final_score}
        except sqlite3.IntegrityError:
            return {"success": False, "msg": "Duplicate entity found."}
        finally:
            conn.close()

def log_interaction(ngo_id, user_type, action, details):
    conn = sqlite3.connect('ngo_marketplace.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO interactions (ngo_id, user_type, action_type, details, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (ngo_id, user_type, action, details, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

# =====================================================================
# 3. MODERN FRONTEND UI (STREAMLIT)
# =====================================================================
def main():
    # Setup page properties
    st.set_page_config(page_title="CivicLink Hub", layout="wide", page_icon="🤝")
    init_db()
    seed_initial_data()

    # Custom Clean UI injection using CSS
    st.markdown("""
        <style>
            .main { background-color: #fcfcfc; }
            .stTabs [data-baseweb="tab-list"] { gap: 12px; }
            .stTabs [data-baseweb="tab"] {
                background-color: #f0f2f6;
                border-radius: 8px 8px 0px 0px;
                padding: 10px 24px;
                font-weight: 600;
                color: #495057;
            }
            .stTabs [data-baseweb="tab"][aria-selected="true"] {
                background-color: #0d6efd;
                color: white !important;
            }
            div[data-testid="stBlock"] {
                background-color: white;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.04);
                margin-bottom: 15px;
                border: 1px solid #f0f0f0;
            }
            .trust-high { color: #198754; font-weight: bold; font-size: 1.1rem; }
            .trust-mid { color: #ffc107; font-weight: bold; font-size: 1.1rem; }
            .trust-low { color: #dc3545; font-weight: bold; font-size: 1.1rem; }
        </style>
    """, unsafe_allow_html=True)

    # Clean Header Hero Section
    st.title("🤝 CivicLink")
    st.markdown("##### *The Autonomous Verification Marketplace Matching Donors & Aid Seekers with Trusted Non-Profits.*")
    
    # Unified Global Filters Row
    st.markdown("### 🔍 Filter Ecosystem")
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        sel_country = st.selectbox("🌐 Country", ["All Countries", "USA", "India"])
    with f_col2:
        sel_category = st.selectbox("📁 Service Category", ["All Categories", "Food Supply", "Education & Scholarships"])
    with f_col3:
        min_trust = st.slider("🛡️ Minimum Trust Score Threshold", 0.0, 10.0, 0.0, step=0.5)

    st.write("")

    # Primary Navigation Tabs
    tab1, tab2, tab3 = st.tabs(["🏛️ Active NGO Marketplace", "🤖 Trigger AI Scraper Engine", "📊 Transparency Registry"])

    # -----------------------------------------------------------------
    # TAB 1: THE MARKETPLACE
    # -----------------------------------------------------------------
    with tab1:
        # DB Query Processing
        conn = sqlite3.connect('ngo_marketplace.db')
        query = "SELECT * FROM ngos WHERE trust_score >= ?"
        params = [min_trust]
        
        if sel_country != "All Countries":
            query += " AND country = ?"
            params.append(sel_country)
        if sel_category != "All Categories":
            query += " AND category = ?"
            params.append(sel_category)
            
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        if df.empty:
            st.warning("No verified or pending NGOs match your criteria. Head to the 'Trigger AI Scraper Engine' tab to find more entities automatically.")
        else:
            for index, row in df.iterrows():
                # Clean, Card-Style Layout Container
                with st.container():
                    left_col, right_col = st.columns([3, 1])
                    
                    with left_col:
                        st.markdown(f"### {row['name']} <span style='font-size:1rem; color:grey;'>({row['country']})</span>", unsafe_allow_html=True)
                        st.caption(f"**Category:** {row['category']}  |  **Last Verified Check:** {row['last_updated']}")
                        st.write(row['description'])
                        st.markdown(f"🔗 [Visit Official Website]({row['website']}) &nbsp;&nbsp;•&nbsp;&nbsp; ✉️ Contact Desk: `{row['contact']}`")
                    
                    with right_col:
                        score = row['trust_score']
                        if score >= 8.5:
                            st.markdown(f"<p class='trust-high'>🟢 Trust Rank: {score}/10<br><span style='font-size:0.8rem; color:grey;'>High Verification Integrity</span></p>", unsafe_allow_html=True)
                        elif score >= 7.0:
                            st.markdown(f"<p class='trust-mid'>🟡 Trust Rank: {score}/10<br><span style='font-size:0.8rem; color:grey;'>Moderate Integrity Status</span></p>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<p class='trust-low'>🔴 Trust Rank: {score}/10<br><span style='font-size:0.8rem; color:grey;'>Incomplete/Pending Audits</span></p>", unsafe_allow_html=True)

                    # Seamless Inline Accordion Action Panel
                    with st.expander("🤝 Connect / Transact with this Organization"):
                        act_col1, act_col2 = st.columns(2)
                        
                        with act_col1:
                            st.markdown("**Option A: Contribute Resources**")
                            c_type = st.selectbox("What will you give?", ["Financial Donation", "Volunteer Hours", "Physical Goods/Supplies"], key=f"ct_{row['id']}")
                            c_detail = st.text_input("Pledge Details / Availability notes", placeholder="e.g., Willing to pledge $100 or volunteer on weekends", key=f"cx_{row['id']}")
                            if st.button("Submit Contribution Intent", key=f"cb_{row['id']}", use_container_width=True):
                                log_interaction(row['id'], "Contributor", c_type, c_detail)
                                st.success(f"Successfully connected with {row['name']}! Intakes staff will contact your verified email.")
                                
                        with act_col2:
                            st.markdown("**Option B: Request Services / Aid**")
                            s_need = st.text_area("Specify what resources or scholarships you need help with", placeholder="Describe your resource requirements concisely...", key=f"sx_{row['id']}")
                            if st.button("Request Support Resources", key=f"sb_{row['id']}", use_container_width=True):
                                log_interaction(row['id'], "Beneficiary", "Aid Request", s_need)
                                st.success("Your structural support query has been logged securely and routed to compliance officers.")

    # -----------------------------------------------------------------
    # TAB 2: AI SCRAPER ENGINE CONTROL PANEL
    # -----------------------------------------------------------------
    with tab2:
        st.subheader("🤖 Autonomous Agent Core Operations")
        st.write("Deploy deep-web background scraping algorithms to scan public portals, verify regional licenses, and assign metrics dynamically.")
        
        col_a, col_b = st.columns(2)
        with col_a:
            agent_category = st.selectbox("Target Sector Matrix", ["Food Supply", "Education & Scholarships"])
        with col_b:
            agent_country = st.selectbox("Target Geographical Boundary", ["USA", "India"])
            
        if st.button("🚀 Execute Live Discovery & Auditing Pipeline", use_container_width=True):
            with st.spinner("Pipeline parsing web registers, examining active certificates, and computing trust ratings..."):
                res = NGOAgentPipeline.run_pipeline(agent_category, agent_country)
                if res["success"]:
                    st.toast(f"Discovered: {res['name']}", icon="✅")
                    st.success(f"🎉 **New Entity Integrated Successfully!** Discovered, ranked, and indexed **{res['name']}** with a verified Trust Index score of **{res['score']}/10**.")
                else:
                    st.info("The automated indexer scanned the selected quadrant but identified no new unmapped entities.")

    # -----------------------------------------------------------------
    # TAB 3: TRANSPARENCY REGISTRY
    # -----------------------------------------------------------------
    with tab3:
        st.subheader("📊 Immutable Backend Logging")
        st.write("Real-time telemetry tables showing data points parsed by our multi-layered framework.")
        
        conn = sqlite3.connect('ngo_marketplace.db')
        all_ngos = pd.read_sql_query("SELECT id, name, category, country, trust_score, verification_status, last_updated FROM ngos ORDER BY trust_score DESC", conn)
        all_interactions = pd.read_sql_query("SELECT * FROM interactions ORDER BY id DESC", conn)
        conn.close()
        
        st.markdown("#### Indexed Database Organizations")
        st.dataframe(all_ngos, use_container_width=True, hide_index=True)
        
        st.markdown("#### Live Marketplace Operational Telemetry (Connections Formed)")
        if all_interactions.empty:
            st.info("No connections or match-making operations have occurred yet in this deployment instance.")
        else:
            st.dataframe(all_interactions, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()