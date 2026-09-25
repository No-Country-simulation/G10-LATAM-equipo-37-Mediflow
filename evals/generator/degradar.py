"""Degrada documentos para probar la puerta de legibilidad.

Produce las variantes de imagen que pide `plan_golden.csv`: `GS-NN_foto.png` simula la foto que un
auxiliar toma con el teléfono, y `GS-NN_escaneado.png` simula el escáner de admisiones. El nivel de
la columna `nivel_legibilidad` decide cuánto se castiga la imagen.

    python evals/generator/degradar.py                # todo lo que falte
    python evals/generator/degradar.py --solo GS-12
    python evals/generator/degradar.py --forzar

Usa Augraphy si está instalado, porque sus efectos de papel y tinta son más realistas. Si no está,
cae a una tubería propia con Pillow que produce el mismo tipo de daño. Las dos rutas respetan los
tres niveles, así que el conjunto se puede regenerar en cualquier máquina.

Qué debe lograr cada nivel, medido contra los umbrales de `rules.yaml`:
  leve    legibilidad >= 0,70, el documento se procesa normal
  media   entre 0,40 y 0,70, se extrae lo posible y va a revisión humana con AMB-4
  severa  por debajo de 0,40, revisión humana con el motivo de solicitar nueva captura
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PLAN = RAIZ / "evals" / "golden" / "plan_golden.csv"
FILES = RAIZ / "evals" / "golden" / "files"

# (desenfoque, ruido, contraste, rotación, calidad JPEG, sombra, escala)
# La escala es la que más pesa: simula la resolución que se pierde en una foto lejana o en un
# escaneo a pocos puntos por pulgada, y es lo que de verdad castiga al OCR.
# Calibrado midiendo con OCR cuánto texto sobrevive: leve casi todo, media algo más de la mitad,
# severa casi nada. Si se cambian estos números hay que volver a medir, no mirar a ojo.
NIVELES = {
    "leve": (0.4, 5, 0.97, 0.5, 90, 0.05, 1.00),
    "media": (1.6, 16, 0.75, 1.4, 42, 0.16, 0.22),
    "severa": (2.6, 30, 0.58, 3.2, 25, 0.30, 0.13),
}


def _pagina_desde_pdf(ruta: Path, dpi: int = 200):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    from PIL import Image

    doc = fitz.open(ruta)
    try:
        pix = doc[0].get_pixmap(dpi=dpi)
        return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    finally:
        doc.close()


def _pagina_desde_texto(texto: str, ancho: int = 1240, alto: int = 1754):
    """Respaldo cuando todavía no hay PDF: dibuja el texto en una hoja A4 a 150 ppp."""
    from PIL import Image, ImageDraw, ImageFont

    imagen = Image.new("RGB", (ancho, alto), "white")
    dibujo = ImageDraw.Draw(imagen)
    try:
        fuente = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except OSError:
        fuente = ImageFont.load_default()
    y = 120
    for linea in texto.strip().splitlines():
        for trozo in [linea[i:i + 78] for i in range(0, max(len(linea), 1), 78)]:
            dibujo.text((110, y), trozo, fill=(20, 20, 20), font=fuente)
            y += 32
            if y > alto - 140:
                return imagen
        y += 4
    return imagen


def _sombra(imagen, fuerza: float):
    """Iluminación despareja: es lo que más distingue una foto de un escaneo."""
    from PIL import Image, ImageDraw, ImageFilter

    ancho, alto = imagen.size
    capa = Image.new("L", (ancho, alto), 255)
    dibujo = ImageDraw.Draw(capa)
    x0 = random.randint(-ancho // 3, ancho // 2)
    dibujo.polygon([(x0, 0), (x0 + ancho // 2, 0), (x0 + ancho, alto), (x0 + ancho // 3, alto)],
                   fill=int(255 * (1 - fuerza)))
    capa = capa.filter(ImageFilter.GaussianBlur(ancho // 12))
    return Image.composite(imagen, Image.new("RGB", imagen.size, (0, 0, 0)), capa)


def _con_pillow(imagen, nivel: str, variante: str):
    from PIL import Image, ImageEnhance, ImageFilter

    desenfoque, ruido, contraste, giro, calidad, sombra, escala = NIVELES[nivel]
    if variante == "foto":
        imagen = _sombra(imagen, sombra)
        imagen = imagen.rotate(random.uniform(-giro, giro), expand=False, fillcolor=(245, 245, 245),
                               resample=Image.BICUBIC)
    else:  # el escáner deja la hoja derecha, pero lava el contraste y mete polvo
        imagen = imagen.convert("L").convert("RGB")
        imagen = imagen.rotate(random.uniform(-giro / 3, giro / 3), expand=False, fillcolor=(250, 250, 250),
                               resample=Image.BICUBIC)
    imagen = imagen.filter(ImageFilter.GaussianBlur(desenfoque))
    imagen = ImageEnhance.Contrast(imagen).enhance(contraste)
    imagen = ImageEnhance.Brightness(imagen).enhance(1.0 + (0.12 if variante == "foto" else -0.05))

    pixeles = imagen.load()
    ancho, alto = imagen.size
    for _ in range((ancho * alto) // max(400 - ruido * 8, 40)):
        x, y = random.randrange(ancho), random.randrange(alto)
        delta = random.randint(-ruido * 4, ruido * 4)
        r, g, b = pixeles[x, y]
        pixeles[x, y] = (max(0, min(255, r + delta)), max(0, min(255, g + delta)), max(0, min(255, b + delta)))

    if escala < 1.0:  # se pierde resolución y se recupera el tamaño: el texto queda pastoso
        chico = imagen.resize((max(int(ancho * escala), 8), max(int(alto * escala), 8)), Image.BILINEAR)
        imagen = chico.resize((ancho, alto), Image.BICUBIC)

    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=calidad)  # el artefacto de compresión es parte del daño
    return Image.open(buffer).convert("RGB")


def _con_augraphy(imagen, nivel: str, variante: str):
    import numpy as np
    from augraphy import AugraphyPipeline, default_augraphy_pipeline  # noqa: F401
    from PIL import Image

    pipeline = default_augraphy_pipeline()
    salida = pipeline(np.array(imagen))
    resultado = Image.fromarray(salida if isinstance(salida, np.ndarray) else salida["output"])
    # Augraphy simula papel y tinta; el nivel lo ajusta la tubería propia encima
    return _con_pillow(resultado.convert("RGB"), nivel, variante)


def degradar(imagen, nivel: str, variante: str, usar_augraphy: bool):
    if usar_augraphy:
        try:
            return _con_augraphy(imagen, nivel, variante), "augraphy"
        except Exception as exc:  # noqa: BLE001 - si falla, la tubería propia hace el trabajo
            print(f"     (Augraphy no disponible: {type(exc).__name__}; se usa Pillow)")
    return _con_pillow(imagen, nivel, variante), "pillow"


def main() -> int:
    p = argparse.ArgumentParser(description="Degrada documentos para la puerta de legibilidad.")
    p.add_argument("--solo", nargs="+", metavar="ID")
    p.add_argument("--forzar", action="store_true")
    p.add_argument("--sin-augraphy", action="store_true", help="usa solo Pillow")
    p.add_argument("--semilla", type=int, default=37, help="para que la degradación sea reproducible")
    args = p.parse_args()
    random.seed(args.semilla)

    filas = [f for f in csv.DictReader(open(PLAN, encoding="utf-8-sig")) if f["variante_imagen"]]
    if args.solo:
        pedidos = {x.upper() for x in args.solo}
        filas = [f for f in filas if f["id"].upper() in pedidos]

    hechos, faltan, saltados = [], [], []
    for fila in filas:
        cid, variante = fila["id"], fila["variante_imagen"]
        nivel = fila["nivel_legibilidad"] or "media"
        if nivel not in NIVELES:
            print(f"  {cid}: nivel '{nivel}' desconocido, se salta")
            continue
        sufijo = "_foto" if variante == "foto" else "_escaneado"
        destino = FILES / f"{cid}{sufijo}.png"
        if destino.exists() and not args.forzar:
            saltados.append(destino.name)
            continue

        pdf, txt = FILES / f"{cid}.pdf", FILES / f"{cid}.txt"
        if pdf.exists():
            pagina = _pagina_desde_pdf(pdf)
        elif txt.exists():
            pagina = _pagina_desde_texto(txt.read_text(encoding="utf-8"))
        else:
            faltan.append(cid)
            continue

        print(f"  {cid} · {variante} · {nivel}")
        imagen, motor = degradar(pagina, nivel, variante, not args.sin_augraphy)
        imagen.save(destino)
        hechos.append(f"{destino.name} ({motor})")

    print(f"\ngeneradas: {len(hechos)}")
    for h in hechos:
        print("  ", h)
    if saltados:
        print(f"ya existían ({len(saltados)}): usa --forzar para rehacerlas")
    if faltan:
        print(f"sin documento todavía ({len(faltan)}): {', '.join(faltan)}")
    print("\nRevisar a ojo antes de dar por buenas: una imagen 'media' tiene que seguir siendo legible "
          "para una persona, y una 'severa' no.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
