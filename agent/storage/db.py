"""Conexión a Autonomous AI Database con python-oracledb y wallet."""
import os


def connect():
    import oracledb

    return oracledb.connect(
        user=os.getenv("ADB_USER"),
        password=os.getenv("ADB_PASSWORD"),
        dsn=os.getenv("ADB_DSN"),
        config_dir=os.getenv("ADB_WALLET_DIR", "./wallet"),
        wallet_location=os.getenv("ADB_WALLET_DIR", "./wallet"),
        wallet_password=os.getenv("ADB_WALLET_PASSWORD"),
    )


# TODO sprint 2: guardar_resultado(documento_id, resultado_json), listar_cola_humana(), guardar_auditoria(...)
