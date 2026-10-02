"""Shared helpers for the Streamlit pages."""
from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

API_URL = os.getenv("MEDIFLOW_API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = float(os.getenv("MEDIFLOW_API_TIMEOUT", "120"))


def api_request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    """Call the API and turn network failures into a user-facing message."""
    try:
        return httpx.request(method, f"{API_URL}{path}", timeout=TIMEOUT, **kwargs)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"No se pudo conectar con la API en {API_URL}: {exc}") from exc


def show_api_error(response: httpx.Response) -> None:
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    st.error(f"La API respondió {response.status_code}: {detail}")


def remember_document(uploaded_file: Any) -> None:
    """Keep the original bytes in session state so auditors can recall the document."""
    st.session_state["review_file_name"] = uploaded_file.name
    st.session_state["review_file_type"] = uploaded_file.type or "application/octet-stream"
    st.session_state["review_file_bytes"] = uploaded_file.getvalue()


def show_document_preview() -> None:
    data = st.session_state.get("review_file_bytes")
    if not data:
        st.warning("No hay una copia local del documento original para revisar.")
        return

    name = st.session_state.get("review_file_name", "documento")
    mime = st.session_state.get("review_file_type", "application/octet-stream")
    st.markdown(f"**Documento original:** `{name}`")
    if mime.startswith("image/"):
        st.image(data, caption=name, use_container_width=True)
    elif mime == "application/pdf":
        st.download_button("Descargar PDF para revisar", data, file_name=name, mime=mime)
        st.caption("La vista previa del PDF está disponible descargándolo; el archivo original se conserva en esta sesión.")
    elif mime.startswith("text/") or name.lower().endswith((".txt", ".json")):
        st.code(data.decode("utf-8", errors="replace"), language="json" if name.endswith(".json") else "text")
    else:
        st.download_button("Descargar documento original", data, file_name=name, mime=mime)


def render_result(result: dict[str, Any]) -> None:
    status = result.get("status", "desconocido")
    decision = result.get("decision_enrutamiento", {})
    classification = result.get("clasificacion", {})
    score = result.get("score_confianza")

    if status == "revision_humana" or decision.get("requiere_auditoria_humana"):
        st.warning("Este documento requiere revisión humana antes de continuar.")
    elif status == "procesado":
        st.success("Documento procesado correctamente.")
    else:
        st.info(f"Estado: {status}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Documento", result.get("documento_id", "-"))
    c2.metric("Tipo", classification.get("tipo_documento", "-"))
    c3.metric("Confianza", f"{float(score):.0%}" if isinstance(score, (int, float)) else "-")
    st.write("**Destino:**", decision.get("destino_principal", "-"))
    st.write("**Justificación:**", decision.get("justificacion_enrutamiento", "-"))
    with st.expander("Resultado completo"):
        st.json(result)
