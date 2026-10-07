"""Cache en disco de generaciones: misma solicitud + buena calidad = sin llamar al LLM."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from pydantic import ValidationError

UMBRAL_CACHE = 0.7  # mismo umbral de anclaje que usa el grafo de agentes


def _directorio() -> Path:
    # Se lee en cada llamada para que las pruebas puedan aislarlo con una variable de entorno.
    return Path(os.environ.get("NUEVAMENTE_CACHE_DIR", ".cache_generacion"))


def _ruta(solicitud) -> Path:
    huella = hashlib.sha256(solicitud.model_dump_json().encode("utf-8")).hexdigest()
    return _directorio() / f"{huella}.json"


def obtener(solicitud):
    """Devuelve (contenido, evaluacion, fuentes) si hay una entrada valida; si no, None."""
    from nuevamente.contratos import MODELOS_POR_FORMATO, Chunk, EvaluacionCalidad

    ruta = _ruta(solicitud)
    if not ruta.exists():
        return None
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        contenido = MODELOS_POR_FORMATO[solicitud.formato_salida].model_validate(datos["contenido"])
        evaluacion = EvaluacionCalidad.model_validate(datos["evaluacion"])
        fuentes = [Chunk.model_validate(f) for f in datos["fuentes"]]
    except (OSError, ValueError, KeyError, ValidationError):
        return None  # entrada corrupta o de un esquema viejo: se ignora y se regenera
    return contenido, evaluacion, fuentes


def guardar(solicitud, contenido, evaluacion, fuentes=()) -> bool:
    """Guarda solo si la calidad es suficiente. Devuelve True si quedo en cache."""
    if evaluacion.anclaje_fuente_score < UMBRAL_CACHE:
        return False
    try:
        ruta = _ruta(solicitud)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        carga = {
            "contenido": contenido.model_dump(),
            "evaluacion": evaluacion.model_dump(),
            "fuentes": [f.model_dump() for f in fuentes],
        }
        ruta.write_text(json.dumps(carga, ensure_ascii=False), encoding="utf-8")
    except OSError:
        return False  # la cache es una optimizacion: nunca debe romper una generacion
    return True