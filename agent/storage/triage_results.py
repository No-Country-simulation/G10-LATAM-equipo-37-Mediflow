
"""Persistencia SQLite de resultados de triaje."""
import json
import os
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
DB_PATH = Path(
    os.getenv("MEDIFLOW_TRIAGE_DB", RAIZ / "data" / "triage_results.sqlite3")
)


def _conectar(db_path: Path | None = None) -> sqlite3.Connection:
    """Abre a base de dados e garante que a tabela existe."""
    caminho = Path(db_path) if db_path is not None else DB_PATH
    caminho.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS triage_results (
            documento_id TEXT PRIMARY KEY,
            destino TEXT NOT NULL,
            score REAL NOT NULL,
            resultado_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def guardar_resultado(
    resultado: dict, db_path: Path | None = None
) -> None:
    """Guarda ou atualiza o resultado de um documento."""
    documento_id = resultado["documento_id"]
    destino = resultado["decision_enrutamiento"]["destino_principal"]
    score = resultado["score_confianza"]
    resultado_json = json.dumps(resultado, ensure_ascii=False)

    with _conectar(db_path) as conn:
        conn.execute(
            """
            INSERT INTO triage_results
                (documento_id, destino, score, resultado_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(documento_id) DO UPDATE SET
                destino = excluded.destino,
                score = excluded.score,
                resultado_json = excluded.resultado_json,
                created_at = CURRENT_TIMESTAMP
            """,
            (documento_id, destino, score, resultado_json),
        )


def listar_resultados(db_path: Path | None = None) -> list[dict]:
    """Lista os resultados com os campos necessários para a fila."""
    with _conectar(db_path) as conn:
        filas = conn.execute(
            """
            SELECT documento_id, destino, score, created_at
            FROM triage_results
            ORDER BY created_at DESC, documento_id
            """
        ).fetchall()

    return [dict(fila) for fila in filas]


def obtener_resultado(
    documento_id: str, db_path: Path | None = None
) -> dict | None:
    """Recupera o resultado completo de um documento."""
    with _conectar(db_path) as conn:
        fila = conn.execute(
            """
            SELECT resultado_json
            FROM triage_results
            WHERE documento_id = ?
            """,
            (documento_id,),
        ).fetchone()

    if fila is None:
        return None

    return json.loads(fila["resultado_json"])