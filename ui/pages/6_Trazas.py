"""Trazas · ver pensar al agente.

De dónde salen los datos, en este orden:

1. Los resultados persistidos en el bucket (`./data` en local, OCI en la VM). Es la vista histórica:
   cada documento con su traza completa.
2. Un JSON pegado o subido a mano. Sirve para revisar la corrida que mandó otra persona, sin
   depender del bucket.

La lógica de lectura y de cálculo vive en `agent/traza.py`, no acá: la UI solo muestra. Así el mismo
resumen lo puede usar la API y los tests lo prueban sin abrir Streamlit.
"""
import json
import sys
from pathlib import Path

import streamlit as st

# Streamlit ejecuta la página con la carpeta de la página en el path, así que la raíz del repo (dos
# niveles arriba) hay que agregarla a mano para poder importar `agent.traza`.
RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

try:
    from agent import traza
except ImportError:  # la UI se puede correr sin el paquete agent: se cae al JSON pegado
    traza = None

st.title("Trazas · ver pensar al agente")
st.caption(
    "Un registro por nodo del grafo: cuánto tardó, qué modelo respondió, cuánto costó y qué decidió. "
    "La traza no guarda el texto del documento: guarda conteos, decisiones y justificaciones."
)


def _duracion(ms) -> str:
    """Duración legible: milisegundos hasta un segundo, segundos a partir de ahí."""
    if ms is None:
        return "s/d"
    return f"{ms / 1000:.1f} s" if ms >= 1000 else f"{ms:.0f} ms"


def _costo(valor) -> str:
    if valor is None:
        return "s/d"
    return f"US$ {valor:.6f}".rstrip("0").rstrip(".") if valor < 1 else f"US$ {valor:.4f}"


@st.cache_data(ttl=30, show_spinner=False)
def _leer_persistidos(bucket: str) -> dict:
    """Lectura del bucket, cacheada 30 segundos para no golpear el almacenamiento en cada tecla."""
    return traza.leer_resultados(bucket=bucket)


def _cargar_del_bucket() -> dict | None:
    """Resultados persistidos, o None si no hay de dónde leer."""
    if traza is None:
        st.warning(
            "No se pudo importar `agent.traza`. Corré la UI desde la raíz del repo "
            "(`streamlit run ui/app.py`) o montá la carpeta `agent/` para ver el histórico."
        )
        return None

    bucket = traza.bucket_configurado()
    lectura = _leer_persistidos(bucket)
    if lectura["error"]:
        st.info(f"{lectura['error']} Procesá un documento (pantalla de Carga) o pegá un JSON abajo.")
        return None
    if not lectura["resultados"]:
        st.info(f"No hay resultados en el bucket `{bucket}` todavía.")
        return None

    aviso = f"{len(lectura['resultados'])} resultado(s) en `{bucket}`"
    if lectura["ilegibles"]:
        aviso += f" · {lectura['ilegibles']} archivo(s) ilegible(s), ignorados"
    st.caption(aviso)
    return lectura


# --------------------------------------------------------------------------- elección del documento

fuente = st.radio(
    "Fuente",
    ["Resultados persistidos", "Pegar o subir un JSON"],
    horizontal=True,
    help="El histórico sale del bucket; el JSON sirve para revisar una corrida puntual.",
)

resultado = None
if fuente == "Resultados persistidos":
    lectura = _cargar_del_bucket()
    if lectura:
        resultados = sorted(lectura["resultados"], key=lambda r: str(r.get("documento_id", "")))
        etiquetas = [
            f"{r.get('documento_id', 'sin id')} · {r.get('clasificacion', {}).get('tipo_documento', 'Otro')} "
            f"· score {r.get('score', 's/d')}"
            for r in resultados
        ]
        elegido = st.selectbox("Documento", range(len(resultados)), format_func=lambda i: etiquetas[i])
        resultado = resultados[elegido]
else:
    pegado = st.text_area("Resultado del triaje (JSON)", height=200, placeholder='{"documento_id": "DOC-1", ...}')
    subido = st.file_uploader("…o subí el archivo", type=["json"])
    contenido = subido.getvalue() if subido is not None else pegado
    if contenido:
        try:
            resultado = traza.cargar_json(contenido) if traza else json.loads(contenido)
        except (ValueError, json.JSONDecodeError) as e:
            st.error(str(e))

if not resultado:
    st.stop()

if traza is None:
    st.json(resultado.get("trace", []))
    st.stop()

resumen = traza.resumen_traza(resultado.get("trace"))
decision = resultado.get("decision") or {}
clasificacion = resultado.get("clasificacion") or {}
segunda = resultado.get("segunda_opinion") or {}

