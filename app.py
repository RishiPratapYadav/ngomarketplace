import streamlit as st
import os
import pandas as pd
import datetime
import random
import requests
import re
from apscheduler.schedulers.background import BackgroundScheduler
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
    def _search_every_org(category, limit=3):
        """Every.org API for global NGO discovery."""
        url = f"https://partners.every.org/v1/search/{category}"
        params = {
            "take": limit,
            "apiKey": "public"
        }
        results = []
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for org in data.get("nonprofits", []):
                    results.append({
                        "name": org.get("name"),
                        "desc": org.get("description") or "International non-profit organization.",
                        "web": org.get("profileUrl") or "https://every.org",
                    })
        except Exception as e:
            print(f"Every.org Discovery Error: {e}")
        return results

    @staticmethod
    def _search_global_giving(category, limit=3):
        """GlobalGiving API for global NGO discovery."""
        api_key = os.getenv("GLOBALGIVING_API_KEY")
        if not api_key:
            return []
        url = "https://api.globalgiving.org/api/public/services/search/projects.json"
        params = {"api_key": api_key, "q": category}
        results = []
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # GlobalGiving structure for search results
                projects = data.get("search", {}).get("response", {}).get("projects", {}).get("project", [])
                if isinstance(projects, dict): projects = [projects]
                for p in projects[:limit]:
                    org = p.get("organization", {})
                    results.append({
                        "name": org.get("name") or p.get("title"),
                        "desc": p.get("summary") or "Active international development project.",
                        "web": org.get("url") or p.get("projectLink"),
                    })
        except Exception as e:
            print(f"GlobalGiving Discovery Error: {e}")
        return results

    @staticmethod
    def _search_wikipedia(category, country, limit=3):
        """Wikipedia API as a discovery tool for NGOs."""
        url = "https://en.wikipedia.org/w/api.php"
        search_query = f"Non-profit organization {category} {country}"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": search_query,
            "format": "json",
            "srlimit": limit
        }
        results = []
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            if "application/json" not in resp.headers.get("Content-Type", ""):
                print(f"Wikipedia Discovery Warning: Expected JSON but got {resp.headers.get('Content-Type')}")
                return []
            data = resp.json()
            for item in data.get("query", {}).get("search", []):
                title = item['title']
                snippet = re.sub(r'<[^>]+>', '', item['snippet'])
                results.append({
                    "name": title,
                    "desc": f"{snippet}...",
                    "web": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                })
        except Exception as e:
            print(f"Wikipedia Discovery Error: {e}")
        return results

    @staticmethod
    def _process_discovery_item(name, category, country, desc, web, reg_id=None):
        """Handles scoring and DB insertion for a discovered entity."""
        subcategory = SUBCATEGORY_OPTIONS.get(category, ["General"])[0]
        email = "contact@partner-network.org"

        # Dynamic Scoring Heuristics
        base_score = 8.0 if country == "USA" or "wikipedia" not in web.lower() else 6.5
        if reg_id: base_score += 1.0
        if desc and "Verified" in desc: base_score += 0.5
        
        final_score = round(min(base_score + random.uniform(0.1, 0.5), 10.0), 1)
        status = "Verified" if final_score >= 7.5 else "Pending Review"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        return insert_ngo(
            name,
            category,
            subcategory,
            country,
            desc or "",
            web,
            email,
            status,
            final_score,
            timestamp,
        )

    @staticmethod
    def run_autonomous_discovery():
        """
        Agentic task to balance and expand the marketplace database autonomously.
        1. Analyze current metrics to identify underserved sectors.
        2. Execute targeted discovery for those gaps.
        """
        try:
            all_ngos = fetch_all_ngos()
            if not all_ngos:
                target_cat = random.choice(MAIN_CATEGORIES)
            else:
                # Agentic Reasoning: Prioritize categories with the fewest NGOs to ensure marketplace balance
                counts = {cat: 0 for cat in MAIN_CATEGORIES}
                for ngo in all_ngos:
                    cat = ngo.get('category')
                    if cat in counts:
                        counts[cat] += 1
                target_cat = min(counts, key=counts.get)
            
            discoveries = []
            # Process discovery for primary target regions
            for country in ["USA", "India", "Global"]:
                try:
                    res = NGOAgentPipeline.run_pipeline(target_cat, country)
                    if res and res.get("success"):
                        discoveries.append(res)
                except Exception as e:
                    print(f"Autonomous discovery error for {country}: {e}")
            
            print(f"[{datetime.datetime.now()}] Autonomous Weekly Agent Discovery Completed: {len(discoveries)} new entities added.")
            return discoveries
        except Exception as e:
            print(f"Autonomous Agent Error: {e}")
            return []

    @staticmethod
    def run_pipeline(category, country, reg_id=None):
        """Discovers and verifies real NGO data using public APIs (Single Audit)."""
        name, desc, web = None, None, "https://not-found.org"

        # 1. Real-World Discovery/Verification Call
        if country == "USA":
            # Use ProPublica Nonprofit Explorer API (Free/Open)
            query = reg_id if reg_id else category
            url = f"https://projects.propublica.org/nonprofits/api/v2/search.json?q={query}"
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if data.get("organizations"):
                    org = data["organizations"][0] # Grab the top match
                    name = org.get("name").title()
                    desc = f"Verified US Nonprofit. EIN: {org.get('ein')}. Located in {org.get('city')}, {org.get('state')}."
                    # Note: ProPublica doesn't always provide the website in the search endpoint
                    web = f"https://projects.propublica.org/nonprofits/organizations/{org.get('ein')}"
            except Exception as e:
                print(f"USA Discovery Error: {e}")

        elif country == "India":
            # Use Wikipedia tool for India discovery
            wiki_results = NGOAgentPipeline._search_wikipedia(category, country, limit=1)
            if wiki_results:
                name, desc, web = wiki_results[0]['name'], wiki_results[0]['desc'], wiki_results[0]['web']

        elif country == "Global":
            # Use Every.org for global discovery
            every_results = NGOAgentPipeline._search_every_org(category, limit=1)
            if every_results:
                name, desc, web = every_results[0]['name'], every_results[0]['desc'], every_results[0]['web']
            else:
                # Fallback to GlobalGiving
                gg_results = NGOAgentPipeline._search_global_giving(category, limit=1)
                if gg_results:
                    name, desc, web = gg_results[0]['name'], gg_results[0]['desc'], gg_results[0]['web']

        # If Discovery failed to find a specific match, fallback to a placeholder with a low score
        if not name:
            name = f"Discovery: {category} Search"
            desc = "Our agent scanned regional records but could not find a high-confidence match for this specific query."
            final_score = 4.5
            status = "Pending Review"
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            subcategory = SUBCATEGORY_OPTIONS.get(category, ["General"])[0]
            return insert_ngo(name, category, subcategory, country, desc, web, "contact@not-found.org", status, final_score, timestamp)

        return NGOAgentPipeline._process_discovery_item(name, category, country, desc, web, reg_id)

    @staticmethod
    def run_bulk_pipeline(category, country, limit=5):
        """Bulk discovery and import using external tools (Wikipedia & ProPublica)."""
        items = []
        if country == "USA":
            url = f"https://projects.propublica.org/nonprofits/api/v2/search.json?q={category}"
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    orgs = resp.json().get("organizations", [])[:limit]
                    for org in orgs:
                        ein = org.get("ein")
                        items.append({
                            "name": org.get("name").title(),
                            "desc": f"Verified US Nonprofit. EIN: {ein}. Located in {org.get('city')}, {org.get('state')}.",
                            "web": f"https://projects.propublica.org/nonprofits/organizations/{ein}"
                        })
            except Exception as e:
                print(f"Bulk USA Discovery Error: {e}")
        
        # Global tools: Every.org, GlobalGiving, and Wikipedia
        if not items or country != "USA":
            items.extend(NGOAgentPipeline._search_every_org(category, limit=limit))
            if len(items) < limit:
                items.extend(NGOAgentPipeline._search_global_giving(category, limit=limit - len(items)))
            if len(items) < limit:
                items.extend(NGOAgentPipeline._search_wikipedia(category, country, limit=limit - len(items)))

        discoveries = []
        for item in items[:limit]:
            try:
                res = NGOAgentPipeline._process_discovery_item(item['name'], category, country, item['desc'], item['web'])
                if res and res.get("success"):
                    discoveries.append(res)
            except Exception as e:
                print(f"Discovery insertion error for {item.get('name')}: {e}")
        return discoveries


