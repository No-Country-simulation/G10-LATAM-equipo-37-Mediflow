"""Tests for Phoenix default deactivation and sensitive data exclusion."""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_phoenix_state():
    """Reset Phoenix global state before each test."""
    import agent.llm.phoenix as phoenix_module
    phoenix_module._phoenix_initialized = False
    phoenix_module._phoenix_app = None
    yield
    phoenix_module._phoenix_initialized = False
    phoenix_module._phoenix_app = None


def test_phoenix_disabled_by_default():
    """Phoenix should be disabled by default (opt-in)."""
    # Ensure PHOENIX_ENABLED is not set
    with patch.dict(os.environ, {}, clear=True):
        # Remove any existing PHOENIX_ENABLED
        os.environ.pop("PHOENIX_ENABLED", None)
        os.environ.pop("ENV", None)
        
        from agent.llm.phoenix import _phoenix_enabled
        
        assert _phoenix_enabled() is False


def test_phoenix_disabled_when_env_prod():
    """Phoenix should be disabled when ENV=prod and PHOENIX_ENABLED not set."""
    with patch.dict(os.environ, {"ENV": "prod"}, clear=True):
        from agent.llm.phoenix import _phoenix_enabled
        
        assert _phoenix_enabled() is False


def test_phoenix_enabled_explicit_true():
    """Phoenix should be enabled when PHOENIX_ENABLED=true explicitly."""
    with patch.dict(os.environ, {"PHOENIX_ENABLED": "true"}, clear=True):
        from agent.llm.phoenix import _phoenix_enabled
        
        assert _phoenix_enabled() is True


def test_phoenix_disabled_explicit_false():
    """Phoenix should be disabled when PHOENIX_ENABLED=false explicitly."""
    with patch.dict(os.environ, {"PHOENIX_ENABLED": "false"}, clear=True):
        from agent.llm.phoenix import _phoenix_enabled
        
        assert _phoenix_enabled() is False


def test_phoenix_host_defaults_to_loopback():
    """PHOENIX_HOST should default to 127.0.0.1 (loopback), not 0.0.0.0."""
    with patch.dict(os.environ, {}, clear=True):
        import importlib

        import agent.llm.phoenix as phoenix_module
        importlib.reload(phoenix_module)
        
        # Mock the Phoenix launch to capture the host argument
        mock_px = MagicMock()
        mock_px.launch_app.return_value = MagicMock()
        
        # Patch the module's px reference
        phoenix_module.px = mock_px
        
        # Mock imports to avoid actual Phoenix dependency
        with patch.dict(sys.modules, {
            "phoenix": mock_px,
            "openinference.instrumentation.litellm": MagicMock(),
            "openinference.instrumentation.openai": MagicMock(),
        }):
            # Enable Phoenix for this test
            with patch.dict(os.environ, {"PHOENIX_ENABLED": "true"}):
                phoenix_module.init_phoenix()
                
                # Verify launch_app was called with loopback
                mock_px.launch_app.assert_called_once()
                call_kwargs = mock_px.launch_app.call_args.kwargs
                assert call_kwargs["host"] == "127.0.0.1", f"Expected 127.0.0.1, got {call_kwargs['host']}"


def test_phoenix_no_sensitive_data_in_traces():
    """Test that patient data is not leaked in OpenInference traces."""
    from agent.privacidad import detalle_seguro
    
    # Test that detalle_seguro filters out sensitive fields
    sensitive_detail = {
        "paciente": "Juan Perez",
        "documento_texto": "Paciente con dolor toracico",
        "evidencia_nombre": "Juan Perez, 45 anos",
        "diagnostico": "Infarto agudo de miocardio",
        "tipo_documento": "Epicrisis",
        "nivel_prioridad": "Urgente",
        "score": 0.95,
        "detectada": True,
        "imagenes": 3,
    }
    
    safe = detalle_seguro(sensitive_detail)
    
    # Should only contain allowed enums, scores, flags, integers
    assert "paciente" not in safe
    assert "documento_texto" not in safe
    assert "evidencia_nombre" not in safe
    assert "diagnostico" not in safe
    
    # Should contain allowed fields
    assert safe.get("tipo_documento") == "Epicrisis"
    assert safe.get("nivel_prioridad") == "Urgente"
    assert safe.get("score") == 0.95
    assert safe.get("detectada") is True
    assert safe.get("imagenes") == 3


