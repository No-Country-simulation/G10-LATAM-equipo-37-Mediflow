"""API de MediFlow."""
import hmac
import logging
import os
from pathlib import Path
from typing import Literal, Optional

from agent.storage.buckets import bucket_actual

if os.getenv("STORAGE_BACKEND", "local").lower() == "oci":
    from agent.storage import object_storage as upload_storage
else:
    from agent.storage import local as upload_storage

from fastapi import FastAPI, File, Form, Header, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent.graph import run_triage
from agent.ingestion import IngestionError, ingest_document
from agent.rules.loader import ReglasInvalidas, guardar_reglas, load_rules, toca_umbrales
from agent.schemas.contrato import TriageRequest, TriageResponse
from agent.storage import local_audit, triage_results
from agent.storage.local_audit import (
    AccionInvalida,
    DocumentoNoEncontrado,
    OriginalNoDisponible,
    ResolucionYaExiste,
)

app = FastAPI(title="MediFlow", version="0.1.0")


class DecisionAuditor(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    accion: Literal["aprobar", "corregir", "rechazar"]  # ADR-004
    revisor: str = Field(min_length=1)
    motivo: str = Field(min_length=1)
    correcciones: Optional[dict] = None

    @model_validator(mode="after")
    def _correcciones_solo_al_corregir(self):
        if self.correcciones and self.accion != "corregir":
            raise ValueError("Las correcciones solo se admiten con la acción 'corregir'")
        return self


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

    resultado = run_triage(
        req.documento_id,
        req.tipo_archivo,
        req.documento_texto,
        req.canal_origen,
    )
    respuesta = _a_respuesta(resultado)
    triage_results.guardar_resultado(respuesta.model_dump(mode="json"))
    return respuesta

_EXTENSOES_POR_TIPO = {
    "PDF": {".pdf"},
    "TEXTO": {".txt"},
    "JSON": {".json"},
    "IMAGEN": {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"},
}

_EXTENSOES_POR_MIME = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "application/json": ".json",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/tiff": ".tiff",
    "image/webp": ".webp",
}


def _extensao_original(
    filename: str | None,
    content_type: str | None,
    tipo_archivo: str,
) -> str:
    extensiones_validas = _EXTENSOES_POR_TIPO.get(tipo_archivo)
    if extensiones_validas is None:
        raise HTTPException(
            status_code=422,
            detail="Tipo de archivo no válido",
        )

    extension = Path(filename or "").suffix.lower()
    if extension in extensiones_validas:
        return extension

    mime = (content_type or "").split(";", 1)[0].lower()
    extension = _EXTENSOES_POR_MIME.get(mime)

    if extension in extensiones_validas:
        return extension

    raise HTTPException(
        status_code=422,
        detail="No se pudo determinar la extensión del archivo",
    )



@app.post("/triage/upload", response_model=TriageResponse)
async def triage_upload(
    documento_id: str = Form(...),
    canal_origen: str = Form("web"),
    archivo: UploadFile = File(...),
):
    if (
        not documento_id.strip()
        or documento_id in {".", ".."}
        or "/" in documento_id
        or "\\" in documento_id
    ):
        raise HTTPException(
            status_code=422,
            detail="documento_id no válido",
        )

    try:
        contenido = await archivo.read()
        documento = ingest_document(
            contenido,
            filename=archivo.filename,
            content_type=archivo.content_type,
        )
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await archivo.close()

    extension = _extensao_original(
        archivo.filename,
        archivo.content_type,
        documento.tipo_archivo,
    )
    ruta_original = f"recibidos/{documento_id}{extension}"

    try:
        upload_storage.upload_bytes(
            bucket_actual(),
            ruta_original,
            contenido,
            content_type=archivo.content_type or "application/octet-stream",
        )
    except Exception as exc:
        logging.exception("No se pudo guardar el archivo original")
        raise HTTPException(
            status_code=503,
            detail="No se pudo guardar el archivo original",
        ) from exc

    resultado = run_triage(
        documento_id,
        documento.tipo_archivo,
        documento.texto,
        canal_origen,
        imagenes=documento.imagenes,
        legibilidad=documento.legibilidad,
    )
    respuesta = _a_respuesta(resultado)
    triage_results.guardar_resultado(respuesta.model_dump(mode="json"))
    return respuesta

@app.get("/triage")
def listar_triage():
    return {"items": triage_results.listar_resultados()}

@app.get("/triage/{documento_id}")
def obtener_triage(documento_id: str):
    resultado = triage_results.obtener_resultado(documento_id)

    if resultado is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    return resultado


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


@app.get("/audit/{documento_id}/original")
def original_auditoria(documento_id: str):
    try:
        contenido, tipo = local_audit.obtener_original(documento_id, base=local_audit.DATA_DIR)
    except (DocumentoNoEncontrado, OriginalNoDisponible) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=contenido, media_type=tipo)
@app.get("/rules")
def reglas():
    return load_rules()


@app.put("/rules")
def actualizar_reglas(
    nuevas: dict,
    x_admin_token: str | None = Header(default=None),
    x_editor: str | None = Header(default=None),
):
    esperado = os.getenv("RULES_ADMIN_TOKEN")
    if not esperado:
        raise HTTPException(status_code=503, detail="Edición de reglas deshabilitada: falta RULES_ADMIN_TOKEN")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, esperado):
        raise HTTPException(status_code=401, detail="Token de administrador inválido")
    if not x_editor or not x_editor.strip():
        raise HTTPException(status_code=422, detail="Falta el header X-Editor con quién hace el cambio")
    try:
        cambios = guardar_reglas(nuevas, quien=x_editor.strip())
    except ReglasInvalidas as exc:
        raise HTTPException(status_code=422, detail={"errores": exc.errores}) from exc
    umbral = toca_umbrales(cambios)
    return {
        "actualizado": True,
        "cambios": cambios,
        "umbral_modificado": umbral,
        "aviso": "Cambiaste un umbral: corre el golden set antes de dejarlo." if umbral else None,
    }


@app.get("/metrics")
def metricas():
    return {"documentos_hoy": 0, "urgencias_hoy": 0, "en_revision": 0, "confianza_media": None}