"""Continuidad: fallos controlados y cliente ChatOllama real por HTTP local."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from nuevamente import agentes


def _doble():
    cliente = Mock()
    cliente.with_retry.return_value = cliente
    return cliente


class Salida(BaseModel):
    respuesta: str


@pytest.fixture(autouse=True)
def aislar(monkeypatch):
    monkeypatch.setenv("LLM_PROVEEDOR", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://prueba.ngrok-free.dev")
    monkeypatch.setattr(agentes, "_llm_primario", None)
    monkeypatch.setattr(agentes, "_llm_fallback", None)


@pytest.mark.parametrize("etapa", ["construccion", "preparacion", "conexion", "timeout", "vacia", "estructura"])
def test_respaldo_cubre_etapas(monkeypatch, etapa):
    primario, respaldo = _doble(), _doble()
    primario.with_structured_output.return_value = primario
    respaldo.with_structured_output.return_value = respaldo
    respaldo.invoke.return_value = {"respuesta": "respaldo"}
    primario.invoke.return_value = {"respuesta": "ok"}
    obtener = Mock(return_value=primario)
    if etapa == "construccion":
        obtener.side_effect = RuntimeError("cliente no disponible")
    elif etapa == "preparacion":
        primario.with_structured_output.side_effect = ValueError("formato no soportado")
    elif etapa == "conexion":
        primario.invoke.side_effect = ConnectionError("sin conexion")
    elif etapa == "timeout":
        primario.invoke.side_effect = TimeoutError("tiempo agotado")
    elif etapa == "vacia":
        primario.invoke.return_value = None
    else:
        primario.invoke.return_value = {"campo_incorrecto": "dato"}
    monkeypatch.setattr(agentes, "_obtener_llm_primario", obtener)
    monkeypatch.setattr(agentes, "_obtener_llm_fallback", lambda: respaldo)
    assert agentes._invocar("pregunta", Salida).respuesta == "respaldo"
    respaldo.invoke.assert_called_once_with("pregunta")


@pytest.mark.parametrize("vacia", ["", "   ", SimpleNamespace(content=[]), SimpleNamespace(content=[{"type": "thinking", "thinking": "interno"}])])
def test_texto_vacio(monkeypatch, vacia):
    primario, respaldo = _doble(), _doble()
    primario.invoke.return_value = vacia
    respaldo.invoke.return_value = "Respuesta util"
    monkeypatch.setattr(agentes, "_obtener_llm_primario", lambda: primario)
    monkeypatch.setattr(agentes, "_obtener_llm_fallback", lambda: respaldo)
    assert agentes._invocar("p") == "Respuesta util"


def test_ollama_sano(monkeypatch):
    primario, fallback = _doble(), _doble()
    primario.invoke.return_value = "contenido"
    monkeypatch.setattr(agentes, "_obtener_llm_primario", lambda: primario)
    monkeypatch.setattr(agentes, "_obtener_llm_fallback", fallback)
    assert agentes._invocar("p") == "contenido"
    fallback.assert_not_called()


def test_dos_caidos(monkeypatch):
    primario, respaldo = _doble(), _doble()
    primario.invoke.side_effect = ConnectionError("Ollama caido")
    respaldo.invoke.side_effect = ConnectionError("Gemini caido")
    monkeypatch.setattr(agentes, "_obtener_llm_primario", lambda: primario)
    monkeypatch.setattr(agentes, "_obtener_llm_fallback", lambda: respaldo)
    with pytest.raises(ConnectionError, match="Gemini caido"):
        agentes._invocar("p")
    assert primario.invoke.call_count == respaldo.invoke.call_count == 1


def test_default_normalizado(monkeypatch):
    monkeypatch.delenv("LLM_PROVEEDOR")
    assert agentes._proveedor() == "ollama"
    monkeypatch.setenv("LLM_PROVEEDOR", " OLLAMA ")
    assert agentes._proveedor() == "ollama"


@pytest.mark.parametrize("valor", ["0", "-1", "nan", "inf", "texto"])
def test_timeout_invalido(monkeypatch, valor):
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", valor)
    with pytest.raises(ValueError):
        agentes._construir_llm("ollama")


def test_clientes_reales_configuracion(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-simulada")
    ollama = agentes._construir_llm("ollama")
    gemini = agentes._construir_llm("gemini")
    assert ollama.base_url == "https://prueba.ngrok-free.dev"
    assert ollama.client_kwargs["headers"]["ngrok-skip-browser-warning"] == "true"
    assert ollama.client_kwargs["timeout"].read == 60
    assert ollama.client_kwargs["timeout"].connect == 5
    assert gemini.timeout == 45
    assert gemini.max_retries == 0


@pytest.mark.parametrize("fallar", [False, True])
def test_chatollama_real_http_controlado(monkeypatch, fallar):
    class Handler(BaseHTTPRequestHandler):
        llamadas = 0

        def log_message(self, *_args):
            pass

        def do_POST(self):
            Handler.llamadas += 1
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert payload["model"] == "qwen2.5:7b"
            assert self.headers.get("ngrok-skip-browser-warning") == "true"
            self.send_response(503 if fallar else 200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {"error": "no disponible"} if fallar else {
                "model": "qwen2.5:7b", "message": {"role": "assistant", "content": "respuesta HTTP"},
                "done": True, "done_reason": "stop"
            }
            self.wfile.write(json.dumps(data).encode() + b"\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    hilo = threading.Thread(target=server.serve_forever, daemon=True)
    hilo.start()
    monkeypatch.setenv("OLLAMA_BASE_URL", f"http://127.0.0.1:{server.server_port}")
    respaldo = _doble()
    respaldo.invoke.return_value = SimpleNamespace(content="Gemini simulado")
    monkeypatch.setattr(agentes, "_obtener_llm_fallback", lambda: respaldo)
    try:
        respuesta = agentes._invocar("hola")
        assert respuesta.content == ("Gemini simulado" if fallar else "respuesta HTTP")
        assert Handler.llamadas == 1
        assert respaldo.invoke.call_count == int(fallar)
    finally:
        server.shutdown()
        server.server_close()
        hilo.join(timeout=2)
