"""Variable Dictionary — every column in the harmonized dataset with unit + definition."""
import streamlit as st
import pandas as pd
from src.schema import VARIABLES
from src.config import NAVY

st.set_page_config(page_title="Variable Dictionary — INEXION Registry", layout="wide")
st.title("Variable Dictionary")
st.caption("Every variable in the NHANES harmonized dataset — units, definitions, grouping.")
st.info(
    "**This dictionary covers the biomarker / phenotype layer** (NHANES, HRS, "
    "MIDUS, NSHAP). Two registry layers use their own schemas and are "
    "documented elsewhere:\n\n"
    "- The **GEO molecular-aging reference catalog** uses gene/probe IDs as "
    "feature columns (not named biomarker fields). Its variables are surfaced "
    "inside the **GEO Explorer** page, with per-dataset metadata tables and "
    "expression-matrix previews.\n\n"
    "- The **INEXION clinic layer** uses a ~70-column longitudinal lab panel "
    "(CBC + CMP + lipids + hormones + inflammation + iron + LD isoenzymes) "
    "plus an intervention taxonomy with therapeutic class, mechanism class, "
    "molecular target, and ATC/INEXION codes per intervention. These are "
    "surfaced inside the **Clinic Explorer** page (Lab Distributions tab + "
    "Interventions tab + per-patient drill-in)."
)

# Search
q = st.text_input("Search", placeholder="Type a variable name, unit, or keyword")

rows = []
for v in VARIABLES:
    rows.append({
        "Key": v["key"],
        "Label": v["label"],
        "Unit": v.get("unit", ""),
        "Group": v.get("group", ""),
        "Range": (
            f"{v['min']} – {v['max']}"
            if ("min" in v and "max" in v) else ""
        ),
        "Description": v.get("description", ""),
    })
df = pd.DataFrame(rows)

if q:
    ql = q.lower()
    mask = df.apply(lambda r: any(ql in str(r[c]).lower() for c in df.columns), axis=1)
    df = df[mask]

# Group + render
for group, sub in df.groupby("Group", sort=False):
    st.markdown(
        f"<div style='color:{NAVY}; font-weight:700; font-size:18px; "
        f"margin-top:20px; margin-bottom:6px;'>{group}</div>",
        unsafe_allow_html=True,
    )
    st.dataframe(
        sub[["Key", "Label", "Unit", "Range", "Description"]],
        width='stretch', hide_index=True, height=min(400, 55 + 35 * len(sub)),
    )

st.caption(f"{len(df)} variables shown.")
