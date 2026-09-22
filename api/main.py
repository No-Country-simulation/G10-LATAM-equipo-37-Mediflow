"""API de MediFlow."""
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from agent.graph import run_triage
from agent.rules.loader import load_rules
from agent.schemas.contrato import TriageRequest, TriageResponse

app = FastAPI(title="MediFlow", version="0.1.0")


def _a_respuesta(resultado: dict) -> TriageResponse:
    decision = resultado["decision"]
    status = "revision_humana" if decision["destino_principal"] == "Cola_Revision_Humana" else "procesado"
    return TriageResponse(
        status=status,
        documento_id=resultado["documento_id"],
        clasificacion=resultado.get("clasificacion") or {
            "tipo_documento": "Otro", "nivel_prioridad": "Rutina", "score_confianza_clasificacion": 0.0
        },
        datos_extraidos=resultado.get("datos_extraidos") or {},
        decision_enrutamiento=decision,
        almacenamiento_oci=resultado["almacenamiento"],
        score_confianza=resultado.get("score", 0.0),
        modelo_utilizado=resultado.get("modelo_utilizado"),
        trace=resultado.get("trace", []),
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "mediflow-api"}


@app.post("/triage", response_model=TriageResponse)
def triage(req: TriageRequest):
    if req.tipo_archivo in ("TEXTO", "JSON") and not req.documento_texto:
        raise HTTPException(status_code=422, detail="documento_texto es obligatorio para TEXTO y JSON")
    resultado = run_triage(req.documento_id, req.tipo_archivo, req.documento_texto, req.canal_origen)
    return _a_respuesta(resultado)


@app.post("/triage/upload", response_model=TriageResponse)
async def triage_upload(
    documento_id: str = Form(...), canal_origen: str = Form("web"), archivo: UploadFile = File(...)
):
    # TODO sprint 2: guardar en recibidos/, detectar PDF o imagen, renderizar y pasar imágenes al grafo.
    contenido = await archivo.read()
    tipo = "PDF" if archivo.filename.lower().endswith(".pdf") else "IMAGEN"
    texto = contenido.decode("utf-8", errors="ignore") if archivo.filename.lower().endswith(".txt") else ""
    resultado = run_triage(documento_id, "TEXTO" if texto else tipo, texto, canal_origen)
    return _a_respuesta(resultado)


@app.get("/triage/{documento_id}")
def obtener_triage(documento_id: str):
    # TODO sprint 2: leer de ADB o del bucket.
    raise HTTPException(status_code=404, detail="pendiente de implementar")


@app.get("/queue/human")
def cola_humana():
    # TODO sprint 3: listar auditoria_humana/ desde ADB.
    return {"items": []}


@app.post("/audit/{documento_id}")
def auditar(documento_id: str, decision: dict):
    # TODO sprint 3: guardar la decisión del auditor y reencaminar.
    return {"documento_id": documento_id, "recibido": decision}


@app.get("/rules")
def reglas():
    return load_rules()


@app.put("/rules")
def actualizar_reglas(nuevas: dict):
    # TODO sprint 3: persistir en la tabla rules de ADB y limpiar la caché.
    return {"actualizado": False, "detalle": "pendiente de implementar"}


@app.get("/metrics")
def metricas():
    # TODO sprint 3: KPIs desde ADB para el dashboard y el reporte diario.
    return {"documentos_hoy": 0, "urgencias_hoy": 0, "en_revision": 0, "confianza_media": None}
