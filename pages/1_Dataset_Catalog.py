"""Dataset Catalog — what's in the registry, what's pending, what's gated."""
import streamlit as st
from src.config import DATASETS, NAVY, GOLD

st.set_page_config(page_title="Dataset Catalog — INEXION Registry", layout="wide")
st.title("Dataset Catalog")
st.caption("Sources currently in the registry, pipelines built and ready, and access in progress.")

STATUS_COLOR = {
    "Available": "#2E8B8B",
    "Pipeline built — access pending": GOLD,
    "Application in progress": GOLD,
    "Access not yet initiated": "#6B6B8D",
    "P1 series ready to download": "#2E8B8B",
}

for d in DATASETS:
    color = STATUS_COLOR.get(d["status"], NAVY)
    st.markdown(
        f"""
        <div style='border-left: 4px solid {color};
                    background: #FAFAFB; padding: 16px 20px;
                    margin-bottom: 14px; border-radius: 4px;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div style='font-weight: 700; font-size: 18px; color: {NAVY};'>{d["name"]}</div>
                <div style='color: {color}; font-size: 12px; font-weight: 600;
                            text-transform: uppercase;'>{d["status"]}</div>
            </div>
            <div style='color: #6B6B8D; font-size: 13px; margin-top: 4px;'>{d["source"]}</div>
            <div style='margin-top: 12px; color: #1A1A2E; font-size: 14px;
                        line-height: 1.55;'>{d["description"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    cols[0].metric("Participants (approx)", f"{d['participants']:,}" if d["participants"] else "—")
    cols[1].metric("Cycles / waves", f"{d['cycles']}" if d["cycles"] else "—")
    cols[2].metric("Range", d["cycle_range"] or "—")
    cols[3].metric("Access tier", d["access"])
    st.markdown("")
