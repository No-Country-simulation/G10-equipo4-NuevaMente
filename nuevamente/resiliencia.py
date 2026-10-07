"""Reintentos con espera cuando el proveedor de LLM responde por limite de cuota."""

from __future__ import annotations

import time

PALABRAS_CUOTA = ("429", "resource_exhausted", "quota", "rate limit", "rate_limit", "too many requests")
ESPERAS_SEGUNDOS = (5, 15, 30)

# Se llama como funcion de modulo (no se copia en un default) para que las pruebas
# puedan reemplazarla y no esperar de verdad.
dormir = time.sleep


def es_limite_de_cuota(exc: BaseException) -> bool:
    texto = f"{type(exc).__name__} {exc}".lower()
    return any(palabra in texto for palabra in PALABRAS_CUOTA)


def invocar_con_espera(llm, prompt, esperas: tuple[int, ...] | None = None):
    """Invoca al LLM (con los 3 reintentos rapidos de LangChain). Si falla por cuota
    (429 / RESOURCE_EXHAUSTED), espera y vuelve a intentar segun `esperas`; cualquier
    otro error, o agotar las esperas, se propaga tal cual."""
    esperas = ESPERAS_SEGUNDOS if esperas is None else esperas
    intento = 0
    while True:
        try:
            return llm.with_retry(stop_after_attempt=3).invoke(prompt)
        except Exception as exc:
            if not es_limite_de_cuota(exc) or intento >= len(esperas):
                raise
            dormir(esperas[intento])
            intento += 1