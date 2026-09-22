import os

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
st.title("Reglas de triaje")
st.caption("Umbrales, destinos, hallazgos críticos y medicamentos de alto riesgo. Editables sin tocar el código.")
try:
    st.json(httpx.get(f"{API_URL}/rules", timeout=30).json())
except Exception as e:  # noqa: BLE001
    st.error(f"No se pudo leer /rules: {e}")
