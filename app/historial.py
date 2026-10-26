"""Historial de materiales generados en la sesion ("Mis materiales")."""

from __future__ import annotations

import time

MAXIMO_MATERIALES = 8  # cada resultado viaja completo al navegador: se limita para no inflar la pagina


def agregar_material(historial: list[dict] | None, resultado: dict, solicitud: dict, ahora_ms: int | None = None) -> list[dict]:
    """Devuelve un historial nuevo con el resultado al principio, sin duplicados y con tope.

    `resultado` es la Respuesta serializada (con `id_solicitud`); `solicitud` es lo que envio la UI
    (archivo_nombre, perfil, formato, nivel). No modifica la lista recibida.
    """
    contenido = resultado.get("contenido_adaptado") or {}
    metadatos = resultado.get("metadatos") or {}
    entrada = {
        "id": resultado["id_solicitud"],
        "titulo": contenido.get("titulo") or solicitud.get("archivo_nombre", "Material"),
        "formato": metadatos.get("formato_generado") or solicitud.get("formato", ""),
        "perfil": metadatos.get("perfil_aplicado") or solicitud.get("perfil", ""),
        "nivel": solicitud.get("nivel", ""),
        "archivo": solicitud.get("archivo_nombre", ""),
        "creado_ms": int(time.time() * 1000) if ahora_ms is None else ahora_ms,
        "resultado": resultado,
    }
    anteriores = [material for material in (historial or []) if material.get("id") != entrada["id"]]
    return [entrada, *anteriores][:MAXIMO_MATERIALES]
