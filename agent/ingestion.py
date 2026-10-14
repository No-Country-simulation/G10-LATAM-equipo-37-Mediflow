"""Ingreso seguro de documentos clínicos.

Este módulo normaliza archivos antes de enviarlos al grafo. No interpreta imágenes médicas ni
completa datos clínicos: extrae texto cuando hay evidencia en el archivo, renderiza las páginas
que el modelo multimodal necesita ver, y marca los casos que requieren revisión.

Dos reglas que vienen del contrato (docs/api-contract.md):

1. La legibilidad de imágenes y PDF escaneados NO se fija aquí. Se devuelve `None` y la calcula
   `agent/nodes/normalizar.py`, que es donde vive la puerta de legibilidad (paquete N2-08). Si se
   fijara 1.0 por el solo hecho de que el OCR sacó algo, una foto ilegible pasaría como perfecta.
2. Las imágenes no se descartan. El OCR es apoyo; el modelo multimodal tiene que ver la página.
"""
from __future__ import annotations

import base64
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

MAX_BYTES = int(os.getenv("MEDIFLOW_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
MAX_PDF_PAGES = int(os.getenv("MEDIFLOW_MAX_PDF_PAGES", "50"))
MAX_TEXT_CHARS = int(os.getenv("MEDIFLOW_MAX_TEXT_CHARS", "2000000"))
# Páginas que se le mandan al modelo. Más que esto no aporta y multiplica el costo por documento.
MAX_PAGINAS_AL_MODELO = int(os.getenv("MEDIFLOW_MAX_PAGINAS_MODELO", "4"))
# Lado mayor al que se reduce cada página antes de enviarla. Suficiente para leer una receta.
MAX_LADO_PX = int(os.getenv("MEDIFLOW_MAX_LADO_PX", "1600"))
OCR_LANG = os.getenv("MEDIFLOW_OCR_LANG", "spa+por+eng")

_ALLOWED_MIME = {
    "application/pdf": "PDF",
    "text/plain": "TEXTO",
    "application/json": "JSON",
    "image/jpeg": "IMAGEN",
    "image/png": "IMAGEN",
    "image/tiff": "IMAGEN",
    "image/webp": "IMAGEN",
}
_ALLOWED_EXTENSIONS = {
    ".pdf": "PDF",
    ".txt": "TEXTO",
    ".json": "JSON",
    ".jpg": "IMAGEN",
    ".jpeg": "IMAGEN",
    ".png": "IMAGEN",
    ".tif": "IMAGEN",
    ".tiff": "IMAGEN",
    ".webp": "IMAGEN",
}


class IngestionError(ValueError):
    """Error seguro y apto para devolver al cliente sin revelar contenido."""


@dataclass(frozen=True)
class IngestedDocument:
    tipo_archivo: str
    texto: str
    # None cuando la calcula el grafo: imagen o PDF escaneado. Float solo para texto digital.
    legibilidad: float | None = None
    # Páginas renderizadas en PNG base64, listas para el modelo multimodal.
    imagenes: list[str] = field(default_factory=list)
    paginas: int = 0
    requiere_revision: bool = False
    motivo_revision: str | None = None
    texto_por_ocr: bool = False


# --------------------------------------------------------------------------- validación de entrada
def _sniff_type(data: bytes) -> str:
    """Detecta el formato por firma, no por el nombre enviado por el cliente."""
    if data.startswith(b"%PDF-"):
        return "PDF"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "IMAGEN"
    if data.startswith(b"\xff\xd8\xff"):
        return "IMAGEN"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "IMAGEN"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "IMAGEN"
    return "DESCONOCIDO"


def _validate_upload(filename: str | None, content_type: str | None, data: bytes) -> str:
    if not data:
        raise IngestionError("El archivo está vacío")
    if len(data) > MAX_BYTES:
        raise IngestionError(f"El archivo supera el límite de {MAX_BYTES} bytes")

    extension_type = _ALLOWED_EXTENSIONS.get(Path(filename or "").suffix.lower())
    declared_type = _ALLOWED_MIME.get((content_type or "").split(";", 1)[0].lower())
    sniffed_type = _sniff_type(data)

    if sniffed_type == "DESCONOCIDO":
        # Texto y JSON no tienen una firma fiable; se aceptan solo con tipo o extensión coherentes
        # y se decodifican de forma estricta más adelante.
        if declared_type not in {"TEXTO", "JSON"} and extension_type not in {"TEXTO", "JSON"}:
            raise IngestionError("Tipo de archivo no soportado")
        return declared_type or extension_type  # type: ignore[return-value]

    if extension_type and extension_type != sniffed_type:
        raise IngestionError("La extensión no coincide con el contenido del archivo")
    if declared_type and declared_type != sniffed_type:
        raise IngestionError("El tipo MIME no coincide con el contenido del archivo")
    return sniffed_type


# --------------------------------------------------------------------------- texto y JSON
def _decode_text(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestionError("El texto debe estar codificado en UTF-8") from exc
    if len(text) > MAX_TEXT_CHARS:
        raise IngestionError("El texto supera el límite permitido")
    return text.replace("\x00", "").strip()


def _texto_desde_json(crudo: str) -> str:
    """El contrato del brief manda el documento dentro de `documento_texto`."""
    try:
        datos = json.loads(crudo)
    except json.JSONDecodeError as exc:
        raise IngestionError("El JSON no es válido") from exc
    if isinstance(datos, dict):
        for clave in ("documento_texto", "texto", "contenido"):
            valor = datos.get(clave)
            if isinstance(valor, str) and valor.strip():
                return valor.strip()
        raise IngestionError("El JSON no contiene documento_texto")
    raise IngestionError("El JSON debe ser un objeto con documento_texto")


# --------------------------------------------------------------------------- imágenes y OCR
def _a_png_base64(imagen) -> str:
    """Reduce la página y la codifica. Devolver base64 evita escribir archivos temporales."""
    from PIL import Image

    copia = imagen.convert("RGB")
    lado = max(copia.size)
    if lado > MAX_LADO_PX:
        escala = MAX_LADO_PX / lado
        copia = copia.resize((int(copia.width * escala), int(copia.height * escala)), Image.LANCZOS)
    buffer = io.BytesIO()
    copia.save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _ocr(imagen) -> str:
    """OCR de apoyo. Si tesseract no está instalado, se sigue sin texto: decide el modelo."""
    try:
        import pytesseract
    except ImportError:
        return ""
    try:
        return pytesseract.image_to_string(imagen, lang=OCR_LANG)[:MAX_TEXT_CHARS].strip()
    except Exception:  # noqa: BLE001 - binario ausente, idioma faltante o imagen rara
        return ""


def _abrir_imagen(data: bytes):
    from PIL import Image

    try:
        Image.open(io.BytesIO(data)).verify()  # detecta archivos corruptos antes de cargarlos
        imagen = Image.open(io.BytesIO(data))
        imagen.load()
        return imagen
    except Exception as exc:  # noqa: BLE001 - no exponer detalles del archivo
        raise IngestionError("La imagen no se puede leer") from exc


# --------------------------------------------------------------------------- PDF
def _extraer_pdf(data: bytes) -> tuple[str, list[str], int, bool]:
    """Devuelve (texto, imágenes, páginas, texto_por_ocr).

    PDF con capa de texto: se extrae el texto y no se renderiza nada.
    PDF escaneado: se renderizan las primeras páginas para el modelo y el OCR queda de apoyo.
    """
    try:  # PyMuPDF renombró el paquete; se aceptan las dos formas
        import pymupdf as fitz
    except ImportError:
        import fitz

    try:
        documento = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - no exponer detalles del archivo
        raise IngestionError("El PDF no se puede leer") from exc

    try:
        if documento.page_count == 0:
            raise IngestionError("El PDF no contiene páginas")
        if documento.page_count > MAX_PDF_PAGES:
            raise IngestionError(f"El PDF supera el máximo de {MAX_PDF_PAGES} páginas")

        paginas = [pagina.get_text("text").strip() for pagina in documento]
        texto = "\n\n".join(p for p in paginas if p)
        if texto:
            return texto[:MAX_TEXT_CHARS], [], documento.page_count, False

        from PIL import Image

        imagenes, textos_ocr = [], []
        for pagina in documento[:MAX_PAGINAS_AL_MODELO]:
            pix = pagina.get_pixmap(dpi=200)
            imagen = Image.open(io.BytesIO(pix.tobytes("png")))
            imagenes.append(_a_png_base64(imagen))
            textos_ocr.append(_ocr(imagen))
        texto_ocr = "\n\n".join(t for t in textos_ocr if t)
        return texto_ocr[:MAX_TEXT_CHARS], imagenes, documento.page_count, bool(texto_ocr)
    finally:
        documento.close()


# --------------------------------------------------------------------------- entrada única
def ingest_document(
    data: bytes,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    expected_type: str | None = None,
) -> IngestedDocument:
    """Valida y normaliza un documento sin persistirlo ni emitir datos sensibles."""
    tipo = _validate_upload(filename, content_type, data)
    if expected_type and expected_type != tipo:
        raise IngestionError("El tipo declarado no coincide con el archivo")

    if tipo == "TEXTO":
        texto = _decode_text(data)
        return IngestedDocument(
            tipo_archivo="TEXTO",
            texto=texto,
            legibilidad=1.0 if texto else 0.0,
            requiere_revision=not texto,
            motivo_revision=None if texto else "Documento vacío",
        )

    if tipo == "JSON":
        texto = _texto_desde_json(_decode_text(data))
        return IngestedDocument(tipo_archivo="JSON", texto=texto, legibilidad=1.0)

    if tipo == "PDF":
        texto, imagenes, paginas, por_ocr = _extraer_pdf(data)
        escaneado = bool(imagenes)
        return IngestedDocument(
            tipo_archivo="PDF",
            texto=texto,
            # PDF con capa de texto: legible con certeza. Escaneado: lo decide el grafo.
            legibilidad=None if escaneado else (1.0 if texto else 0.0),
            imagenes=imagenes,
            paginas=paginas,
            requiere_revision=not texto and not imagenes,
            motivo_revision=None if (texto or imagenes) else "PDF sin texto ni páginas legibles",
            texto_por_ocr=por_ocr,
        )

    imagen = _abrir_imagen(data)
    texto_ocr = _ocr(imagen)
    return IngestedDocument(
        tipo_archivo="IMAGEN",
        texto=texto_ocr,
        legibilidad=None,  # la calcula normalizar.py: es la puerta de legibilidad (N2-08)
        imagenes=[_a_png_base64(imagen)],
        paginas=1,
        texto_por_ocr=bool(texto_ocr),
    )


__all__ = ["IngestedDocument", "IngestionError", "ingest_document"]
