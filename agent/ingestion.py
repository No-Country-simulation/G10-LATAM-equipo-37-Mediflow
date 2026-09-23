"""Ingreso seguro de documentos clínicos.

Este módulo normaliza archivos antes de enviarlos al grafo. No interpreta
imágenes médicas ni completa datos clínicos: solamente extrae texto cuando
existe evidencia en el archivo y marca los casos que requieren revisión.
"""
from __future__ import annotations

import io
import mimetypes
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = int(os.getenv("MEDIFLOW_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
MAX_PDF_PAGES = int(os.getenv("MEDIFLOW_MAX_PDF_PAGES", "50"))
MAX_TEXT_CHARS = int(os.getenv("MEDIFLOW_MAX_TEXT_CHARS", "2_000_000"))

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
    legibilidad: float
    paginas: int = 0
    requiere_revision: bool = False
    motivo_revision: str | None = None


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
        # Texto y JSON no tienen una firma fiable; se aceptan solo con tipo/extensión
        # coherentes y se decodifican de forma estricta más adelante.
        if declared_type not in {"TEXTO", "JSON"} and extension_type not in {"TEXTO", "JSON"}:
            raise IngestionError("Tipo de archivo no soportado")
        return declared_type or extension_type  # type: ignore[return-value]

    if extension_type and extension_type != sniffed_type:
        raise IngestionError("La extensión no coincide con el contenido del archivo")
    if declared_type and declared_type != sniffed_type:
        raise IngestionError("El tipo MIME no coincide con el contenido del archivo")
    return sniffed_type


def _decode_text(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestionError("El texto debe estar codificado en UTF-8") from exc
    if len(text) > MAX_TEXT_CHARS:
        raise IngestionError("El texto supera el límite permitido")
    return text.replace("\x00", "").strip()


def _extract_pdf(data: bytes) -> tuple[str, int]:
    import fitz  # PyMuPDF

    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - no exponer detalles del archivo
        raise IngestionError("El PDF no se puede leer") from exc
    try:
        if document.page_count == 0:
            raise IngestionError("El PDF no contiene páginas")
        if document.page_count > MAX_PDF_PAGES:
            raise IngestionError(f"El PDF supera el máximo de {MAX_PDF_PAGES} páginas")
        pages = [page.get_text("text").strip() for page in document]
        text = "\n\n".join(page for page in pages if page)
        return text[:MAX_TEXT_CHARS], document.page_count
    finally:
        document.close()


def _extract_image(data: bytes, filename: str | None) -> str:
    """Hace OCR de una imagen documental; nunca intenta diagnosticarla."""
    from PIL import Image
    import pytesseract

    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:  # noqa: BLE001
        raise IngestionError("La imagen no se puede leer") from exc
    try:
        text = pytesseract.image_to_string(image, lang=os.getenv("MEDIFLOW_OCR_LANG", "spa+por+eng"))
    except Exception as exc:  # noqa: BLE001
        raise IngestionError("No fue posible procesar el texto de la imagen") from exc
    return text[:MAX_TEXT_CHARS].strip()


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

    if tipo in {"TEXTO", "JSON"}:
        texto = _decode_text(data)
        return IngestedDocument(tipo, texto, 1.0 if texto else 0.0, requiere_revision=not bool(texto), motivo_revision="Documento vacío" if not texto else None)
    if tipo == "PDF":
        texto, paginas = _extract_pdf(data)
        return IngestedDocument(tipo, texto, 1.0 if texto else 0.0, paginas, not bool(texto), "PDF sin capa de texto; requiere OCR/visión" if not texto else None)

    texto = _extract_image(data, filename)
    return IngestedDocument(tipo, texto, 1.0 if texto else 0.0, 1, not bool(texto), "Imagen sin texto legible" if not texto else None)


__all__ = ["IngestedDocument", "IngestionError", "ingest_document"]
