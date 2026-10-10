"""Tests para bucket_actual()."""
import pytest

from agent.storage.buckets import bucket_actual


def test_bucket_actual_dev(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("OCI_BUCKET_DEV", raising=False)
    assert bucket_actual() == "mediflow-dev"


def test_bucket_actual_prod(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.delenv("OCI_BUCKET_PROD", raising=False)
    assert bucket_actual() == "mediflow-prod"


def test_bucket_actual_dev_con_variable(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("OCI_BUCKET_DEV", "mediflow-dev-custom")
    assert bucket_actual() == "mediflow-dev-custom"


def test_bucket_actual_prod_con_variable(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("OCI_BUCKET_PROD", "mediflow-prod-custom")
    assert bucket_actual() == "mediflow-prod-custom"


def test_bucket_actual_env_desconocido(monkeypatch):
    monkeypatch.setenv("ENV", "staging")
    with pytest.raises(ValueError, match="no es válido"):
        bucket_actual()