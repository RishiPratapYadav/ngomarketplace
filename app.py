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
            .main { background-color: #f5f7fb; }
            .stTabs [data-baseweb="tab-list"] { gap: 14px; }
            .stTabs [data-baseweb="tab"] {
                background-color: #eef2fb;
                border-radius: 12px 12px 0 0;
                padding: 12px 24px;
                font-weight: 700;
                color: #303245;
                transition: all 0.2s ease;
            }
            .stTabs [data-baseweb="tab"][aria-selected="true"] {
                background-color: #4f6ef7;
                color: white !important;
                box-shadow: 0 8px 22px rgba(79,110,247,0.16);
            }
            .hero-card, .category-card, .assistant-box, .stat-card {
                border-radius: 18px;
                padding: 22px;
                background: white;
                box-shadow: 0 20px 50px rgba(15, 23, 42, 0.06);
                border: 1px solid rgba(226,232,240,0.7);
            }
            .category-card {
                min-height: 110px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 700;
                color: #27374d;
                transition: transform 0.2s ease, background 0.2s ease;
                cursor: pointer;
            }
            .category-card:hover {
                transform: translateY(-3px);
                background: #f8fbff;
                border-color: #dbe4ff;
            }
            .assistant-box {
                background: linear-gradient(180deg, rgba(247,250,255,0.96) 0%, rgba(255,255,255,0.98) 100%);
            }
            .stat-card h3 { margin: 0; color: #101828; font-size: 1.1rem; }
            .stat-card span { display: block; margin-top: 8px; color: #475569; font-size: 1.8rem; font-weight: 800; }
            .trust-high { color: #198754; font-weight: bold; font-size: 1.1rem; }
            .trust-mid { color: #ffc107; font-weight: bold; font-size: 1.1rem; }
            .trust-low { color: #dc3545; font-weight: bold; font-size: 1.1rem; }
            .assistant-box p { margin-bottom: 10px; }
        </style>
    """, unsafe_allow_html=True)

    # Clean Header Hero Section
    st.title("🤝 CivicLink")
    st.markdown("##### *The Autonomous Verification Marketplace Matching Donors & Aid Seekers with Trusted Non-Profits.*")

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

    st.markdown("### 🚀 Explore Trending Sectors")
    for row_idx in range(0, len(MAIN_CATEGORIES), 3):
        row_cols = st.columns(3)
        for col, category in zip(row_cols, MAIN_CATEGORIES[row_idx:row_idx+3]):
            if col.button(category, key=f"quick_{category}", on_click=update_filters, kwargs={"category": category}):
                pass
            col.markdown(f"<div class='category-card'>{category}</div>", unsafe_allow_html=True)

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
        min_trust = st.slider("🛡️ Minimum Trust Score Threshold", 0.0, 10.0, st.session_state.min_trust, step=0.5, key="min_trust")

    search_query = st.text_input("🔎 Search NGOs, services or keywords", value=st.session_state.search_query, key="search_query", help="Type a keyword to find matching organizations quickly.")

    st.write("")

    # Primary Navigation Tabs
    tab1, tab2, tab3 = st.tabs(["🏛️ Active NGO Marketplace", "🤖 Trigger AI Scraper Engine", "📊 Transparency Registry"])

    # -----------------------------------------------------------------
    # TAB 1: THE MARKETPLACE
    # -----------------------------------------------------------------
    with tab1:
        # DB Query Processing
        ngos = fetch_ngos(
            category=sel_category,
            subcategory=sel_subcategory,
            country=sel_country,
            search=search_query,
            min_trust=min_trust,
        )
        df = pd.DataFrame(ngos)

        chat_col, result_col = st.columns([1.2, 2.8])
        with chat_col:
            st.markdown("<div class='assistant-box'><h3>🧠 Search Assistant</h3><p>Ask CivicLink to narrow your search or choose a quick prompt.</p></div>", unsafe_allow_html=True)
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
                    with st.container():
                        left_col, right_col = st.columns([3, 1])
                        
                        with left_col:
                            st.markdown(f"### {row['name']} <span style='font-size:1rem; color:grey;'>({row['country']})</span>", unsafe_allow_html=True)
                            st.caption(f"**Category:** {row['category']} > {row['subcategory']}  |  **Last Verified Check:** {row['last_updated']}")
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
                            if st.button("Submit Contribution Intent", key=f"cb_{row['id']}", width='stretch'):
                                log_interaction(row['id'], "Contributor", c_type, c_detail)
                                st.success(f"Successfully connected with {row['name']}! Intakes staff will contact your verified email.")
                                
                        with act_col2:
                            st.markdown("**Option B: Request Services / Aid**")
                            s_need = st.text_area("Specify what resources or scholarships you need help with", placeholder="Describe your resource requirements concisely...", key=f"sx_{row['id']}")
                            if st.button("Request Support Resources", key=f"sb_{row['id']}", width='stretch'):
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