from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_RUTA_APP = Path(__file__).resolve().parent
_RUTA_FRONTEND = _RUTA_APP / "frontend"
RUTA_FAVICON = _RUTA_APP / "assets" / "favicon.png"

OPCIONES = {
    "perfiles": ["Principiante", "Junior", "Lider Tecnico", "Ejecutivo"],
    "formatos": ["Flashcards", "Tutorial", "Quiz", "TLDR", "Guion"],
    "nichos": ["General", "Fintech", "Salud", "E-commerce"],
    "niveles": ["Didactico", "Intermedio", "Profundo"],
    "idiomas": ["Español", "Português", "English"],
}

TEMAS = ("claro", "oscuro")
TEMA_POR_DEFECTO = "claro"

# En modo oscuro tambien se oscurece la pagina de Streamlit alrededor del componente,
# con el mismo fondo que usa la UI, para que no quede una franja clara.
_ESTILOS_OSCURO = """
<style>
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background-color: #0E1117 !important; }
header [data-testid="stMainMenu"] button { color: #F3F4F6 !important; }
</style>
"""

# El iframe del componente ocupa todo el ancho, sin el padding por defecto de Streamlit
_ESTILOS_PAGINA = """
<style>
.block-container { padding: 0 !important; max-width: 100% !important; }
iframe { width: 100% !important; border: none !important; }
header[data-testid="stHeader"] { background: transparent; }
/* La cabecera de Streamlit es transparente y mide 60px de alto: sin esto tapa los clics
   sobre la UI cuando un boton queda debajo al hacer scroll. Solo el menu sigue activo. */
header[data-testid="stHeader"], header [data-testid="stToolbar"] { pointer-events: none; }
header [data-testid="stMainMenu"], header [data-testid="stToolbarActions"] { pointer-events: auto; }
</style>
"""

_componente = components.declare_component("nuevamente_ui", path=str(_RUTA_FRONTEND))


def configurar_pagina(titulo: str = "NuevaMente") -> None:
    """Titulo de la pestaña, favicon, layout y tema. Debe ser la primera llamada a Streamlit."""
    st.set_page_config(
        page_title=titulo,
        page_icon=str(RUTA_FAVICON),
        layout="wide",
        menu_items={"About": "NuevaMente: documentación técnica convertida en contenido para aprender."},
    )
    st.markdown(_ESTILOS_PAGINA, unsafe_allow_html=True)
    if tema_actual() == "oscuro":
        st.markdown(_ESTILOS_OSCURO, unsafe_allow_html=True)


def tema_actual() -> str:
    tema = st.session_state.get("tema", TEMA_POR_DEFECTO)
    return tema if tema in TEMAS else TEMA_POR_DEFECTO


def leer_cambio_de_tema(valor: dict | None) -> str | None:
    """Si la UI pidio cambiar de tema, devuelve "claro" u "oscuro"; si no, None.
    Solo se aceptan esos dos valores (se usan para decidir que CSS se inyecta)."""
    if not isinstance(valor, dict) or valor.get("accion") != "tema":
        return None
    tema = valor.get("tema")
    return tema if tema in TEMAS else None


def manejar_cambio_de_tema(valor: dict | None) -> None:
    """Guarda el tema pedido por el boton y vuelve a dibujar la pagina con sus colores."""
    tema = leer_cambio_de_tema(valor)
    if tema is None or valor.get("id") == st.session_state.get("ultimo_id_tema"):
        return
    st.session_state.ultimo_id_tema = valor.get("id")
    if tema != tema_actual():
        st.session_state.tema = tema
        st.rerun()


def render_ui(
    opciones: dict,
    resultado: dict | None = None,
    error: dict | None = None,
    historial: list[dict] | None = None,
    conversaciones: dict | None = None,
    valoraciones: dict | None = None,
):
    # Las claves de los diccionarios viajan como texto (JSON): los ids se convierten aqui
    return _componente(
        opciones=opciones,
        resultado=resultado,
        error=error,
        historial=historial or [],
        conversaciones={str(k): v for k, v in (conversaciones or {}).items()},
        valoraciones={str(k): v for k, v in (valoraciones or {}).items()},
        tema=tema_actual(),
        default=None,
        key="nuevamente_ui",
    )
