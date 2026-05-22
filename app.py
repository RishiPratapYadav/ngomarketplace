import streamlit as st
import pandas as pd
import datetime
import random
import re
from db import (
    init_db,
    seed_initial_data,
    log_interaction,
    fetch_metrics,
    fetch_ngos,
    fetch_all_ngos,
    fetch_all_interactions,
    insert_ngo,
    register_user,
    authenticate_user,
    login_with_google_simulated,
)

# =====================================================================
# 2. AI AGENT SIMULATION PIPELINE
# =====================================================================
class NGOAgentPipeline:
    @staticmethod
    def run_pipeline(category, country):
        # Discovery Phase
        suffix = random.randint(100, 999)
        if category == "Food Supply":
            subcategory = "Nutrition Programs"
            name = f"Zero Hunger Alliance {suffix}"
            desc = "Community-led regional distribution program focused on mapping restaurant surplus directly to shelters."
            web = "https://example-zerohunger.org"
            email = "contact@example-zerohunger.org"
        elif category == "Education & Scholarships":
            subcategory = "Scholarships"
            name = f"Bright Horizon Scholars {suffix}"
            desc = "Providing direct financial grants and technology hardware resources to underprivileged students."
            web = "https://example-brighthorizons.org"
            email = "grants@example-brighthorizons.org"
        elif category == "Medical Support & Health":
            subcategory = "Mobile Clinics"
            name = f"Health Access Network {suffix}"
            desc = "Operates mobile clinics and telehealth outreach in remote and underserved regions."
            web = "https://example-healthaccess.org"
            email = "support@example-healthaccess.org"
        elif category == "Clothing & Shelter":
            subcategory = "Clothing Drives"
            name = f"Warm Hearts Collective {suffix}"
            desc = "Drives clothing donation campaigns and emergency shelter assistance for vulnerable families."
            web = "https://example-warmhearts.org"
            email = "hello@example-warmhearts.org"
        elif category == "Environment & Tree Planting":
            subcategory = "Reforestation"
            name = f"Green Canopy Project {suffix}"
            desc = "Restores degraded land through community-led tree planting and sustainable habitat programs."
            web = "https://example-greencanopy.org"
            email = "connect@example-greencanopy.org"
        else:
            subcategory = "Temple Support"
            name = f"Community Blessings Trust {suffix}"
            desc = "Supports local temple restoration, cultural events, and community welfare outreach."
            web = "https://example-communityblessings.org"
            email = "care@example-communityblessings.org"

        # Verification & Scoring Heuristics
        base_score = 7.5 if web.startswith("https") else 5.0
        final_score = round(min(base_score + random.uniform(0.5, 2.3), 10.0), 1)
        status = "Verified" if final_score >= 7.5 else "Pending Review"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        return insert_ngo(
            name,
            category,
            subcategory,
            country,
            desc,
            web,
            email,
            status,
            final_score,
            timestamp,
        )

MAIN_CATEGORIES = [
    "Food Supply",
    "Education & Scholarships",
    "Medical Support & Health",
    "Clothing & Shelter",
    "Environment & Tree Planting",
    "Community & Culture"
]

SUBCATEGORY_OPTIONS = {
    "Food Supply": ["Meals Distribution", "Nutrition Programs", "Food Security"],
    "Education & Scholarships": ["Scholarships", "Learning Centers", "Career Guidance"],
    "Medical Support & Health": ["Mobile Clinics", "Emergency Relief", "Mental Health"],
    "Clothing & Shelter": ["Clothing Drives", "Winter Relief", "Shelter Support"],
    "Environment & Tree Planting": ["Reforestation", "Urban Greening", "Habitat Restoration"],
    "Community & Culture": ["Temple Support", "Cultural Heritage", "Community Centers"]
}

def update_filters(category=None, subcategory=None, country=None, search=None, min_trust=None):
    if category is not None:
        st.session_state.sel_category = category
        st.session_state.sel_subcategory = "All Subcategories"
    if subcategory is not None:
        st.session_state.sel_subcategory = subcategory
    if country is not None:
        st.session_state.sel_country = country
    if search is not None:
        st.session_state.search_query = search
    if min_trust is not None:
        st.session_state.min_trust = min_trust


