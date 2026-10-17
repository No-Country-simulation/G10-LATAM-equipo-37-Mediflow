"""Regresión de la ruta de importación usada por el comando de CI."""
import os
import subprocess
import sys
from pathlib import Path


def test_entrypoint_encuentra_agent_fuera_del_repo(tmp_path):
    raiz = Path(__file__).resolve().parents[1]
    script = raiz / "evals" / "run.py"
    codigo = """
import importlib.util
import runpy
import sys
from pathlib import Path
script = Path(sys.argv[1])
raiz = script.parent.parent
sys.path = [str(script.parent)] + [p for p in sys.path if p and Path(p).resolve() != raiz]
runpy.run_path(str(script), run_name="eval_entry_test")
assert Path(importlib.util.find_spec("agent").origin).resolve() == raiz / "agent" / "__init__.py"
"""
    entorno = dict(os.environ)
    entorno.pop("PYTHONPATH", None)
    resultado = subprocess.run([sys.executable, "-c", codigo, str(script)],
                               cwd=tmp_path, env=entorno, capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stderr
