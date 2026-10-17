"""Trace page for the last result in the current session."""
import streamlit as st

st.title("🔍 Trazas")
result = st.session_state.get("last_triage_result")
if not result:
    st.info("Procesa un documento para consultar su traza.")
else:
    trace = result.get("trace", [])
    if trace:
        st.dataframe(trace, use_container_width=True)
    else:
        st.info("La API no devolvió pasos de traza para este resultado.")
