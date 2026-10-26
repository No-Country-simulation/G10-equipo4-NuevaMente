"""Integracion del grafo y ChatOllama reales contra un servidor HTTP controlado.

No es inferencia real: valida transporte, esquema, parseo y respaldo sin credenciales.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from nuevamente import agentes
from nuevamente.contratos import MODELOS_POR_FORMATO, Chunk
from tests.helpers_contenido import contenido, evaluacion, solicitud


@pytest.mark.parametrize("formato", list(MODELOS_POR_FORMATO))
@pytest.mark.parametrize("respuesta_invalida", [False, True])
def test_grafo_real_con_json_http(monkeypatch, formato, respuesta_invalida):
    material = contenido(formato)
    peticiones = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            peticiones.append(payload)
            assert self.path == "/api/chat"
            assert self.headers["ngrok-skip-browser-warning"] == "true"
            esquema = payload.get("format")
            if not esquema:
                texto = "Una VCN es una red privada en la nube."
            elif esquema["title"] == "EvaluacionCalidad":
                texto = evaluacion().model_dump_json()
            else:
                assert esquema["title"] == type(material).__name__
                texto = '{"invalido":true}' if respuesta_invalida else material.model_dump_json()
            data = {"model": payload["model"], "message": {"role": "assistant", "content": texto},
                    "done": True, "done_reason": "stop"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode() + b"\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    hilo = threading.Thread(target=server.serve_forever, daemon=True)
    hilo.start()
    monkeypatch.setenv("LLM_PROVEEDOR", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setattr(agentes, "_llm_primario", None)
    respaldo = Mock()
    respaldo.with_retry.return_value = respaldo
    respaldo.with_structured_output.return_value = respaldo
    respaldo.invoke.return_value = material
    obtener_respaldo = Mock(return_value=respaldo)
    monkeypatch.setattr(agentes, "_obtener_llm_fallback", obtener_respaldo)
    try:
        generado, calidad = agentes.generar(solicitud(formato), [Chunk(texto="Una VCN es una red privada.", fuente="manual")])
        assert generado == material
        assert calidad == evaluacion()
        assert len(peticiones) == 3
        assert obtener_respaldo.call_count == int(respuesta_invalida)
    finally:
        server.shutdown()
        server.server_close()
        hilo.join(timeout=2)


@pytest.mark.parametrize("valor", [None, 123, {"reasoning": "sin texto"}])
def test_contenido_no_textual_activa_respaldo(monkeypatch, valor):
    monkeypatch.setenv("LLM_PROVEEDOR", "ollama")
    primario, respaldo = Mock(), Mock()
    primario.with_retry.return_value = primario
    respaldo.with_retry.return_value = respaldo
    primario.invoke.return_value = SimpleNamespace(content=valor)
    respaldo.invoke.return_value = "Texto valido"
    monkeypatch.setattr(agentes, "_obtener_llm_primario", lambda: primario)
    monkeypatch.setattr(agentes, "_obtener_llm_fallback", lambda: respaldo)
    assert agentes._invocar("pregunta") == "Texto valido"


def test_flashcards_vacias_activan_respaldo(monkeypatch):
    monkeypatch.setenv("LLM_PROVEEDOR", "ollama")
    primario, respaldo = Mock(), Mock()
    primario.with_retry.return_value = primario
    respaldo.with_retry.return_value = respaldo
    primario.with_structured_output.return_value = primario
    respaldo.with_structured_output.return_value = respaldo
    primario.invoke.return_value = {"titulo": "T", "introduccion_contextualizada": "I", "items": []}
    respaldo.invoke.return_value = contenido()
    monkeypatch.setattr(agentes, "_obtener_llm_primario", lambda: primario)
    monkeypatch.setattr(agentes, "_obtener_llm_fallback", lambda: respaldo)
    assert agentes._invocar("pregunta", MODELOS_POR_FORMATO["Flashcards"]).items
