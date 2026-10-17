"""Señal conservadora AMB-5 para texto con encabezados documentales explícitos."""
import re
import unicodedata


def detectar_documentos_multiples(texto: str) -> bool:
    texto = "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                    if unicodedata.category(c) != "Mn")
    titulos = list(re.finditer(
        r"(?m)^\s*(receta(?:\s+medica)?|certificado(?:\s+medico)?|epicrisis|"
        r"informe\s+de\s+(?:alta|laboratorio|estudio\s+por\s+imagenes)|"
        r"orden\s+de\s+(?:solicitud\s+de\s+)?procedimiento)\s*[:\-]?\s*$", texto))
    if len(titulos) < 2:
        return False
    tipos = {m.group(1).split()[0] for m in titulos}
    if len(tipos) > 1:
        return True
    # Un encabezado repetido por paginación no basta. Dos pacientes distintos sí.
    pacientes = set()
    for i, titulo in enumerate(titulos):
        fin = titulos[i + 1].start() if i + 1 < len(titulos) else len(texto)
        segmento = texto[titulo.end():fin]
        paciente = re.search(r"(?m)^\s*paciente\s*:\s*([^\n]+)", segmento)
        if paciente:
            pacientes.add(paciente.group(1).strip())
    return len(pacientes) > 1
