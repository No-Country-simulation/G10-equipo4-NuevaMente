import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import base64  # noqa: E402

import streamlit as st  # noqa: E402

from componente import render_ui  # noqa: E402
from nuevamente.contratos import Solicitud, procesar  # noqa: E402
from nuevamente.ingesta import leer_documento  # noqa: E402

st.set_page_config(layout="wide")

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

valor = render_ui(opciones=opciones, resultado=st.session_state.resultado)

if valor and valor.get("accion") == "generar" and valor.get("id") != st.session_state.ultimo_id:
    st.session_state.ultimo_id = valor["id"]
    contenido_bytes = base64.b64decode(valor["archivo_base64"])
    contenido_texto = leer_documento(valor["archivo_nombre"], contenido_bytes)
    solicitud = Solicitud(
        documento_titulo=valor["archivo_nombre"],
        documento_contenido=contenido_texto,
        perfil_destinatario=valor["perfil"],
        formato_salida=valor["formato"],
        nicho_sector=valor["nicho"],
        nivel_detalle=valor["nivel"],
    )
    with st.spinner("Generando contenido..."):
        respuesta = procesar(solicitud)
    st.session_state.resultado = respuesta.model_dump()
    st.rerun()

