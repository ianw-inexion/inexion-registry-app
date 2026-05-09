"""
INEXION Longevity Registry - app entry point.

Thin router that promotes Streamlit Cloud secrets into env vars, renders
the INEXION sidebar logo, defines grouped navigation via st.navigation,
and dispatches to the selected page module.
"""
from dotenv import load_dotenv
load_dotenv()

# Streamlit Cloud: load secrets into environment.
try:
    import streamlit as _st
    for _key in ["INEXION_DATA_DIR", "ANTHROPIC_API_KEY",
                 "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"]:
        if _key in _st.secrets and _key not in __import__("os").environ:
            __import__("os").environ[_key] = _st.secrets[_key]
except Exception:
    pass

import os
import base64
import streamlit as st
from src.config import APP_TITLE, NAVY, GOLD

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=":dna:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Sidebar logo - inject a centered <img> via HTML so we control size + alignment
# (st.logo size=large is too small at sidebar width)
# ---------------------------------------------------------------------------
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "inexion_logo.png")
if os.path.exists(_LOGO_PATH):
    with open(_LOGO_PATH, "rb") as _f:
        _LOGO_B64 = base64.b64encode(_f.read()).decode("ascii")
    st.sidebar.markdown(
        f"""
        <div style='display:flex;justify-content:center;align-items:center;
                    padding:18px 12px 14px 12px;
                    border-bottom:1px solid rgba(13,27,62,0.08);
                    margin-bottom:8px;'>
            <img src='data:image/png;base64,{_LOGO_B64}'
                 style='width:80%; max-width:200px; height:auto;
                        display:block;' />
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Custom CSS - section headers (all-caps bold, darker bg) + hover effects +
# active-state fix (ensure white text shows on navy active link).
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
        /* Sidebar background - subtle gradient */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #FAFAFC 0%, #F2F4F8 100%);
        }}

        /* Hide Streamlit's default page-name header at the very top of the
           nav (which would duplicate "app" / "Home" when section grouping
           is active). */
        [data-testid="stSidebarNav"] > ul > div:first-child {{
            display: none;
        }}

        /* Section headers - bold, uppercase, darker tinted background */
        [data-testid="stSidebarNav"] section header,
        [data-testid="stSidebarNav"] .st-emotion-cache-* h2,
        [data-testid="stSidebarNav"] li > span:not(:has(a)),
        section[data-testid="stSidebarNav"] li[aria-haspopup="true"] {{
            text-transform: uppercase !important;
            letter-spacing: 1.5px !important;
            font-size: 11px !important;
            font-weight: 800 !important;
            color: {NAVY} !important;
            background-color: #E8EAF0 !important;
            padding: 10px 16px !important;
            border-radius: 4px !important;
            margin: 12px 8px 4px 8px !important;
            display: block !important;
        }}

        /* Nav link rows - rest state */
        [data-testid="stSidebarNav"] a {{
            border-radius: 6px !important;
            padding: 8px 14px !important;
            margin: 2px 8px !important;
            transition: background-color 120ms ease, color 120ms ease,
                        transform 120ms ease, box-shadow 120ms ease !important;
            color: #1A1A2E !important;
            font-size: 14px !important;
        }}

        /* Nav link rows - hover state */
        [data-testid="stSidebarNav"] a:hover {{
            background-color: rgba(201, 148, 26, 0.14) !important;
            color: {NAVY} !important;
            transform: translateX(2px);
            box-shadow: 0 1px 3px rgba(13, 27, 62, 0.08);
        }}

        /* Active nav link - navy bg, white text. Belt-and-suspenders: also
           target child span / p / div to win specificity battles with
           Streamlit's default rules. */
        [data-testid="stSidebarNav"] a[aria-current="page"],
        [data-testid="stSidebarNav"] a[aria-current="page"] *,
        [data-testid="stSidebarNav"] a[aria-current="page"] span,
        [data-testid="stSidebarNav"] a[aria-current="page"] p {{
            background-color: {NAVY} !important;
            color: #FFFFFF !important;
            font-weight: 600 !important;
        }}
        [data-testid="stSidebarNav"] a[aria-current="page"]:hover,
        [data-testid="stSidebarNav"] a[aria-current="page"]:hover * {{
            background-color: {NAVY} !important;
            color: #FFFFFF !important;
            transform: none;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Navigation - grouped pages with friendly labels.
# Note: Home is intentionally placed under "Dashboard" rather than its own
# "Home" section, to avoid the visual duplication of section header "Home"
# above page link "Home".
# ---------------------------------------------------------------------------
_PAGES = {
    "Dashboard": [
        st.Page("home.py", title="Home",
                 icon=":material/home:", default=True),
    ],
    "Cohort Explorers": [
        st.Page("pages/1_NHANES_Explorer.py",
                 title="NHANES Explorer",
                 icon=":material/biotech:"),
        st.Page("pages/2_HRS_Explorer.py",
                 title="HRS Explorer",
                 icon=":material/biotech:"),
        st.Page("pages/3_MIDUS_Explorer.py",
                 title="MIDUS Explorer",
                 icon=":material/biotech:"),
        st.Page("pages/3c_NSHAP_Explorer.py",
                 title="NSHAP Explorer",
                 icon=":material/biotech:"),
        st.Page("pages/3_Market_Intelligence.py",
                 title="Market Intelligence",
                 icon=":material/explore:"),
    ],
    "Patient Tools": [
        st.Page("pages/4_Patient_Analysis.py",
                 title="Patient Analysis",
                 icon=":material/person:"),
    ],
    "Clocks & Validation": [
        st.Page("pages/5_Validation.py",
                 title="Validation Dashboard",
                 icon=":material/check_circle:"),
        st.Page("pages/6_Organ_Ages.py",
                 title="Organ Ages",
                 icon=":material/favorite:"),
        st.Page("pages/6b_Methylation_Clocks.py",
                 title="Methylation Clocks",
                 icon=":material/genetics:"),
    ],
    "Research": [
        st.Page("pages/7_Research_Workbench.py",
                 title="Research Workbench",
                 icon=":material/science:"),
    ],
    "Reference & Admin": [
        st.Page("pages/8_Dataset_Catalog.py",
                 title="Dataset Catalog",
                 icon=":material/folder:"),
        st.Page("pages/9_Variable_Dictionary.py",
                 title="Variable Dictionary",
                 icon=":material/menu_book:"),
        st.Page("pages/10_Admin.py",
                 title="Admin",
                 icon=":material/admin_panel_settings:"),
    ],
}

pg = st.navigation(_PAGES, position="sidebar", expanded=True)
pg.run()
