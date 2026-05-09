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
import streamlit as st
from src.config import APP_TITLE, NAVY, GOLD

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=":dna:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Sidebar logo - st.logo positions this above the nav specifically. CSS
# below enlarges the rendered image since size="large" alone isn't big enough.
# ---------------------------------------------------------------------------
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "inexion_logo.png")
if os.path.exists(_LOGO_PATH):
    st.logo(_LOGO_PATH, size="large", icon_image=_LOGO_PATH)


# ---------------------------------------------------------------------------
# Custom CSS - logo enlargement + section headers (UPPERCASE, BOLD, larger,
# tinted bg) + hover effects + active-state fix.
#
# Multiple fallback selectors used because Streamlit's emotion-cache class
# names change between versions; we target by stable testids and structural
# selectors instead.
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
        /* Sidebar background - subtle gradient */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #FAFAFC 0%, #F2F4F8 100%);
        }}

        /* Logo container - st.logo renders into a stLogo-tagged element.
           Enlarge the inner image and center-align. */
        [data-testid="stSidebar"] [data-testid="stLogo"],
        [data-testid="stSidebarHeader"] [data-testid="stLogo"] {{
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            padding: 22px 12px 14px 12px !important;
            border-bottom: 1px solid rgba(13, 27, 62, 0.08);
            margin-bottom: 8px;
            width: 100% !important;
        }}
        [data-testid="stSidebar"] [data-testid="stLogo"] img,
        [data-testid="stSidebarHeader"] [data-testid="stLogo"] img {{
            width: 80% !important;
            max-width: 220px !important;
            height: auto !important;
            min-height: 56px !important;
        }}

        /* SECTION HEADERS - all caps, bold, larger, navy on tinted bg.
           Streamlit's st.navigation renders each group label as a non-link
           div inside stSidebarNav. We target multiple possible structures
           to survive minor version changes. */
        [data-testid="stSidebarNav"] li > div:not(:has(a)),
        [data-testid="stSidebarNav"] ul > li:has(+ ul) > div,
        [data-testid="stSidebarNav"] [role="heading"],
        [data-testid="stSidebarNav"] h2,
        [data-testid="stSidebarNav"] h3,
        [data-testid="stSidebarNav"] section > h2,
        [data-testid="stSidebarNav"] section > div:not(:has(a)):first-child,
        [data-testid="stSidebarNav"] > ul > div:not(:has(a)),
        [data-testid="stSidebarNav"] > div > div > div:first-child:not(:has(a)) {{
            text-transform: uppercase !important;
            letter-spacing: 1.5px !important;
            font-size: 13px !important;
            font-weight: 800 !important;
            color: {NAVY} !important;
            background-color: #E1E5ED !important;
            padding: 10px 16px !important;
            border-radius: 4px !important;
            margin: 14px 8px 4px 8px !important;
            display: block !important;
        }}

        /* Belt and suspenders for the section header text node itself
           (sometimes wrapped in a span or p) */
        [data-testid="stSidebarNav"] li > div:not(:has(a)) span,
        [data-testid="stSidebarNav"] li > div:not(:has(a)) p,
        [data-testid="stSidebarNav"] [role="heading"] span,
        [data-testid="stSidebarNav"] h2 span,
        [data-testid="stSidebarNav"] h3 span {{
            text-transform: uppercase !important;
            font-size: 13px !important;
            font-weight: 800 !important;
            letter-spacing: 1.5px !important;
            color: {NAVY} !important;
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
            text-transform: none !important;
            font-weight: 400 !important;
            letter-spacing: normal !important;
        }}

        /* Nav link rows - hover state */
        [data-testid="stSidebarNav"] a:hover {{
            background-color: rgba(201, 148, 26, 0.14) !important;
            color: {NAVY} !important;
            transform: translateX(2px);
            box-shadow: 0 1px 3px rgba(13, 27, 62, 0.08);
        }}

        /* Active nav link - navy bg, white text */
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
# "Dashboard" group label avoids the visual duplication that "Home" group
# label would cause (since the page inside is also "Home").
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
