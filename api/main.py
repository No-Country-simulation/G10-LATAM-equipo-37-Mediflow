"""API de MediFlow."""
import hashlib

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from pydantic import ValidationError

from agent.graph import run_triage
from agent.ingestion import IngestionError, ingest_document
from agent.nodes.revision_humana import DecisionHumana
from agent.revision_runtime import RevisionConflicto, RevisionNoExiste, reanudar
from agent.rules.loader import load_rules
from agent.schemas.contrato import TriageRequest, TriageResponse
from agent.storage import local_audit
from agent.storage.backend import storage
from agent.storage.buckets import bucket_actual
from agent.storage.identificadores import validar_id
from agent.storage.local_audit import (
    AccionInvalida,
    DocumentoNoEncontrado,
    OriginalNoDisponible,
    ResolucionYaExiste,
)

app = FastAPI(title="MediFlow", version="0.1.0")


DecisionAuditor = DecisionHumana


def _validar_id(documento_id):
    try:
        validar_id(documento_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Identificador no permitido") from exc


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


def _ejecutar_triage(*args, **kwargs):
    try:
        return run_triage(*args, **kwargs)
    except OSError as exc:
        raise HTTPException(status_code=503, detail="No se pudo persistir; reintente el documento") from exc


@app.get("/health")
def health():
    return {"status": "ok", "service": "mediflow-api"}


@app.post("/triage", response_model=TriageResponse)
def triage(req: TriageRequest):
    _validar_id(req.documento_id)
    if req.tipo_archivo in ("TEXTO", "JSON") and not (req.documento_texto or "").strip():
        raise HTTPException(status_code=422, detail="documento_texto es obligatorio para TEXTO y JSON")
    resultado = _ejecutar_triage(req.documento_id, req.tipo_archivo, req.documento_texto, req.canal_origen)
    return _a_respuesta(resultado)


@app.post("/triage/upload", response_model=TriageResponse)
async def triage_upload(
    documento_id: str = Form(...), canal_origen: str = Form("web"), archivo: UploadFile = File(...)
):
    try:
        _validar_id(documento_id)
        contenido = await archivo.read()
        documento = ingest_document(contenido, filename=archivo.filename, content_type=archivo.content_type)
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await archivo.close()

    # Clave por contenido: reintentar el mismo ID no sustituye el original ya auditado.
    ruta_original = f"recibidos/{documento_id}/{hashlib.sha256(contenido).hexdigest()}"
    try:
        storage.upload_bytes(bucket_actual(), ruta_original, contenido)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="No se pudo guardar el original") from exc
    resultado = _ejecutar_triage(
        documento_id,
        documento.tipo_archivo,
        documento.texto,
        canal_origen,
        imagenes=documento.imagenes,
        legibilidad=documento.legibilidad,
        ruta_original=ruta_original,
    )
    return _a_respuesta(resultado)


@app.get("/triage/{documento_id}")
def obtener_triage(documento_id: str):
    raise HTTPException(status_code=404, detail="pendiente de implementar")


@app.get("/queue/human")
def cola_humana():
    items = local_audit.listar_cola_humana()
    return {"items": items}


@app.post("/audit/{documento_id}")
def auditar(documento_id: str, decision: DecisionAuditor):
    try:
        return reanudar(documento_id, decision.model_dump(exclude_none=True))
    except (DocumentoNoEncontrado, RevisionNoExiste) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ResolucionYaExiste, RevisionConflicto) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (AccionInvalida, ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="Decisión o identificador no válido") from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="No se pudo persistir; reintente la misma decisión") from exc


@app.get("/audit/{documento_id}/original")
def original_auditoria(documento_id: str):
    try:
        contenido, tipo = local_audit.obtener_original(documento_id)
    except (DocumentoNoEncontrado, OriginalNoDisponible) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=contenido, media_type=tipo)


@app.get("/rules")
def reglas():
    return load_rules()


@app.put("/rules")
def actualizar_reglas(nuevas: dict):
    return {"actualizado": False, "detalle": "pendiente de implementar"}


@app.get("/metrics")
def metricas():
    return {"documentos_hoy": 0, "urgencias_hoy": 0, "en_revision": 0, "confianza_media": None}
