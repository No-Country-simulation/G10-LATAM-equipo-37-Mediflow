"""Validación de identificadores usados como componentes de rutas."""


def validar_id(documento_id: str) -> str:
    if (not documento_id or len(documento_id) > 128 or documento_id == "."
            or ".." in documento_id or any(c in documento_id for c in '/\\:')
            or any(ord(c) < 32 for c in documento_id)):
        raise ValueError("Identificador no permitido")
    return documento_id
