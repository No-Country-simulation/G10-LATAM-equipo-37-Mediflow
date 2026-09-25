"""Metrics page."""
import streamlit as st

from ui.lib import api_request, show_api_error

st.title("📊 Métricas")
try:
    response = api_request("GET", "/metrics")
    if response.is_success:
        metrics = response.json()
        cols = st.columns(len(metrics) or 1)
        for column, (name, value) in zip(cols, metrics.items()):
            column.metric(name.replace("_", " ").title(), "-" if value is None else value)
        with st.expander("Respuesta completa"):
            st.json(metrics)
    else:
        show_api_error(response)
except RuntimeError as exc:
    st.error(str(exc))
