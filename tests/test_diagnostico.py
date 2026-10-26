"""El diagnostico distingue disponibilidad de modelo e inferencia por proveedor."""
from unittest.mock import Mock

import pytest

from scripts import verificar_servicios as diagnostico


@pytest.mark.parametrize("disponible", [False, True])
@pytest.mark.parametrize("inferir", [False, True])
def test_diagnostico_devuelve_estado_y_no_oculta_fallos(monkeypatch, disponible, inferir):
    monkeypatch.setattr("sys.argv", ["verificar_servicios.py", *(["--inferir"] if inferir else [])])
    monkeypatch.setattr(diagnostico, "load_dotenv", lambda *_a: None)
    monkeypatch.setenv("LLM_PROVEEDOR", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://prueba.ngrok-free.dev")
    cliente = Mock()
    cliente.__enter__ = Mock(return_value=cliente)
    cliente.__exit__ = Mock(return_value=False)
    cliente.get.return_value.json.return_value = {"models": [{"name": "qwen2.5:7b"}] if disponible else []}
    monkeypatch.setattr(diagnostico.httpx, "Client", Mock(return_value=cliente))
    construir = Mock(side_effect=lambda p: p)
    monkeypatch.setattr(diagnostico.agentes, "_construir_llm", construir)
    invocar = Mock(side_effect=lambda obtener, *_a: obtener())
    monkeypatch.setattr(diagnostico.agentes, "_ejecutar_llm", invocar)
    assert diagnostico.main() == int(not disponible)
    assert invocar.call_count == (2 if inferir else 0)
    if inferir:
        assert [c.args[0] for c in construir.call_args_list] == ["ollama", "gemini"]
