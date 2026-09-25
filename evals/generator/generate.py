"""Genera las variantes de formato del conjunto de prueba.

El `.txt` que escribe cada persona es la fuente de verdad. Este script produce, a partir de él, el
PDF y el JSON de entrada que pide `plan_golden.csv`, para que las tres versiones digan exactamente
lo mismo y compartan la etiqueta esperada.

    python evals/generator/generate.py               # todo lo que falte
    python evals/generator/generate.py --solo GS-07  # un caso
    python evals/generator/generate.py --forzar      # rehace los que ya existen

El PDF imita un documento clínico impreso: membrete, bloque del paciente, cuerpo y pie de firma.
No es decoración: el modelo tiene que vérselas con encabezados, columnas y sellos, no con texto
plano metido en una hoja.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PLAN = RAIZ / "evals" / "golden" / "plan_golden.csv"
FILES = RAIZ / "evals" / "golden" / "files"

MEMBRETE = "HOSPITAL GENERAL SAN MARTÍN"
SUBMEMBRETE = "Servicio de {especialidad} · Av. Libertador 2350 · Tel. (011) 4555-8000"
PIE = "Documento generado para el conjunto de prueba de MediFlow. Paciente ficticio."


def _tipo_a_titulo(tipo: str) -> str:
    return {
        "Receta Medica": "RECETA MÉDICA",
        "Informe de Estudio por Imagenes": "INFORME DE ESTUDIO POR IMÁGENES",
        "Informe de Laboratorio": "INFORME DE LABORATORIO",
        "Orden de Solicitud de Procedimiento": "ORDEN DE SOLICITUD DE PROCEDIMIENTO",
        "Epicrisis": "EPICRISIS",
        "Certificado Medico": "CERTIFICADO MÉDICO",
    }.get(tipo, "DOCUMENTO CLÍNICO")


def _partir(texto: str) -> tuple[str, list[str]]:
    """Separa un encabezado opcional del cuerpo. Una línea en MAYÚSCULAS al principio se toma como
    título propio del documento y no se repite."""
    lineas = [line.rstrip() for line in texto.strip().splitlines()]
    titulo = ""
    if lineas and lineas[0].isupper() and len(lineas[0]) < 80:
        titulo = lineas.pop(0).strip()
        while lineas and not lineas[0].strip():
            lineas.pop(0)
    return titulo, lineas


def escribir_pdf(destino: Path, texto: str, fila: dict) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

    base = getSampleStyleSheet()
    membrete = ParagraphStyle("membrete", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=13,
                              alignment=TA_CENTER, textColor=colors.HexColor("#1B2A4A"))
    submembrete = ParagraphStyle("sub", parent=base["Normal"], fontSize=7.5, alignment=TA_CENTER,
                                 textColor=colors.HexColor("#5A6270"))
    titulo = ParagraphStyle("titulo", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=11,
                            alignment=TA_CENTER, spaceBefore=10, spaceAfter=10)
    cuerpo = ParagraphStyle("cuerpo", parent=base["Normal"], fontSize=9.5, leading=14, alignment=TA_JUSTIFY)
    campo = ParagraphStyle("campo", parent=cuerpo, fontName="Helvetica-Bold", spaceBefore=3)
    pie = ParagraphStyle("pie", parent=base["Normal"], fontSize=6.5, alignment=TA_CENTER,
                         textColor=colors.HexColor("#9AA1AC"))

    propio, lineas = _partir(texto)
    doc = SimpleDocTemplate(str(destino), pagesize=A4, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                            leftMargin=2.2 * cm, rightMargin=2.2 * cm, title=fila["id"])
    s = [Paragraph(MEMBRETE, membrete),
         Paragraph(SUBMEMBRETE.format(especialidad=fila.get("cuadro", "") and "Clínica Médica" or "Clínica Médica"),
                   submembrete),
         Spacer(1, 6), HRFlowable(width="100%", color=colors.HexColor("#C9CFD9")),
         Paragraph(propio or _tipo_a_titulo(fila["tipo_documento"]), titulo)]

    for linea in lineas:
        if not linea.strip():
            s.append(Spacer(1, 5))
            continue
        # "Paciente: Ana Pérez" se destaca; el resto va como párrafo
        estilo = campo if re.match(r"^[A-ZÁÉÍÓÚÑ][\w áéíóúñ/()-]{2,28}:", linea.strip()) else cuerpo
        s.append(Paragraph(linea.strip().replace("&", "&amp;").replace("<", "&lt;"), estilo))

    s += [Spacer(1, 26), HRFlowable(width="45%", color=colors.HexColor("#5A6270"), hAlign="RIGHT"),
          Paragraph("Firma y sello del profesional", ParagraphStyle(
              "firma", parent=base["Normal"], fontSize=7.5, alignment=2,
              textColor=colors.HexColor("#5A6270"))),
          Spacer(1, 14), Paragraph(PIE, pie)]
    doc.build(s)


def escribir_json(destino: Path, texto: str, fila: dict) -> None:
    """Entrada del contrato: el mismo documento como lo mandaría otro sistema."""
    destino.write_text(json.dumps({
        "documento_id": fila["id"],
        "tipo_archivo": "TEXTO",
        "documento_texto": texto.strip(),
        "canal_origen": "Sistema_Laboratorio" if "Laboratorio" in fila["tipo_documento"] else "HIS_Integracion",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Genera los PDF y los JSON del conjunto de prueba.")
    p.add_argument("--solo", nargs="+", metavar="ID")
    p.add_argument("--forzar", action="store_true", help="rehace los archivos que ya existen")
    args = p.parse_args()

    filas = list(csv.DictReader(open(PLAN, encoding="utf-8-sig")))
    if args.solo:
        pedidos = {x.upper() for x in args.solo}
        filas = [f for f in filas if f["id"].upper() in pedidos]

    hechos, faltan, saltados = [], [], []
    for fila in filas:
        if fila["origen"] == "equipo":  # las manuscritas se fotografían, no se generan
            continue
        origen = FILES / f"{fila['id']}.txt"
        if not origen.exists():
            if fila["formato_pdf"] == "si" or fila["formato_json"] == "si":
                faltan.append(fila["id"])
            continue
        texto = origen.read_text(encoding="utf-8")
        for bandera, extension, escribir in [("formato_pdf", ".pdf", escribir_pdf),
                                             ("formato_json", ".json", escribir_json)]:
            if fila[bandera] != "si":
                continue
            destino = FILES / f"{fila['id']}{extension}"
            if destino.exists() and not args.forzar:
                saltados.append(destino.name)
                continue
            escribir(destino, texto, fila)
            hechos.append(destino.name)

    print(f"generados: {len(hechos)}")
    for h in hechos:
        print("  ", h)
    if saltados:
        print(f"ya existían ({len(saltados)}): usa --forzar para rehacerlos")
    if faltan:
        print(f"sin .txt todavía ({len(faltan)}): {', '.join(faltan)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

