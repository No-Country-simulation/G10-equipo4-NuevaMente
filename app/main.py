import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import base64
import logging

import streamlit as st
from componente import render_ui

from nuevamente.contratos import Solicitud, procesar
from nuevamente.errores import describir_error
from nuevamente.ingesta import leer_documento

st.set_page_config(layout="wide")

# Ajustar el estilo para que el iframe del componente ocupe todo el ancho y no haya padding
st.markdown(
    """
    <style>
    .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }
    iframe {
        width: 100% !important;
        border: none !important;
    }
    header[data-testid="stHeader"] {
        background: transparent;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

opciones = {
    "perfiles": ["Principiante", "Junior", "Lider Tecnico", "Ejecutivo"],
    "formatos": ["Flashcards", "Tutorial", "Quiz", "TLDR", "Guion"],
    "nichos": ["General", "Fintech", "Salud", "E-commerce"],
    "niveles": ["Didactico", "Intermedio", "Profundo"],
}

if "resultado" not in st.session_state:
    st.session_state.resultado = None
if "ultimo_id" not in st.session_state:
    st.session_state.ultimo_id = None
if "error" not in st.session_state:
    st.session_state.error = None

valor = render_ui(opciones=opciones, resultado=st.session_state.resultado, error=st.session_state.error)

if valor and valor.get("accion") == "generar" and valor.get("id") != st.session_state.ultimo_id:
    st.session_state.ultimo_id = valor["id"]
    try:
        contenido_bytes = base64.b64decode(valor["archivo_base64"])
        contenido_texto = leer_documento(valor["archivo_nombre"], contenido_bytes)
        if not contenido_texto.strip():
            raise ValueError("No se pudo extraer texto del documento. Si es un PDF escaneado, prueba con uno que tenga texto seleccionable.")
        solicitud = Solicitud(
            documento_titulo=valor["archivo_nombre"],
            documento_contenido=contenido_texto,
            perfil_destinatario=valor["perfil"],
            formato_salida=valor["formato"],
            nicho_sector=valor["nicho"],
            nivel_detalle=valor["nivel"],
        )
        with st.spinner("Generando contenido..."):
            respuesta = procesar(solicitud, usar_cache=not valor.get("regenerar", False))
        st.session_state.resultado = {**respuesta.model_dump(), "id_solicitud": valor["id"]}
        st.session_state.error = None
    except Exception as exc:
        logging.getLogger(__name__).exception("Fallo al generar contenido")
        st.session_state.error = {**describir_error(exc), "id": valor["id"]}
    st.rerun()