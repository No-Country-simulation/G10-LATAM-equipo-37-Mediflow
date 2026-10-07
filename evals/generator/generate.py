"""Genera las variantes de formato del conjunto de prueba.

El `.txt` que escribe cada persona es la fuente de verdad. Este script produce, a partir de él, el
PDF y el JSON de entrada que pide `plan_golden.csv`, para que las tres versiones digan exactamente
lo mismo y compartan la etiqueta esperada.

    python evals/generator/generate.py               # todo lo que falte
    python evals/generator/generate.py --solo GS-07  # un caso
    python evals/generator/generate.py --forzar      # rehace los que ya existen

El PDF dice exactamente lo que dice el .txt, ni una palabra más ni una menos: el membrete, el título
y la firma los escribe cada persona en su texto. El generador solo les da formato de documento
impreso. Una versión anterior agregaba un membrete propio, con dirección y teléfono, y una marca de
"paciente ficticio" al pie, y eso hacía que el PDF y el texto no fueran el mismo documento.

Que los datos son sintéticos está documentado en `evals/DATA.md`, que es su lugar, y nunca dentro
de los documentos: un documento real no trae esa marca y el agente podría usarla para decidir.
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

CAMPO = re.compile(r"^([A-ZÁÉÍÓÚÑ][^:]{0,40}:)(.*)$")


def _es_titulo(linea: str) -> bool:
    letras = [c for c in linea if c.isalpha()]
    return bool(letras) and all(c.isupper() for c in letras) and len(linea) < 90


def _es_tabla(linea: str) -> bool:
    """Una línea con columnas alineadas a espacios, como los resultados de un laboratorio."""
    return re.search(r"\S {3,}\S", linea) is not None


def escribir_pdf(destino: Path, texto: str, fila: dict) -> None:
    """Imprime el .txt tal cual, solo con formato: no agrega ni quita una palabra.

    El membrete, el título, la firma y todo lo demás vienen del texto que escribió cada persona. El
    generador solo decide cómo se ven: las líneas en mayúsculas van en negrita, el encabezado
    centrado, y las tablas en fuente de ancho fijo para que las columnas sigan alineadas.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer

    base = getSampleStyleSheet()
    normal = ParagraphStyle("normal", parent=base["Normal"], fontSize=9.5, leading=13.5, alignment=TA_LEFT)
    negrita = ParagraphStyle("negrita", parent=normal, fontName="Helvetica-Bold")
    cabecera = ParagraphStyle("cabecera", parent=negrita, fontSize=12, leading=15, alignment=TA_CENTER,
                              textColor=colors.HexColor("#1B2A4A"))
    subcabecera = ParagraphStyle("subcabecera", parent=normal, fontSize=8.5, alignment=TA_CENTER,
                                 textColor=colors.HexColor("#3A4250"))
    tabla = ParagraphStyle("tabla", parent=normal, fontName="Courier", fontSize=8, leading=10.5)

    def esc(t: str) -> str:
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lineas = texto.strip("\n").splitlines()
    s = []
    en_cabecera = True  # las primeras líneas, hasta el primer campo o la primera línea en blanco
    for n, linea in enumerate(lineas):
        limpia = linea.rstrip()
        if not limpia.strip():
            en_cabecera = False
            s.append(Spacer(1, 6))
            continue
        if en_cabecera and ":" not in limpia:
            s.append(Paragraph(esc(limpia.strip()), cabecera if n == 0 else subcabecera))
            continue
        en_cabecera = False
        partes = [x for x in re.split(r" {3,}", limpia.strip()) if x]
        campos = [CAMPO.match(x) for x in partes]
        if all(campos):
            # "Edad: 68 años     Sexo: Masculino": uno o varios campos en la misma línea
            unidos = "&nbsp;&nbsp;&nbsp;&nbsp;".join(f"<b>{esc(m.group(1))}</b>{esc(m.group(2))}" for m in campos)
            s.append(Paragraph(unidos, normal))
        elif _es_tabla(limpia):
            s.append(Preformatted(limpia, tabla))
        elif _es_titulo(limpia.strip()):
            s.append(Paragraph(esc(limpia.strip()), negrita))
        else:
            s.append(Paragraph(esc(limpia.strip()), normal))

    doc = SimpleDocTemplate(str(destino), pagesize=A4, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            leftMargin=2.2 * cm, rightMargin=2.2 * cm, title=fila["id"])
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


