"""Modo demo: prueba la UI completa sin LLM ni OCI.

Ejecutar con:  streamlit run app/demo.py

Usa el mismo componente y el mismo flujo que main.py (incluida la lectura real del
archivo con leer_documento), pero en lugar de llamar a procesar() responde con
contenido de ejemplo construido con los modelos Pydantic reales.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base64

import streamlit as st
from componente import render_ui

from nuevamente.contratos import (
    AlmacenamientoOCI,
    ContenidoAdaptado,
    ContenidoGuion,
    ContenidoQuiz,
    ContenidoTLDR,
    ContenidoTutorial,
    EscenaGuion,
    EvaluacionCalidad,
    ItemFlashcard,
    Metadatos,
    PasoTutorial,
    PreguntaQuiz,
    PuntoClave,
    Respuesta,
    _resumir_contenido,
)
from nuevamente.ingesta import leer_documento

opciones = {
    "perfiles": ["Principiante", "Junior", "Lider Tecnico", "Ejecutivo"],
    "formatos": ["Flashcards", "Tutorial", "Quiz", "TLDR", "Guion"],
    "nichos": ["General", "Fintech", "Salud", "E-commerce"],
    "niveles": ["Didactico", "Intermedio", "Profundo"],
}

INTRO = "Una VCN es la red privada donde viven tus recursos en OCI. Este contenido es de ejemplo (modo demo)."


def _contenido_de_ejemplo(formato: str, titulo: str):
    if formato == "Tutorial":
        return ContenidoTutorial(
            titulo=titulo,
            introduccion_contextualizada=INTRO,
            objetivos=["Crear una VCN con el asistente", "Configurar una subred privada"],
            pasos=[
                PasoTutorial(
                    titulo="Abre el asistente de VCN",
                    explicacion="En la consola ve a Networking y elige **Start VCN Wizard**.",
                    consejo="Elige la region correcta antes de empezar.",
                ),
                PasoTutorial(
                    titulo="Crea la VCN desde la CLI",
                    explicacion="Tambien puedes usar `oci network vcn create`.",
                    ejemplo="oci network vcn create \\\n  --compartment-id $COMPARTMENT_ID \\\n  --cidr-blocks '[\"10.0.0.0/16\"]'",
                ),
                PasoTutorial(
                    titulo="Revisa las reglas de seguridad",
                    explicacion="Permite solo el puerto 443 desde el balanceador.",
                    ejemplo="Por ejemplo, solo el gateway de pagos recibe trafico publico.",
                    consejo="No abras 0.0.0.0/0 en el puerto 22.",
                ),
            ],
            conclusion="Ya tienes una VCN lista para desplegar tu servicio.",
        )
    if formato == "Quiz":
        return ContenidoQuiz(
            titulo=titulo,
            introduccion_contextualizada=INTRO,
            preguntas=[
                PreguntaQuiz(
                    enunciado="Que componente permite a una instancia privada salir a internet sin exponerse?",
                    opciones=["NAT Gateway", "Internet Gateway", "Service Gateway", "DRG"],
                    indice_correcto=0,
                    explicacion="El NAT Gateway solo permite conexiones iniciadas desde dentro de la VCN.",
                    pista="Piensa en trafico solo de salida.",
                ),
                PreguntaQuiz(
                    enunciado="Una VCN puede abarcar varias regiones.",
                    opciones=["Verdadero", "Falso"],
                    indice_correcto=1,
                    explicacion="La VCN es un recurso regional.",
                ),
                PreguntaQuiz(
                    enunciado="Que define el rango de direcciones IP de la VCN?",
                    opciones=["La lista de seguridad", "El bloque CIDR", "La tabla de rutas"],
                    indice_correcto=1,
                    explicacion="El bloque CIDR, por ejemplo `10.0.0.0/16`.",
                    pista="Es una notacion con barra.",
                ),
            ],
        )
    if formato == "TLDR":
        return ContenidoTLDR(
            titulo=titulo,
            introduccion_contextualizada=INTRO,
            resumen_una_linea="Una VCN aisla tus recursos en OCI y tu decides por donde entra y sale el trafico.",
            puntos_clave=[
                PuntoClave(titulo="Es regional", detalle="Vive en una region y se divide en subredes."),
                PuntoClave(titulo="Gateways", detalle="Internet, NAT y Service Gateway controlan cada salida."),
                PuntoClave(titulo="Seguridad", detalle="Listas de seguridad y NSG filtran por puerto y origen."),
            ],
            acciones_recomendadas=["Planifica el CIDR antes de crear la VCN", "Usa subredes privadas para bases de datos"],
        )
    if formato == "Guion":
        return ContenidoGuion(
            titulo=titulo,
            introduccion_contextualizada=INTRO,
            escenas=[
                EscenaGuion(
                    titulo="Gancho",
                    narracion="Imagina que tu app vive en un edificio sin puertas. Hoy le ponemos una, bien vigilada.",
                    apoyo_visual="Animacion de un edificio cerrado con un candado",
                    duracion_segundos=25,
                ),
                EscenaGuion(
                    titulo="Que es una VCN",
                    narracion="Una VCN es tu red privada en la nube de Oracle.",
                    apoyo_visual="Diagrama con la VCN y dos subredes",
                    duracion_segundos=70,
                ),
            ],
            cierre="Crea tu propia VCN en la capa gratuita y comparte tu diagrama.",
        )
    return ContenidoAdaptado(
        titulo=titulo,
        introduccion_contextualizada=INTRO,
        items=[
            ItemFlashcard(
                frente="Que es una VCN?",
                dorso="Una red virtual privada y personalizable dentro de una region de OCI.",
                pista_didactica="Piensa en un barrio cerrado con calles propias.",
            ),
            ItemFlashcard(
                frente="Para que sirve un Internet Gateway?",
                dorso="Permite trafico entre subredes publicas e internet.",
                pista_didactica="Es la puerta principal del barrio.",
            ),
            ItemFlashcard(
                frente="Que pasa con `<b>etiquetas</b>` en el texto?",
                dorso="Se muestran como texto: la UI escapa el HTML que genere el modelo.",
                pista_didactica="Prueba de seguridad.",
            ),
        ],
    )


def _respuesta_de_ejemplo(valor: dict) -> Respuesta:
    contenido = _contenido_de_ejemplo(valor["formato"], f"[Demo] {valor['archivo_nombre']}")
    tiempo_estimado, conceptos_clave = _resumir_contenido(contenido)
    return Respuesta(
        status="exito",
        metadatos=Metadatos(
            perfil_aplicado=valor["perfil"],
            formato_generado=valor["formato"],
            tiempo_estimado_estudio_minutos=tiempo_estimado,
            conceptos_clave=conceptos_clave,
        ),
        contenido_adaptado=contenido,
        evaluacion_calidad=EvaluacionCalidad(
            anclaje_fuente_score=0.86, claridad_pedagogica="Alta", observaciones="Contenido de ejemplo del modo demo."
        ),
        almacenamiento_oci=AlmacenamientoOCI(bucket="demo", objeto_id="demo.json", status_upload="completado"),
    )


def _ejecutar_app():
    st.set_page_config(layout="wide")

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
            respuesta = _respuesta_de_ejemplo(valor)
            st.session_state.resultado = {**respuesta.model_dump(), "id_solicitud": valor["id"]}
            st.session_state.error = None
        except Exception as exc:  # noqa: BLE001
            st.session_state.error = {"mensaje": str(exc), "id": valor["id"]}
        st.rerun()


if __name__ == "__main__":
    _ejecutar_app()