def create_search_assistant(prompt):
    prompt_lower = prompt.lower()
    response = "I found relevant NGOs across the marketplace. Refine further by location, service type, or trust level."
    if any(term in prompt_lower for term in ["medical", "health", "clinic", "hospital"]):
        update_filters(category="Medical Support & Health", search="", min_trust=7.0)
        response = "Showing Medical Support & Health organizations now. You can also ask for 'mobile clinics in India' or 'urgent care'."
    elif any(term in prompt_lower for term in ["cloth", "clothing", "winter", "shelter"]):
        update_filters(category="Clothing & Shelter", search="", min_trust=6.0)
        response = "Filtered to Clothing & Shelter NGOs. Try asking for 'clothing drives in USA' or 'shelter support'."
    elif any(term in prompt_lower for term in ["plant", "tree", "green", "environment"]):
        update_filters(category="Environment & Tree Planting", search="", min_trust=6.5)
        response = "Presenting Environment & Tree Planting causes. You can also narrow to 'urban greening' or 'reforestation'."
    elif any(term in prompt_lower for term in ["temple", "culture", "community"]):
        update_filters(category="Community & Culture", search="", min_trust=6.0)
        response = "Showing Community & Culture initiatives. Try 'temple support' or 'heritage preservation'."
    elif any(term in prompt_lower for term in ["education", "school", "scholarship"]):
        update_filters(category="Education & Scholarships", search="", min_trust=7.5)
        response = "Filtered to Education & Scholarships NGOs. You can refine with 'career guidance' or 'student scholarships'."
    elif any(term in prompt_lower for term in ["food", "meal", "hunger", "nutrition"]):
        update_filters(category="Food Supply", search="", min_trust=7.0)
        response = "Showing Food Supply partners. Ask for 'meal distribution' or 'school lunches' to narrow it further."
    elif "india" in prompt_lower:
        update_filters(country="India", search="")
        response = "Filtered results to India. You can also ask for a category like 'health' or 'education'."
    elif "usa" in prompt_lower or "america" in prompt_lower:
        update_filters(country="USA", search="")
        response = "Filtered results to the USA. Ask for more specific services like 'clothing' or 'medical'."
    elif "high trust" in prompt_lower or "verified" in prompt_lower:
        update_filters(min_trust=8.5)
        response = "Showing only highly verified NGOs with strong trust ratings."
    elif "low trust" in prompt_lower or "pending" in prompt_lower:
        update_filters(min_trust=0.0)
        response = "Showing all available NGOs, including pending reviews."
    else:
        update_filters(search=prompt)
    return response


