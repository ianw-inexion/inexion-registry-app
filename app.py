"""
INEXION Longevity Registry - app entry point.

Thin router that promotes Streamlit Cloud secrets into env vars, renders
the INEXION sidebar logo, defines grouped navigation via st.navigation,
and dispatches to the selected page module.
"""
from dotenv import load_dotenv
load_dotenv()

# Streamlit Cloud: load secrets into environment.
# Promote them to env vars so the rest of the app (including src/config.py)
# picks them up transparently.
try:
    import streamlit as _st
    for _key in ["INEXION_DATA_DIR", "ANTHROPIC_API_KEY",
                 "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"]:
        if _key in _st.secrets and _key not in __import__("os").environ:
            __import__("os").environ[_key] = _st.secrets[_key]
except Exception:
    pass

import os
import streamlit as st
from src.config import APP_TITLE, NAVY, GOLD

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=":dna:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar logo - INEXION mark above the navigation
# ---------------------------------------------------------------------------
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "inexion_logo.png")
if os.path.exists(_LOGO_PATH):
    st.logo(_LOGO_PATH, size="large", icon_image=_LOGO_PATH)

# ---------------------------------------------------------------------------
# Custom CSS - hover effects on nav links + section header polish + tighter
# spacing for grouped sections.
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
        /* Sidebar background slightly tinted for distinction from main canvas */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #FAFAFC 0%, #F2F4F8 100%);
        }}

        /* Section headers in the navigation */
        [data-testid="stSidebarNav"] [data-testid="stSidebarNavSeparator"] {{
            margin-top: 14px !important;
            margin-bottom: 6px !important;
        }}
        [data-testid="stSidebarNav"] section > div > div:first-child {{
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-size: 11px !important;
            color: {NAVY} !important;
            padding: 12px 16px 4px 16px !important;
            border-bottom: 1px solid rgba(13, 27, 62, 0.08);
        }}

        /* Nav link rows - rest state */
        [data-testid="stSidebarNav"] a {{
            border-radius: 6px !important;
            padding: 8px 12px !important;
            margin: 2px 8px !important;
            transition: background-color 120ms ease, color 120ms ease,
                        transform 120ms ease, box-shadow 120ms ease !important;
            color: #1A1A2E !important;
        }}

        /* Nav link rows - hover state */
        [data-testid="stSidebarNav"] a:hover {{
            background-color: rgba(201, 148, 26, 0.12) !important;  /* GOLD tint */
            color: {NAVY} !important;
            transform: translateX(2px);
            box-shadow: 0 1px 3px rgba(13, 27, 62, 0.08);
        }}

        /* Active nav link */
        [data-testid="stSidebarNav"] a[aria-current="page"] {{
            background-color: {NAVY} !important;
            color: white !important;
            font-weight: 600 !important;
        }}
        [data-testid="stSidebarNav"] a[aria-current="page"]:hover {{
            background-color: {NAVY} !important;
            color: white !important;
        }}

        /* Logo container - tighter top padding */
        [data-testid="stSidebar"] [data-testid="stLogo"] {{
            padding-top: 12px;
            padding-bottom: 8px;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Navigation - grouped pages with friendly labels
# ---------------------------------------------------------------------------
_PAGES = {
    "Home": [
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
