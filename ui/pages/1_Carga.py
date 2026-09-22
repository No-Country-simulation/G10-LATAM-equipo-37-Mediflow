import os

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
st.title("Carga de documentos")

with st.form("carga"):
    documento_id = st.text_input("documento_id", "DOC-CLIN-2026-0001")
    canal = st.text_input("canal_origen", "web")
    texto = st.text_area("Texto del documento (o sube un archivo abajo)", height=200)
    archivo = st.file_uploader("PDF o imagen", type=["pdf", "png", "jpg", "jpeg", "txt"])
    enviado = st.form_submit_button("Procesar")

if enviado:
    with st.spinner("Procesando..."):
        if archivo is not None:
            r = httpx.post(
                f"{API_URL}/triage/upload",
                data={"documento_id": documento_id, "canal_origen": canal},
                files={"archivo": (archivo.name, archivo.getvalue())},
                timeout=120,
            )
        else:
            r = httpx.post(
                f"{API_URL}/triage",
                json={
                    "documento_id": documento_id,
                    "tipo_archivo": "TEXTO",
                    "documento_texto": texto,
                    "canal_origen": canal,
                },
                timeout=120,
            )
    if r.status_code == 200:
        st.success("Procesado")
        st.json(r.json())
    else:
        st.error(f"Error {r.status_code}: {r.text}")
