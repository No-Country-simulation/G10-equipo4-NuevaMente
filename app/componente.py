from __future__ import annotations

import os

import streamlit.components.v1 as components

_RUTA_FRONTEND = os.path.join(os.path.dirname(__file__), "frontend")

_componente = components.declare_component("nuevamente_ui", path=_RUTA_FRONTEND)


def render_ui(opciones: dict, resultado: dict | None = None):
    return _componente(opciones=opciones, resultado=resultado, default=None, key="nuevamente_ui")
