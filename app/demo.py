"""Modo demo: prueba la UI completa sin LLM ni OCI.

Ejecutar con:  streamlit run app/demo.py

Usa el mismo componente y el mismo flujo que main.py (incluida la lectura real del
archivo con leer_documento), pero en lugar de llamar a procesar() responde con
contenido de ejemplo construido con los modelos Pydantic reales.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re
import unicodedata

import streamlit as st
from componente import OPCIONES, configurar_pagina, manejar_cambio_de_tema, render_ui
from flujo import ejecutar_accion, iniciar_estado

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
    Solicitud,
    _prerrequisitos,
    _resumir_contenido,
)

INTRO = "Una VCN es la red privada donde viven tus recursos en OCI. Este contenido es de ejemplo (modo demo)."

# En el demo cada perfil recibe una introduccion distinta, para que "Comparar perfiles" muestre la diferencia
INTRO_POR_PERFIL = {
    "Principiante": "Imagina un barrio cerrado: tus servidores viven dentro y tú decides qué puertas abrir. Eso es una VCN.",
    "Junior": "Una VCN es la red privada de tu proyecto en OCI: la creas, la divides en subredes y conectas tus servicios.",
    "Lider Tecnico": "La VCN es una red regional con CIDR propio: segmenta por subredes y controla el egreso con NAT y Service Gateway.",
    "Ejecutivo": "La VCN aísla los sistemas de la empresa en la nube y reduce el riesgo de exponer datos sensibles.",
}
NOMBRES_AJUSTE = {
    "mas_ejemplos": "más ejemplos", "mas_corto": "más corto", "mas_tecnico": "más técnico",
    "menos_jerga": "menos jerga", "mas_elementos": "más elementos",
}


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
                    consejo="Elige la región correcta antes de empezar.",
                ),
                PasoTutorial(
                    titulo="Crea la VCN desde la CLI",
                    explicacion="También puedes usar `oci network vcn create`.",
                    ejemplo="oci network vcn create \\\n  --compartment-id $COMPARTMENT_ID \\\n  --cidr-blocks '[\"10.0.0.0/16\"]'",
                ),
                PasoTutorial(
                    titulo="Revisa las reglas de seguridad",
                    explicacion="Permite solo el puerto 443 desde el balanceador.",
                    ejemplo="Por ejemplo, solo el gateway de pagos recibe tráfico público.",
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
                    enunciado="¿Qué componente permite a una instancia privada salir a internet sin exponerse?",
                    opciones=["NAT Gateway", "Internet Gateway", "Service Gateway", "DRG"],
                    indice_correcto=0,
                    explicacion="El NAT Gateway solo permite conexiones iniciadas desde dentro de la VCN.",
                    pista="Piensa en tráfico solo de salida.",
                ),
                PreguntaQuiz(
                    enunciado="Una VCN puede abarcar varias regiones.",
                    opciones=["Verdadero", "Falso"],
                    indice_correcto=1,
                    explicacion="La VCN es un recurso regional.",
                ),
                PreguntaQuiz(
                    enunciado="¿Qué define el rango de direcciones IP de la VCN?",
                    opciones=["La lista de seguridad", "El bloque CIDR", "La tabla de rutas"],
                    indice_correcto=1,
                    explicacion="El bloque CIDR, por ejemplo `10.0.0.0/16`.",
                    pista="Es una notación con barra.",
                ),
            ],
        )
    if formato == "TLDR":
        return ContenidoTLDR(
            titulo=titulo,
            introduccion_contextualizada=INTRO,
            resumen_una_linea="Una VCN aísla tus recursos en OCI y tú decides por dónde entra y sale el tráfico.",
            puntos_clave=[
                PuntoClave(titulo="Es regional", detalle="Vive en una región y se divide en subredes."),
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
                    apoyo_visual="Animación de un edificio cerrado con un candado",
                    duracion_segundos=25,
                ),
                EscenaGuion(
                    titulo="Qué es una VCN",
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
                frente="¿Qué es una VCN?",
                dorso="Una red virtual privada y personalizable dentro de una región de OCI.",
                pista_didactica="Piensa en un barrio cerrado con calles propias.",
            ),
            ItemFlashcard(
                frente="¿Para qué sirve un Internet Gateway?",
                dorso="Permite tráfico entre subredes públicas e internet.",
                pista_didactica="Es la puerta principal del barrio.",
            ),
            ItemFlashcard(
                frente="¿Qué pasa con `<b>etiquetas</b>` en el texto?",
                dorso="Se muestran como texto: la UI escapa el HTML que genere el modelo.",
                pista_didactica="Prueba de seguridad.",
            ),
        ],
    )


def _intro_de_ejemplo(solicitud: Solicitud) -> str:
    intro = INTRO_POR_PERFIL.get(solicitud.perfil_destinatario, INTRO)
    if solicitud.ajustes:
        intro += " Versión ajustada: " + ", ".join(NOMBRES_AJUSTE[a] for a in solicitud.ajustes) + "."
    if solicitud.idioma_salida != "Español":
        intro += f" (Modo demo: con la IA real, todo este contenido estaría en {solicitud.idioma_salida}.)"
    return intro


def procesar_demo(solicitud: Solicitud, usar_cache: bool = True) -> Respuesta:
    """Misma firma que nuevamente.contratos.procesar, pero sin LLM ni almacenamiento."""
    contenido = _contenido_de_ejemplo(solicitud.formato_salida, f"[Demo] {solicitud.documento_titulo}")
    contenido = contenido.model_copy(update={"introduccion_contextualizada": _intro_de_ejemplo(solicitud)})
    tiempo_estimado, conceptos_clave = _resumir_contenido(contenido)
    return Respuesta(
        status="exito",
        metadatos=Metadatos(
            perfil_aplicado=solicitud.perfil_destinatario,
            formato_generado=solicitud.formato_salida,
            tiempo_estimado_estudio_minutos=tiempo_estimado,
            conceptos_clave=conceptos_clave,
            prerrequisitos=_prerrequisitos(solicitud),
            idioma_salida=solicitud.idioma_salida,
        ),
        contenido_adaptado=contenido,
        evaluacion_calidad=EvaluacionCalidad(
            anclaje_fuente_score=0.86, claridad_pedagogica="Alta", observaciones="Contenido de ejemplo del modo demo."
        ),
        almacenamiento_oci=AlmacenamientoOCI(bucket="demo", objeto_id="demo.json", status_upload="completado"),
    )


def _respuesta_de_ejemplo(valor: dict, texto: str) -> Respuesta:
    return procesar_demo(
        Solicitud(
            documento_titulo=valor["archivo_nombre"],
            documento_contenido=texto,
            perfil_destinatario=valor["perfil"],
            formato_salida=valor["formato"],
            nicho_sector=valor["nicho"],
            nivel_detalle=valor["nivel"],
        )
    )


def _palabras(texto: str) -> set[str]:
    sin_tildes = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode("ascii")
    return {palabra for palabra in re.findall(r"[a-z0-9]+", sin_tildes) if len(palabra) > 3}


def preguntar_demo(documento_titulo: str, documento_contenido: str, pregunta: str, idioma: str = "Español") -> dict:
    """Misma firma que nuevamente.preguntas.preguntar: busca la pregunta en los parrafos del documento."""
    from nuevamente.preguntas import validar_pregunta

    pregunta = validar_pregunta(pregunta)
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", documento_contenido) if p.strip()] or [documento_contenido]
    buscadas = _palabras(pregunta)
    puntajes = sorted(((len(buscadas & _palabras(p)), i) for i, p in enumerate(parrafos)), reverse=True)
    usados = [i for puntaje, i in puntajes[:2] if puntaje > 0]
    if not usados:
        return {"respuesta": "No encontré eso en el documento. Prueba con otras palabras.", "en_documento": False, "fuentes": []}
    total = len(parrafos)
    frase = re.split(r"(?<=[.!?])\s+", parrafos[usados[0]])[0]
    return {
        "respuesta": f"Según el documento: {frase} (Modo demo: la IA real redacta la respuesta completa.)",
        "en_documento": True,
        "fuentes": [{"texto": parrafos[i][:600], "fuente": f"{documento_titulo} · fragmento {i + 1} de {total}"} for i in usados],
    }


def _ejecutar_app():
    configurar_pagina("NuevaMente (demo)")
    iniciar_estado(st.session_state)

    valor = render_ui(
        opciones=OPCIONES,
        resultado=st.session_state.resultado,
        error=st.session_state.error,
        historial=st.session_state.historial,
        conversaciones=st.session_state.conversaciones,
        valoraciones=st.session_state.valoraciones,
    )

    manejar_cambio_de_tema(valor)

    if ejecutar_accion(valor, st.session_state, procesar=procesar_demo, preguntar=preguntar_demo):
        st.rerun()


if __name__ == "__main__":
    _ejecutar_app()
