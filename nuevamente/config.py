"""Lectura de configuracion: primero variables de entorno (.env) y luego st.secrets (Streamlit Cloud)."""

from __future__ import annotations

import os


class ConfiguracionIncompletaError(RuntimeError):
    """Falta una variable de configuracion obligatoria. El nombre queda en el mensaje tecnico."""

    def __init__(self, clave: str) -> None:
        super().__init__(f"Falta configurar la variable {clave}.")
        self.clave = clave


def leer_configuracion(clave: str, defecto: str | None = None) -> str | None:
    valor = os.environ.get(clave)
    if valor:
        return valor.strip()
    try:
        import streamlit as st

        valor = st.secrets.get(clave)
    except (ImportError, FileNotFoundError, KeyError, AttributeError):
        # Sin streamlit o sin secrets.toml: st.secrets lanza en vez de devolver None
        valor = None
    return str(valor).strip() if valor else defecto


def requerir_configuracion(clave: str) -> str:
    valor = leer_configuracion(clave)
    if not valor:
        raise ConfiguracionIncompletaError(clave)
    return valor