st.subheader(str(resultado.get("documento_id", "documento sin id")))
st.caption(
    f"{clasificacion.get('tipo_documento', 'Otro')} · prioridad {clasificacion.get('nivel_prioridad', 's/d')} "
    f"· score {resultado.get('score', 's/d')} · destino {decision.get('destino_principal', 's/d')}"
)

# --------------------------------------------------------------------------- números de la corrida

columnas = st.columns(5)
columnas[0].metric("Nodos", len(resumen["nodos"]))
columnas[1].metric("Tiempo total", _duracion(resumen["total_ms"]))
columnas[2].metric("Modelos", len(resumen["modelos"]) or "s/d")
columnas[3].metric("Tokens", resumen["tokens"]["entrada"] + resumen["tokens"]["salida"] or "s/d")
columnas[4].metric("Costo", _costo(resumen["costo_usd"]))

if not resumen["medido"] and resumen["nodos"]:
    st.caption(
        "Algunos registros no traen la duración medida: se muestra la diferencia entre marcas de "
        "tiempo, que acota al nodo siguiente."
    )

if resumen["cambio_de_modelo"]["hubo"]:
    cambio = resumen["cambio_de_modelo"]
    st.warning(f"Cambio de modelo en esta corrida: de `{cambio['de']}` a `{cambio['a']}`.")
else:
    st.caption(f"Un solo modelo en toda la corrida: `{resumen['modelos'][0] if resumen['modelos'] else 'sin modelo'}`.")

# --------------------------------------------------------------------------- línea de tiempo

st.markdown("#### Línea de tiempo")
tabla = [
    {
        "Nodo": nodo["nodo"],
        "Modelo": nodo["modelo"] or "—",
        "Duración": _duracion(nodo["ms"]),
    }
    for nodo in resumen["nodos"]
]
st.dataframe(tabla, width="stretch", hide_index=True)

duraciones = {
    f"{indice + 1}. {nodo['nodo']}": nodo["ms"] for indice, nodo in enumerate(resumen["nodos"]) if nodo["ms"]
}
if duraciones:
    st.bar_chart(duraciones, horizontal=True, color="#4C78A8")

st.caption("Abrí cada nodo para ver qué decidió exactamente.")
for indice, nodo in enumerate(resumen["nodos"]):
    modelo = f" · {nodo['modelo']}" if nodo["modelo"] else ""
    with st.expander(f"{indice + 1}. {nodo['nodo']} · {_duracion(nodo['ms'])}{modelo}"):
        st.json(nodo["detalle"] or {})

# --------------------------------------------------------------------------- segunda opinión

st.markdown("#### Segunda opinión")
if not segunda:
    st.caption("En esta corrida no se pidió segunda opinión: el score no cayó en la franja media.")
else:
    if segunda.get("disponible"):
        if segunda.get("acuerdo"):
            st.success(f"Los dos modelos coinciden en los campos comparables ({segunda.get('campos_comparados', 0)}).")
        else:
            st.error("Los modelos no coinciden en: " + ", ".join(segunda.get("campos_en_desacuerdo", [])))
    else:
        st.warning(f"Segunda opinión no disponible: {segunda.get('motivo', 'sin motivo registrado')}")

    columnas_so = st.columns(3)
    columnas_so[0].metric("Modelo principal", segunda.get("modelo_primario") or "s/d")
    columnas_so[1].metric("Modelo de respaldo", segunda.get("modelo") or "s/d")
    columnas_so[2].metric("Latencia", _duracion(segunda.get("latencia_ms")))
    st.caption(f"Motivo: {segunda.get('motivo', 's/d')}")

    if segunda.get("campos_solo_en_un_modelo"):
        st.caption(
            "Campos que completó un solo modelo (diferencia de cobertura, no de criterio): "
            + ", ".join(segunda["campos_solo_en_un_modelo"])
        )
    if segunda.get("datos"):
        with st.expander("Extracción del segundo modelo"):
            st.json(segunda["datos"])

# --------------------------------------------------------------------------- decisión y descarga

st.markdown("#### Decisión")
st.write(f"**Destino:** {decision.get('destino_principal', 's/d')}")
st.write(f"**Requiere auditoría humana:** {'sí' if decision.get('requiere_auditoria_humana') else 'no'}")
st.write(f"**Justificación:** {decision.get('justificacion_enrutamiento', 's/d')}")

notificacion = decision.get("notificacion_generada") or {}
if notificacion:
    st.info(f"Notificación ({notificacion.get('canal', 's/d')}): {notificacion.get('mensaje', 's/d')}")

st.download_button(
    "Descargar la traza (JSON)",
    data=json.dumps(resultado, ensure_ascii=False, indent=2),
    file_name=f"traza-{resultado.get('documento_id', 'documento')}.json",
    mime="application/json",
)
st.caption(
    "Datos sintéticos. La traza guarda conteos, decisiones y justificaciones: no guarda el texto del "
    "documento ni las imágenes."
)