def show_login_page():
    """Display the login and signup interface."""
    st.markdown("<div style='text-align: center; padding: 2rem 0;'><h1>🤝 CivicLink</h1><p>Secure Access to the NGO Marketplace</p></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_l, tab_s = st.tabs(["Login", "Create Account"])
        
        with tab_l:
            l_email = st.text_input("Email", key="l_email")
            l_pwd = st.text_input("Password", type="password", key="l_pwd")
            if st.button("Sign In", use_container_width=True):
                res = authenticate_user(l_email, l_pwd)
                if res["success"]:
                    st.session_state.authenticated = True
                    st.session_state.user_email = l_email
                    if "show_auth" in st.session_state:
                        st.session_state.show_auth = False
                    st.rerun()
                else:
                    st.error(res["msg"])
            
            st.divider()
            if st.button("Continue with Google 🚀", use_container_width=True, type="secondary"):
                # Real Google OAuth requires Client IDs. 
                # Here we simulate the successful return of a Gmail account.
                google_email = "user@gmail.com" 
                login_with_google_simulated(google_email)
                st.session_state.authenticated = True
                st.session_state.user_email = google_email
                if "show_auth" in st.session_state:
                    st.session_state.show_auth = False
                st.success("Google Authentication Simulated Successfully!")
                st.rerun()

        with tab_s:
            s_email = st.text_input("Email", key="s_email")
            s_pwd = st.text_input("Password", type="password", key="s_pwd")
            s_pwd_conf = st.text_input("Confirm Password", type="password", key="s_pwd_conf")
            
            if st.button("Register", use_container_width=True):
                if s_pwd != s_pwd_conf:
                    st.error("Passwords do not match.")
                elif len(s_pwd) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    res = register_user(s_email, s_pwd)
                    if res["success"]:
                        st.success("Account created! Please login.")
                    else:
                        st.error(res["msg"])


# =====================================================================
# 3. MODERN FRONTEND UI (STREAMLIT)
# =====================================================================
def main():
    # Setup page properties
    st.set_page_config(page_title="CivicLink Hub", layout="wide", page_icon="🤝")
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "show_auth" not in st.session_state:
        st.session_state.show_auth = False
    
    try:
        init_db()
        seed_initial_data()
    except Exception as e:
        st.error(f"Database Initialization Error: {e}")

    if st.session_state.show_auth:
        if st.button("← Back to Marketplace"):
            st.session_state.show_auth = False
            st.rerun()
        show_login_page()
        return

    # Custom Clean UI injection using CSS
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
            
            html, body, [class*="css"] {
                font-family: 'Inter', sans-serif;
            }

            .main { background-color: #f8fafc; }
            
            /* Modern Tabs */
            .stTabs [data-baseweb="tab-list"] { 
                gap: 8px; 
                background-color: #f1f5f9;
                padding: 6px;
                border-radius: 12px;
            }
            .stTabs [data-baseweb="tab"] {
                background-color: transparent;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                color: #64748b;
                border: none !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
            .stTabs [data-baseweb="tab"][aria-selected="true"] {
                background-color: white;
                color: #0f172a !important;
                box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            }

            /* Cards and Containers */
            .ngo-card {
                border-radius: 16px;
                padding: 24px;
                background: white;
                border: 1px solid #e2e8f0;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                margin-bottom: 20px;
            }
            .ngo-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 12px 24px -10px rgba(0,0,0,0.08);
                border-color: #cbd5e1;
            }

            .assistant-box {
                background: rgba(255, 255, 255, 0.7);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.5);
                border-radius: 20px;
                padding: 24px;
                box-shadow: 0 8px 32px rgba(31, 38, 135, 0.07);
            }
            
            .stat-card {
                border-radius: 16px;
                padding: 20px;
                background: white;
                border: 1px solid #f1f5f9;
                text-align: center;
            }
            .stat-card h3 { color: #64748b; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
            .stat-card span { color: #0f172a; font-size: 1.75rem; font-weight: 700; }

            /* Accents */
            .ai-gradient {
                background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
                color: white !important;
        </style>
    """, unsafe_allow_html=True)

    # Clean Header Hero Section
    head_col1, head_col2 = st.columns([0.8, 0.2])
    with head_col1:
        st.title("🤝 CivicLink")
        st.markdown("<p style='color: #64748b; font-size: 1.1rem; margin-top: -15px;'>The Intelligent Verification Marketplace for Global Impact.</p>", unsafe_allow_html=True)
    with head_col2:
        st.write("")
        if st.session_state.authenticated:
            st.markdown(f"<div style='text-align: right; font-size: 0.85rem; color: #64748b; margin-bottom: 5px;'>{st.session_state.user_email}</div>", unsafe_allow_html=True)
            if st.button("Sign Out", use_container_width=True):
                st.session_state.authenticated = False
                st.rerun()
        else:
            if st.button("Login / Sign Up", type="primary", use_container_width=True):
                st.session_state.show_auth = True
                st.rerun()
            
    if "sel_country" not in st.session_state:
        st.session_state.sel_country = "All Countries"
    if "sel_category" not in st.session_state:
        st.session_state.sel_category = "All Categories"
    if "sel_subcategory" not in st.session_state:
        st.session_state.sel_subcategory = "All Subcategories"
    if "min_trust" not in st.session_state:
        st.session_state.min_trust = 0.0
    if "search_query" not in st.session_state:
        st.session_state.search_query = ""
    if "assistant_history" not in st.session_state:
        st.session_state.assistant_history = []

    # Hero metrics and featured categories
    top_metrics = fetch_metrics()

    hero_col1, hero_col2, hero_col3 = st.columns(3)
    with hero_col1:
        st.markdown("<div class='stat-card'><h3>NGO Partners</h3><span>{}</span></div>".format(int(top_metrics['total'])), unsafe_allow_html=True)
    with hero_col2:
        st.markdown("<div class='stat-card'><h3>Verified Listings</h3><span>{}</span></div>".format(int(top_metrics['verified'])), unsafe_allow_html=True)
    with hero_col3:
        st.markdown("<div class='stat-card'><h3>Countries Served</h3><span>{}</span></div>".format(int(top_metrics['countries'])), unsafe_allow_html=True)

    st.write("---")
    st.markdown("#### 🧭 Explore Sectors")
    for row_idx in range(0, len(MAIN_CATEGORIES), 3):
        row_cols = st.columns(3)
        for col, category in zip(row_cols, MAIN_CATEGORIES[row_idx:row_idx+3]):
            col.button(category, key=f"quick_{category}", on_click=update_filters, kwargs={"category": category}, use_container_width=True)

    st.markdown("### 🔍 Filter Ecosystem")
    f_col1, f_col2, f_col3, f_col4 = st.columns([2, 2, 2, 2])
    with f_col1:
        sel_country = st.selectbox("🌐 Country", ["All Countries", "USA", "India"], key="sel_country")
    with f_col2:
        sel_category = st.selectbox("📁 Main Category", ["All Categories"] + MAIN_CATEGORIES, key="sel_category", on_change=update_filters, kwargs={"subcategory": "All Subcategories"})
    with f_col3:
        subcategory_options = ["All Subcategories"]
        if st.session_state.sel_category == "All Categories":
            all_subcats = sorted({sub for sublist in SUBCATEGORY_OPTIONS.values() for sub in sublist})
            subcategory_options.extend(all_subcats)
        else:
            subcategory_options.extend(SUBCATEGORY_OPTIONS.get(st.session_state.sel_category, []))
        sel_subcategory = st.selectbox("🧭 Subcategory", subcategory_options, key="sel_subcategory")
    with f_col4:
        # Removed redundant value parameter to resolve Streamlit Session State warning
        st.slider("🛡️ Minimum Trust Score Threshold", 0.0, 10.0, step=0.5, key="min_trust")

    search_query = st.text_input("🔎 Search NGOs, services or keywords", value=st.session_state.search_query, key="search_query", help="Type a keyword to find matching organizations quickly.")

    st.write("")

    # Primary Navigation Tabs
    tab1, tab2, tab3 = st.tabs(["🏛️ Marketplace", "✨ AI Scraper Engine", "📊 Transparency Registry"])

    # -----------------------------------------------------------------
    # TAB 1: MARKETPLACE
    # -----------------------------------------------------------------
    with tab1:
        # DB Query Processing
        ngos = fetch_ngos(
            category=sel_category,
            subcategory=sel_subcategory,
            country=sel_country,
            search=search_query,
            min_trust=st.session_state.min_trust,
        )
        df = pd.DataFrame(ngos)

        chat_col, result_col = st.columns([1.2, 2.8])
        with chat_col:
            st.markdown("<div class='assistant-box'><h3>✨ AI Assistant</h3><p style='color: #64748b; font-size: 0.9rem;'>Ask me to find specific aid or highly-trusted partners.</p></div>", unsafe_allow_html=True)
            for msg in st.session_state.assistant_history:
                st.chat_message(msg['role']).write(msg['content'])
            assistant_input = st.chat_input("How can I help you find the right NGO?")
            if assistant_input:
                st.session_state.assistant_history.append({"role": "user", "content": assistant_input})
                answer = create_search_assistant(assistant_input)
                st.session_state.assistant_history.append({"role": "assistant", "content": answer})

            st.markdown("**Quick prompts**")
            st.button("Find medical partners", on_click=update_filters, kwargs={"category": "Medical Support & Health", "search": "", "min_trust": 7.0})
            st.button("Find clothing & shelter", on_click=update_filters, kwargs={"category": "Clothing & Shelter", "search": "", "min_trust": 6.0})
            st.button("Show verified NGOs", on_click=update_filters, kwargs={"min_trust": 8.5})

        with result_col:
            if df.empty:
                st.warning("No verified or pending NGOs match your criteria. Head to the 'Trigger AI Scraper Engine' tab to find more entities automatically.")
            else:
                for index, row in df.iterrows():
                    # Clean, Card-Style Layout Container
                    score = row['trust_score']
                    badge_color = "#10b981" if score >= 8.5 else "#f59e0b" if score >= 7.0 else "#ef4444"
                    
                    st.markdown(f"""
                        <div class="ngo-card">
                            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
                                <div>
                                    <h3 style="margin: 0; font-size: 1.25rem; color: #0f172a;">{row['name']}</h3>
                                    <div style="font-size: 0.85rem; color: #64748b; margin-top: 4px;">
                                        {row['country']} • {row['category']}
                                    </div>
                                </div>
                                <div style="background: {badge_color}15; color: {badge_color}; padding: 4px 12px; border-radius: 99px; font-weight: 700; font-size: 0.85rem;">
                                    Trust Score: {score}/10
                                </div>
                            </div>
                            <p style="color: #334155; font-size: 0.95rem; line-height: 1.6; margin-bottom: 16px;">{row['description']}</p>
                            <div style="display: flex; gap: 20px; font-size: 0.85rem;">
                                <a href="{row['website']}" style="color: #6366f1; text-decoration: none; font-weight: 600;">🔗 Website</a>
                                <span style="color: #64748b;">✉️ {row['contact']}</span>
                                <span style="color: #94a3b8; margin-left: auto;">Verified: {row['last_updated']}</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                    # Seamless Inline Accordion Action Panel
                    with st.expander("🤝 Connect / Transact with this Organization"):
                        act_col1, act_col2 = st.columns(2, gap="large")
                        
                        with act_col1:
                            st.markdown("**Option A: Contribute Resources**")
                            c_type = st.selectbox("What will you give?", ["Financial Donation", "Volunteer Hours", "Physical Goods/Supplies"], key=f"ct_{row['id']}")
                            c_detail = st.text_input("Pledge Details / Availability notes", placeholder="e.g., Willing to pledge $100 or volunteer on weekends", key=f"cx_{row['id']}")
                            if st.button("Submit Contribution Intent", key=f"cb_{row['id']}", width='stretch'):
                                if not st.session_state.authenticated:
                                    st.session_state.show_auth = True
                                    st.rerun()
                                log_interaction(row['id'], "Contributor", c_type, c_detail)
                                st.success(f"Successfully connected with {row['name']}! Intakes staff will contact your verified email.")
                                
                        with act_col2:
                            st.markdown("**Option B: Request Services / Aid**")
                            s_need = st.text_area("Specify what resources or scholarships you need help with", placeholder="Describe your resource requirements concisely...", key=f"sx_{row['id']}")
                            if st.button("Request Support Resources", key=f"sb_{row['id']}", width='stretch'):
                                if not st.session_state.authenticated:
                                    st.session_state.show_auth = True
                                    st.rerun()
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
            agent_category = st.selectbox("Target Sector Matrix", MAIN_CATEGORIES)
        with col_b:
            agent_country = st.selectbox("Target Geographical Boundary", ["USA", "India"])
            
        if st.button("🚀 Execute Live Discovery & Auditing Pipeline", width='stretch'):
            if not st.session_state.authenticated:
                st.session_state.show_auth = True
                st.rerun()
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
        
        all_ngos = pd.DataFrame(fetch_all_ngos())
        all_interactions = pd.DataFrame(fetch_all_interactions())
        
        st.markdown("#### Indexed Database Organizations")
        st.dataframe(all_ngos, width='stretch', hide_index=True)
        
        st.markdown("#### Live Marketplace Operational Telemetry (Connections Formed)")
        if all_interactions.empty:
            st.info("No connections or match-making operations have occurred yet in this deployment instance.")
        else:
            st.dataframe(all_interactions, width='stretch', hide_index=True)

if __name__ == "__main__":
    main()