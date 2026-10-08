"""API de MediFlow."""
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from agent.graph import run_triage
from agent.ingestion import IngestionError, ingest_document
from agent.rules.loader import ReglasInvalidas, guardar_reglas, load_rules
from agent.schemas.contrato import TriageRequest, TriageResponse
from agent.storage import local_audit
from agent.storage.local_audit import (
    AccionInvalida,
    DocumentoNoEncontrado,
    ResolucionYaExiste,
)

app = FastAPI(title="MediFlow", version="0.1.0")


class DecisionAuditor(BaseModel):
    accion: Literal["aprobar", "corregir", "rechazar"]  # ADR-004
    revisor: str
    motivo: str
    correcciones: Optional[dict] = None


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
    try:
        contenido = await archivo.read()
        documento = ingest_document(contenido, filename=archivo.filename, content_type=archivo.content_type)
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await archivo.close()

    resultado = run_triage(
        documento_id,
        documento.tipo_archivo,
        documento.texto,
        canal_origen,
        imagenes=documento.imagenes,
        legibilidad=documento.legibilidad,
    )
    return _a_respuesta(resultado)


@app.get("/triage/{documento_id}")
def obtener_triage(documento_id: str):
    raise HTTPException(status_code=404, detail="pendiente de implementar")


@app.get("/queue/human")
def cola_humana():
    items = local_audit.listar_cola_humana(base=local_audit.DATA_DIR)
    return {"items": items}


@app.post("/audit/{documento_id}")
def auditar(documento_id: str, decision: DecisionAuditor):
    try:
        resolucion = local_audit.guardar_resolucion(
            documento_id,
            decision.accion,
            revisor=decision.revisor,
            motivo=decision.motivo,
            correcciones=decision.correcciones,
            base=local_audit.DATA_DIR,
        )
    except DocumentoNoEncontrado as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ResolucionYaExiste as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AccionInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"documento_id": documento_id, "resolucion": resolucion}


@app.get("/rules")
def reglas():
    return load_rules()


@app.put("/rules")
def actualizar_reglas(nuevas: dict):
    try:
        guardar_reglas(nuevas)
    except ReglasInvalidas as exc:
        raise HTTPException(status_code=422, detail={"errores": exc.errores}) from exc
    return {"actualizado": True}


@app.get("/metrics")
def metricas():
    return {"documentos_hoy": 0, "urgencias_hoy": 0, "en_revision": 0, "confianza_media": None}