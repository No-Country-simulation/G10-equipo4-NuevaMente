"""Diagnostico real: python scripts/verificar_servicios.py [--inferir]."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from nuevamente import agentes
from nuevamente.config import leer_configuracion, requerir_configuracion


class Comprobacion(BaseModel):
    respuesta: str = Field(min_length=1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inferir", action="store_true", help="Hace una llamada real a cada proveedor; puede consumir cuota de Gemini.")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    fallos = 0
    try:
        if agentes._proveedor() != "ollama":
            raise ValueError("Configura LLM_PROVEEDOR=ollama para mantener Ollama como principal.")
        url = requerir_configuracion("OLLAMA_BASE_URL").rstrip("/")
        with httpx.Client(timeout=10, headers={"ngrok-skip-browser-warning": "true"}) as cliente:
            respuesta = cliente.get(f"{url}/api/tags")
            respuesta.raise_for_status()
            modelos = respuesta.json().get("models", [])
        modelo = leer_configuracion("OLLAMA_MODEL", agentes.OLLAMA_MODELO_POR_DEFECTO)
        if modelo not in {m.get("name") for m in modelos}:
            raise ValueError("El modelo configurado no aparece en /api/tags. Descargalo con ollama pull.")
        print("OK: conexion a Ollama y modelo disponible.")
    except Exception as exc:  # noqa: BLE001 - diagnostico: cualquier fallo debe devolver codigo 1
        print(f"FALLO: Ollama/tunel ({type(exc).__name__}). Revisa URL, tunel activo y modelo instalado.")
        fallos += 1
    if args.inferir:
        for proveedor in ("ollama", "gemini"):
            try:
                # Se prueban por separado para que un respaldo no oculte un fallo.
                agentes._ejecutar_llm(
                    lambda p=proveedor: agentes._construir_llm(p),
                    'Devuelve una respuesta JSON con el campo respuesta y el texto "Conexion correcta".',
                    Comprobacion,
                )
                print(f"OK: inferencia estructurada en {proveedor}.")
            except Exception as exc:  # noqa: BLE001 - diagnostico: cualquier fallo debe devolver codigo 1
                print(f"FALLO: inferencia en {proveedor} ({type(exc).__name__}). Revisa configuracion, disponibilidad y cuota.")
                fallos += 1
    else:
        print("Inferencia no ejecutada. Usa --inferir para comprobar Ollama y Gemini por separado.")
    return int(fallos > 0)


if __name__ == "__main__":
    raise SystemExit(main())
