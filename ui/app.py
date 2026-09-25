"""Portada de MediFlow.

Antes de que alguien se pase diez minutos preguntándose por qué una pantalla está vacía, acá se ve
en qué entorno corre la UI y si la API responde.
"""
import os

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="MediFlow", page_icon="🏥", layout="wide")
st.title("MediFlow · Triaje de documentos clínicos")
st.write(
    "El agente recibe documentos clínicos en PDF, imagen, texto o JSON, los clasifica, extrae los "
    "datos, calcula un score de confianza, detecta urgencias y los enruta. Los casos ambiguos, "
    "inconsistentes o ilegibles van a un auditor humano. La decisión completa queda en la traza."
)

izquierda, derecha = st.columns(2)

with izquierda:
    st.markdown("#### Estado del entorno")
    try:
        salud = httpx.get(f"{API_URL}/health", timeout=10).json()
        st.success(f"API en `{API_URL}`: {salud.get('status', 's/d')}")
    except Exception as e:  # noqa: BLE001 - cualquier fallo de red deja la UI sin datos
        st.error(f"La API en `{API_URL}` no responde ({type(e).__name__}). Levantala con `make dev`.")

    st.caption(f"Entorno: `{os.getenv('ENV', 'dev')}` · almacenamiento: `{os.getenv('STORAGE_BACKEND', 'local')}`")
    llm_activo = os.getenv("USE_LLM", "false").lower() in ("true", "1", "yes")
    st.caption(f"Modelos: {'activos' if llm_activo else 'desactivados (clasifica y extrae por reglas)'}")
    st.caption(f"Principal: `{os.getenv('LLM_PRIMARY', 'gemini/gemini-2.5-flash')}`")
    respaldos = [m.strip() for m in os.getenv("LLM_FALLBACKS", "").split(",") if m.strip()]
    st.caption("Respaldos: " + (", ".join(f"`{m}`" for m in respaldos) if respaldos else "ninguno configurado"))

with derecha:
    st.markdown("#### Las seis pantallas")
    st.markdown(
        "- **Carga**: sube un documento y ve la respuesta completa del agente.\n"
        "- **Cola de triaje**: lo procesado, con destino, score y enlace al objeto del bucket.\n"
        "- **Auditoría**: Human-in-the-loop. Aprobar, corregir o rechazar, y la corrección reencamina.\n"
        "- **Reglas**: umbrales, destinos y listas que salen de `agent/rules/rules.yaml`.\n"
        "- **Métricas**: volumen, urgencias, tasa de revisión humana y calibración del score.\n"
        "- **Trazas**: qué hizo cada nodo del grafo, con qué modelo, en cuánto tiempo y a qué costo."
    )

st.divider()
st.markdown("#### Para tener datos en las pantallas de Métricas y Trazas")
st.markdown(
    "Los resultados se leen del bucket (`./data` en desarrollo, OCI Object Storage en la VM). "
    "Mientras no haya documentos procesados, esas dos pantallas explican qué falta en vez de mostrar "
    "un tablero vacío. Para generar los primeros:"
)
st.code(
    "curl -s -X POST http://localhost:8000/triage \\\n"
    '  -H "Content-Type: application/json" \\\n'
    "  -d @docs/examples/triage_request.json | python -m json.tool",
    language="bash",
)
st.caption(
    "Los datos son sintéticos. Nunca se sube información real de pacientes al repositorio ni al entorno "
    "de desarrollo."
)