def test_registro_seguro_excludes_patient_data():
    """Test that registro_seguro excludes patient identifiers and free text."""
    from agent.privacidad import registro_seguro
    
    registro = {
        "nodo": "clasificar",
        "detalle": {
            "paciente": "Maria Gonzalez",
            "documento_id": "doc-123",
            "evidencia": "Paciente con fiebre alta",
            "tipo_documento": "Informe de Laboratorio",
            "score": 0.88,
        },
        "modelo": "gemini/gemini-2.5-flash",
        "ts": 1234567890.0,
        "paciente_ref": "P-abcdef1234567890abcdef12",
    }
    
    safe = registro_seguro(registro)
    
    # Should not contain patient name or free text
    assert "Maria Gonzalez" not in str(safe)
    assert "fiebre alta" not in str(safe)
    assert "documento_id" not in safe.get("detalle", {})
    assert "evidencia" not in safe.get("detalle", {})
    assert "paciente" not in safe.get("detalle", {})
    
    # Should contain allowed fields
    assert safe.get("nodo") == "clasificar"
    assert safe.get("detalle", {}).get("tipo_documento") == "Informe de Laboratorio"
    assert safe.get("detalle", {}).get("score") == 0.88
    assert safe.get("modelo") == "gemini/gemini-2.5-flash"
    assert safe.get("ts") == 1234567890.0
    # paciente_ref is allowed (it's a pseudonymized reference)
    assert safe.get("paciente_ref") == "P-abcdef1234567890abcdef12"


def test_phoenix_init_no_op_when_disabled():
    """init_phoenix should return False and not initialize when disabled."""
    with patch.dict(os.environ, {"PHOENIX_ENABLED": "false"}, clear=True):
        from agent.llm.phoenix import init_phoenix, is_phoenix_running
        
        result = init_phoenix()
        
        assert result is False
        assert is_phoenix_running() is False


def test_phoenix_context_manager_cleans_up():
    """phoenix_session context manager should clean up on exit."""
    with patch.dict(os.environ, {"PHOENIX_ENABLED": "true"}, clear=True):
        import importlib

        import agent.llm.phoenix as phoenix_module
        importlib.reload(phoenix_module)
        
        mock_px = MagicMock()
        mock_app = MagicMock()
        mock_px.launch_app.return_value = mock_app
        phoenix_module.px = mock_px
        
        with patch.dict(sys.modules, {
            "phoenix": mock_px,
            "openinference.instrumentation.litellm": MagicMock(),
            "openinference.instrumentation.openai": MagicMock(),
        }):
            with phoenix_module.phoenix_session() as initialized:
                assert initialized is True
                assert phoenix_module.is_phoenix_running() is True
            
            # After context exit, should be shutdown
            assert phoenix_module.is_phoenix_running() is False


def test_phoenix_double_init_returns_false():
    """Second init_phoenix call should return False (already initialized)."""
    with patch.dict(os.environ, {"PHOENIX_ENABLED": "true"}, clear=True):
        import importlib

        import agent.llm.phoenix as phoenix_module
        importlib.reload(phoenix_module)
        
        mock_px = MagicMock()
        mock_px.launch_app.return_value = MagicMock()
        phoenix_module.px = mock_px
        
        with patch.dict(sys.modules, {
            "phoenix": mock_px,
            "openinference.instrumentation.litellm": MagicMock(),
            "openinference.instrumentation.openai": MagicMock(),
        }):
            result1 = phoenix_module.init_phoenix()
            result2 = phoenix_module.init_phoenix()
            
            assert result1 is True
            assert result2 is False
            
            phoenix_module.shutdown_phoenix()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])