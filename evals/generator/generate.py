"""Generador de documentos clínicos sintéticos.

Por cada tipo de documento e idioma: texto, JSON con el contrato, PDF digital y una imagen "escaneada" degradada.
"""
import argparse
import json
from pathlib import Path

TIPOS = [
    "Receta Medica",
    "Informe de Estudio por Imagenes",
    "Orden de Solicitud de Procedimiento",
    "Epicrisis",
    "Certificado Medico",
]
IDIOMAS = ["es", "pt", "en"]


def generar_texto(tipo: str, idioma: str, i: int) -> str:
    # TODO sprint 1: agent.llm.adapter.complete con una plantilla por tipo e instrucciones de variedad
    # (urgente sí/no, ambiguo sí/no, dosis fuera de rango, campos faltantes, datos contradictorios).
    return f"[{tipo} sintético {i} en {idioma}]"


def a_pdf(texto: str, destino: Path) -> None:
    # TODO sprint 1: ReportLab con membrete de hospital ficticio.
    destino.write_text(texto, encoding="utf-8")


def a_imagen_degradada(pdf: Path, destino: Path) -> None:
    # TODO sprint 1: PyMuPDF renderiza, Augraphy o Pillow degrada (ruido, inclinación, desenfoque, baja resolución).
    pass


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=12, help="documentos por tipo")
    p.add_argument("--salida", default="evals/golden")
    args = p.parse_args()
    salida = Path(args.salida)
    (salida / "files").mkdir(parents=True, exist_ok=True)
    lineas = []
    k = 0
    for tipo in TIPOS:
        for i in range(args.n):
            idioma = IDIOMAS[i % len(IDIOMAS)]
            k += 1
            doc_id = f"SYN-{k:04d}"
            texto = generar_texto(tipo, idioma, i)
            lineas.append({
                "documento_id": doc_id, "tipo_archivo": "TEXTO", "idioma": idioma, "fuente": "generador",
                "documento_texto": texto, "esperado": {"tipo_documento": tipo}, "revisado_por": [],
            })
    with open(salida / "golden_v0_borrador.jsonl", "w", encoding="utf-8") as f:
        for linea in lineas:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
    print(f"{len(lineas)} documentos borrador en {salida}/golden_v0_borrador.jsonl. Falta la doble revisión.")


if __name__ == "__main__":
    main()
