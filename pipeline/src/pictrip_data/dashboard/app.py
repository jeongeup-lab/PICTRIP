"""Streamlit dashboard (CT111 :8501, tailnet only).

Pipeline-internal view of sync history. The service-side ops admin lives in the
backend (`/admin`) and reads `sync_runs` read-only — keep roles separate.
"""

import streamlit as st

st.title("pictrip-data — pipeline dashboard")
st.caption("KTO collection runs (sync_runs). Internal / tailnet only.")

# TODO: query sync_runs, show recent runs table + counters + error drilldown.
