"""Recorrido con embeddings reales y respuesta HTTP controlada (no inferencia real).

Ejecutar desde la raiz: python scripts/prueba_recorrido.py
No usa credenciales. Descarga embeddings de Chroma si no estan instalados.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "app"))

import chromadb
from flujo import ejecutar_accion, iniciar_estado

from nuevamente import agentes, rag
from nuevamente.contratos import MODELOS_POR_FORMATO, procesar
from nuevamente.preguntas import preguntar
from tests.helpers_contenido import contenido, evaluacion


def main():
    logging.disable(logging.CRITICAL)
    peticiones = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            datos = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert self.path == "/api/chat"
            assert self.headers["ngrok-skip-browser-warning"] == "true"
            peticiones.append(datos)
            esquema = datos.get("format", {}).get("title")
            if esquema == "EvaluacionCalidad":
                texto = evaluacion().model_dump_json()
            elif esquema == "RespuestaPregunta":
                texto = json.dumps({"respuesta": "NAT permite salida a internet.", "en_documento": True,
                                    "fragmentos_usados": [1]})
            elif esquema:
                formato = next(f for f, m in MODELOS_POR_FORMATO.items() if m.__name__ == esquema)
                texto = contenido(formato).model_dump_json()
            else:
                texto = "Una VCN es una red privada. NAT permite salida a internet."
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"model": datos["model"], "message": {"role": "assistant", "content": texto},
                                         "done": True, "done_reason": "stop"}).encode() + b"\n")

    with tempfile.TemporaryDirectory() as temporal:
        os.environ["NUEVAMENTE_CACHE_DIR"] = str(Path(temporal) / "cache")
        rag._cliente = chromadb.PersistentClient(path=str(Path(temporal) / "chroma"))
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        hilo = threading.Thread(target=server.serve_forever, daemon=True)
        hilo.start()
        os.environ["LLM_PROVEEDOR"] = "ollama"
        os.environ["OLLAMA_BASE_URL"] = f"http://127.0.0.1:{server.server_port}"
        agentes._llm_primario = None
        try:
            estado = {}
            iniciar_estado(estado)
            texto = "Una VCN es una red privada. El NAT permite salida a internet. " * 30
            for i, formato in enumerate(MODELOS_POR_FORMATO, start=1):
                valor = {"accion": "generar", "id": i, "archivo_nombre": "manual.md",
                         "archivo_base64": base64.b64encode(texto.encode()).decode(), "perfil": "Principiante",
                         "formato": formato, "nicho": "General", "nivel": "Didactico", "idioma": "Español"}
                assert ejecutar_accion(valor, estado, procesar=procesar, preguntar=preguntar)
                assert estado["error"] is None, estado["error"]
                resultado = estado["resultado"]
                assert resultado["status"] == "exito" and resultado["fuentes"]
                assert resultado["metadatos"]["formato_generado"] == formato
                print(f"OK: archivo MD -> embeddings reales -> Chroma -> grafo -> HTTP -> {formato} -> historial")
            accion = {"accion": "preguntar", "id": "pregunta-1", "id_material": 5,
                      "pregunta": "¿Para que sirve NAT?"}
            assert ejecutar_accion(accion, estado, procesar=procesar, preguntar=preguntar)
            respuesta = estado["conversaciones"][5][-1]
            assert "error" not in respuesta and respuesta["fuentes"] and respuesta["en_documento"]
            print("OK: pregunta -> recuperacion real -> HTTP -> respuesta con fuentes")
            assert len(estado["historial"]) == 5
            assert len(peticiones) == 16, len(peticiones)
            print("OK: 6 recorridos completos, 16 solicitudes HTTP; inferencia y respuestas controladas, sin modelos generativos reales.")
        finally:
            server.shutdown()
            server.server_close()
            hilo.join(timeout=2)


if __name__ == "__main__":
    main()
