# anonimizar.py
# Anonimiza los archivos del golden set de MediFlow.
# - Hashing SHA-256 completo (64 chars) + Salt desde variable de entorno.
# - Pseudonimizacion: Paciente Ficticio NNN / Medico Ficticio NNN.
# - Sobrescribe los archivos originales (borra/reemplaza).
#
# Uso: python evals/generator/anonimizar.py

import hashlib
import os
import re
from pathlib import Path

# ─── Config ─────────────────────────────────────────────────────────────────
SALT = os.environ.get("MEDIFLOW_HASH_SALT")
if not SALT:
    raise SystemExit(
        "ERROR: La variable de entorno MEDIFLOW_HASH_SALT no esta definida.\n"
        "Agregala a tu .env antes de ejecutar este script."
    )

CARPETA = Path(__file__).resolve().parents[1] / "golden" / "files"
ARCHIVOS = ["GS-01.txt", "GS-09.txt", "GS-17.txt", "GS-25.txt", "FA-03.txt"]

# ─── Mapeo de nombres reales -> "Paciente/Medico Ficticio NNN" ──────────────
# Los IDs se asignan en orden. Mantener consistencia si agregas mas.
MAPEO_NOMBRES = {
    # Pacientes
    "Roberto Fernández": "Paciente Ficticio 001",
    "Roberto Fernandez": "Paciente Ficticio 001",
    "Lucía Benítez": "Paciente Ficticio 002",
    "Lucia Benitez": "Paciente Ficticio 002",
    "Elena Ríos": "Paciente Ficticio 003",
    "Elena Rios": "Paciente Ficticio 003",
    "Marcos Aguirre": "Paciente Ficticio 004",
    "María Fernanda López": "Paciente Ficticio 005",
    "Maria Fernanda Lopez": "Paciente Ficticio 005",
    # Medicos
    "Dra. Marta Giménez": "Dra. Ficticia 001",
    "Dra. Marta Gimenez": "Dra. Ficticia 001",
    "Dr. Andrés Salas": "Dr. Ficticio 002",
    "Dr. Andres Salas": "Dr. Ficticio 002",
    "Dr. Pablo Herrera": "Dr. Ficticio 003",
    "Dra. Silvia Romero": "Dra. Ficticia 004",
}


def hashear_numero(match: re.Match) -> str:
    """Reemplaza un numero por su hash SHA-256 completo (64 chars) con Salt."""
    numero_limpio = re.sub(r"[^0-9]", "", match.group(0))
    if not numero_limpio:
        return match.group(0)
    input_con_salt = numero_limpio + SALT
    return hashlib.sha256(input_con_salt.encode()).hexdigest()


def anonimizar(texto: str) -> str:
    """Aplica hashing completo a numeros y pseudonimizacion a nombres."""
    # 1. Matriculas MP XXXXX -> MP <hash>
    texto = re.sub(r"\bMP\s+(\d{4,6})\b", lambda m: "MP " + hashear_numero(m), texto)

    # 2. DNI (XX.XXX.XXX) -> <hash>
    texto = re.sub(r"\b\d{1,2}\.\d{3}\.\d{3}\b", hashear_numero, texto)

    # 3. Numero de afiliado (XX-XXXX-XX) -> <hash>
    texto = re.sub(r"\b\d{2}-\d{4}-\d{2}\b", hashear_numero, texto)

    # 4. Pseudonimizar nombres (pacientes y medicos)
    for real, falso in MAPEO_NOMBRES.items():
        texto = texto.replace(real, falso)

    return texto


def main() -> None:
    print("=== Anonimizador del golden set ===")
    print(f"SALT configurado: {SALT[:8]}...\n")

    for nombre in ARCHIVOS:
        archivo = CARPETA / nombre
        if not archivo.exists():
            print(f"[SKIP] {nombre}: no existe")
            continue

        contenido = archivo.read_text(encoding="utf-8")
        contenido_nuevo = anonimizar(contenido)

        # Hacer backup del original
        backup = archivo.with_suffix(".original.txt")
        if not backup.exists():
            backup.write_text(contenido, encoding="utf-8")
            print(f"[BACKUP] {backup.name}")

        # Sobrescribir con la version anonimizada
        archivo.write_text(contenido_nuevo, encoding="utf-8")
        print(f"[OK] {nombre} anonimizado")

    print("\n=== Listo ===")
    print("Los archivos originales quedaron como .original.txt (backup).")


if __name__ == "__main__":
    main()