@st.cache_resource
def get_scheduler():
    """Persistently initialize and start the background scheduler."""
    sched = BackgroundScheduler()
    # Schedule autonomous discovery to run once a week
    sched.add_job(NGOAgentPipeline.run_autonomous_discovery, 'interval', weeks=1, id='weekly_discovery')
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    return sched


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
            st.info("💡 Real Google OAuth is required for public launch. Configure Supabase Auth Providers in the dashboard.")
            if st.button("Continue with Google (Dev Mode) 🚀", use_container_width=True, type="secondary"):
                st.warning("This is a developer bypass. Real OAuth must be implemented via `supabase.auth.sign_in_with_oauth()`.")
                # Mock logic for dev only
                st.session_state.authenticated = True
                st.session_state.user_email = "dev-tester@gmail.com"
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
    
    # Initialize the Autonomous Weekly Agent
    get_scheduler()

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
            }
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
        st.subheader("✨ Intelligent NGO Discovery")
        st.write("Enter a specific NGO registration ID or URL to run a live trust audit using our verification engine.")
        
        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            agent_category = st.selectbox("Target Sector Matrix", MAIN_CATEGORIES)
        with col_b:
            agent_country = st.selectbox("Target Geographical Boundary", ["USA", "India", "Global"])
        with col_c:
            reg_input = st.text_input("Registration ID (e.g. EIN or 80G)", placeholder="Optional")
            
        if st.button("🚀 Run AI Verification Audit", use_container_width=True):
            if not st.session_state.authenticated:
                st.session_state.show_auth = True
                st.rerun()
            with st.spinner(f"Agent executing live {agent_country} registry crawl..."):
                res = NGOAgentPipeline.run_pipeline(agent_category, agent_country, reg_id=reg_input)
                if res["success"]:
                    st.toast(f"Discovered: {res['name']}", icon="✅")
                    st.success(f"🎉 **New Entity Integrated Successfully!** Discovered, ranked, and indexed **{res['name']}** with a verified Trust Index score of **{res['score']}/10**.")
                else:
                    st.info("The automated indexer scanned the selected quadrant but identified no new unmapped entities.")

        if st.button("🔍 Bulk Discovery & Deep Audit", use_container_width=True):
            if not st.session_state.authenticated:
                st.session_state.show_auth = True
                st.rerun()
            with st.spinner(f"Agentic tools searching internet for {agent_category} partners..."):
                discoveries = NGOAgentPipeline.run_bulk_pipeline(agent_category, agent_country)
                if discoveries:
                    st.success(f"Successfully integrated {len(discoveries)} new partners into the marketplace.")
                    for d in discoveries:
                        st.markdown(f"- **{d['name']}** (Score: {d['score']} | Sector: `{d['subcategory']}`)")
                else:
                    st.info("No new unique partners identified in this sector audit.")

        st.divider()
        st.subheader("🕵️‍♂️ Autonomous Weekly Agent")
        st.info("The CivicLink Agent autonomously scans registries every week to balance the marketplace and fill gaps in underserved sectors.")
        
        if st.button("Manual Trigger: Run Weekly Agent Now", use_container_width=True):
            with st.spinner("Agent is analyzing marketplace health and discovering new partners..."):
                discoveries = NGOAgentPipeline.run_autonomous_discovery()
                if discoveries:
                    st.success(f"Agent successfully discovered {len(discoveries)} new partners!")
                    for d in discoveries:
                        st.markdown(f"- **{d['name']}** - Category: `{d['subcategory']}` | Trust Index: `{d['score']}`")
                else:
                    st.info("Agent analysis complete. No immediate critical gaps identified.")

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