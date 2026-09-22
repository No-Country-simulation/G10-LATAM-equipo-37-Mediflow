"""Carga de reglas. Hoy desde YAML; en el sprint 3 desde la tabla rules de ADB."""
from functools import lru_cache
from pathlib import Path

import yaml

RULES_PATH = Path(__file__).with_name("rules.yaml")


@lru_cache(maxsize=1)
def load_rules() -> dict:
    with open(RULES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)
