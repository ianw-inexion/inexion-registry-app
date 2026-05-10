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

        /* Logo - st.logo renders into a stSidebarHeader testid. Force it
           wider and centered with breathing room above and below. */
        [data-testid="stSidebarHeader"],
        [data-testid="stSidebar"] > div > div:first-child:has(img) {{
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            padding: 28px 12px 24px 12px !important;
            border-bottom: 1px solid rgba(13, 27, 62, 0.08) !important;
            margin-top: 8px !important;
            margin-bottom: 16px !important;
            width: 100% !important;
        }}
        [data-testid="stSidebarHeader"] img,
        [data-testid="stSidebar"] [data-testid="stLogo"] img,
        [data-testid="stSidebar"] [data-testid="stLogo"] {{
            width: 85% !important;
            max-width: 240px !important;
            height: auto !important;
            min-height: 64px !important;
            margin: 0 auto !important;
            display: block !important;
        }}

        /* SECTION HEADERS - styling is keyed off the .inexion-section-header
           class added by JS below. Streamlit's emotion-cache class names
           change between versions, so we tag headers by behavior
           (cursor:pointer, no descendant <a>) rather than tag/class names. */
        .inexion-section-header {{
            text-transform: uppercase !important;
            letter-spacing: 1.5px !important;
            font-size: 13px !important;
            font-weight: 800 !important;
            color: {NAVY} !important;
            background-color: #E1E5ED !important;
            padding: 10px 16px !important;
            border-radius: 4px !important;
            margin: 14px 8px 4px 8px !important;
            list-style: none !important;
        }}

        /* Inner <p>/<span> labels inherit the header look */
        .inexion-section-header * {{
            text-transform: uppercase !important;
            font-size: 13px !important;
            font-weight: 800 !important;
            letter-spacing: 1.5px !important;
            color: {NAVY} !important;
            background-color: transparent !important;
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
        st.Page("home.py", title="Registry Stats",
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
        st.Page("pages/3d_GEO_Explorer.py",
                 title="GEO Explorer",
                 icon=":material/genetics:"),
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
        st.Page("pages/6c_Pathway_Decomposition.py",
                 title="Pathway Decomposition",
                 icon=":material/network_intel_node:"),
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

# JS - tag every section-header element with .inexion-section-header.
# Detection is behavioral: an element is a section header iff it has
# cursor:pointer AND contains no <a> descendant AND isn't inside an <a>.
# This is independent of Streamlit's volatile emotion-cache class names
# and works for both expanded and collapsed sections.
import streamlit.components.v1 as components
components.html(
    """
    <script>
    (function() {
        const parentDoc = window.parent.document;
        const parentWin = window.parent;
        const tag = () => {
            const nav = parentDoc.querySelector('[data-testid="stSidebarNav"]');
            if (!nav) return;
            const all = nav.querySelectorAll('*');
            all.forEach(el => {
                if (el.classList.contains('inexion-section-header')) return;
                if (el.tagName === 'A') return;
                if (el.querySelector('a')) return;
                if (el.closest('a')) return;
                const cs = parentWin.getComputedStyle(el);
                if (!cs || cs.cursor !== 'pointer') return;
                // Only tag the OUTERMOST cursor:pointer element. cursor is
                // inherited so every descendant of a toggle div also reports
                // pointer; tagging them stacks padding/margin and hides text.
                const parent = el.parentElement;
                if (parent && parent !== nav) {
                    const pcs = parentWin.getComputedStyle(parent);
                    if (pcs && pcs.cursor === 'pointer') return;
                }
                el.classList.add('inexion-section-header');
            });
        };
        tag();
        // Re-tag whenever Streamlit re-renders any part of the sidebar
        const sidebar = parentDoc.querySelector('[data-testid="stSidebar"]');
        if (sidebar) {
            const obs = new MutationObserver(() => {
                // Defer one frame so emotion classes settle before measuring
                requestAnimationFrame(tag);
            });
            obs.observe(sidebar, {childList: true, subtree: true});
        }
        // Safety net: re-tag a few times after initial load
        setTimeout(tag, 100);
        setTimeout(tag, 400);
        setTimeout(tag, 1000);
    })();
    </script>
    """,
    height=0, width=0,
)

pg.run()
