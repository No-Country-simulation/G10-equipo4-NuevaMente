from __future__ import annotations

import os
from typing import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from nuevamente.contratos import (
    MODELOS_POR_FORMATO,
    Chunk,
    Contenido,
    EvaluacionCalidad,
    Solicitud,
)
from nuevamente.resiliencia import invocar_con_espera

UMBRAL_ANCLAJE = 0.7
MAX_INTENTOS = 2

INSTRUCCIONES_POR_FORMATO = {
    "Flashcards": (
        "Crea entre 6 y 10 flashcards. 'frente' es una pregunta o concepto corto (maximo 12 palabras), "
        "'dorso' la respuesta en 1 a 3 frases y 'pista_didactica' una analogia o ayuda para recordar."
    ),
    "Tutorial": (
        "Crea un tutorial paso a paso de 4 a 7 pasos en orden logico. Cada paso tiene una explicacion clara, "
        "un 'ejemplo' concreto (codigo o comando si el documento es tecnico, vacio si no aplica) y un 'consejo' "
        "con un error comun a evitar. Incluye de 2 a 5 objetivos y una conclusion breve."
    ),
    "Quiz": (
        "Crea entre 6 y 10 preguntas de evaluacion. Mezcla opcion multiple (4 opciones) con algunas de verdadero/falso "
        "(opciones exactamente ['Verdadero', 'Falso']). Solo una opcion es correcta y 'indice_correcto' es su posicion "
        "empezando en 0. Los distractores deben ser plausibles, sin 'todas las anteriores' ni 'ninguna de las anteriores'. "
        "No antepongas letras ni numeros a las opciones. La 'explicacion' justifica la respuesta con la fuente y la "
        "'pista' orienta sin revelarla."
    ),
    "TLDR": (
        "Crea un resumen ejecutivo: 'resumen_una_linea' con la idea central en una frase, de 3 a 6 'puntos_clave' "
        "(titulo corto y detalle de 1 a 2 frases) y de 2 a 4 'acciones_recomendadas' concretas."
    ),
    "Guion": (
        "Crea un guion para un video o presentacion oral de 4 a 7 escenas. Cada escena tiene la 'narracion' tal cual "
        "se leeria en voz alta, el 'apoyo_visual' que aparece en pantalla y su 'duracion_segundos' realista "
        "(aproximadamente 150 palabras por minuto). Cierra con un 'cierre' que invite a la accion."
    ),
}

_llm_primario = None
_llm_fallback = None

def _construir_llm(proveedor: str):
    if proveedor == "ollama":
        return ChatOllama(
            model=os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
            base_url=os.environ["OLLAMA_BASE_URL"],
        )
    return ChatGoogleGenerativeAI(
        model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        google_api_key=os.environ["GEMINI_API_KEY"],
    )

def _obtener_llm_primario():
    global _llm_primario
    if _llm_primario is None:
        _llm_primario = _construir_llm(os.environ.get("LLM_PROVEEDOR", "gemini"))
    return _llm_primario

def _obtener_llm_fallback():
    global _llm_fallback
    if _llm_fallback is None:
        _llm_fallback = _construir_llm("gemini")
    return _llm_fallback

def _invocar(prompt: str, modelo_salida: type[BaseModel] | None = None):
    llm = _obtener_llm_primario()
    if modelo_salida is not None:
        llm = llm.with_structured_output(modelo_salida)
    try:
        return invocar_con_espera(llm, prompt)
    except Exception:
        if os.environ.get("LLM_PROVEEDOR", "gemini") != "ollama":
            raise
        llm_fallback = _obtener_llm_fallback()
        if modelo_salida is not None:
            llm_fallback = llm_fallback.with_structured_output(modelo_salida)
        return invocar_con_espera(llm_fallback, prompt)

class EstadoAgente(TypedDict):
    solicitud: Solicitud
    chunks: list[Chunk]
    hallazgos: str
    contenido: Contenido
    evaluacion: EvaluacionCalidad
    intentos: int

def _investigar(solicitud: Solicitud, chunks: list[Chunk]) -> str:
    contexto = "\n".join(chunk.texto for chunk in chunks)
    prompt = f"Extrae los puntos clave para un perfil '{solicitud.perfil_destinatario}':\n\n{contexto}"
    return _invocar(prompt).content

def _redactar(solicitud: Solicitud, hallazgos: str) -> Contenido:
    prompt = (
        f"Genera contenido educativo en espanol en formato '{solicitud.formato_salida}' "
        f"para un perfil '{solicitud.perfil_destinatario}', con nivel de detalle '{solicitud.nivel_detalle}' "
        f"y ejemplos del sector '{solicitud.nicho_sector}'.\n"
        f"{INSTRUCCIONES_POR_FORMATO[solicitud.formato_salida]}\n"
        "Usa solo informacion presente en los hallazgos. Texto plano, sin HTML; "
        "puedes marcar codigo en linea con `backticks`.\n\n"
        f"HALLAZGOS:\n{hallazgos}"
    )
    return _invocar(prompt, MODELOS_POR_FORMATO[solicitud.formato_salida])

def _criticar(contenido: Contenido, chunks: list[Chunk]) -> EvaluacionCalidad:
    contexto = "\n".join(chunk.texto for chunk in chunks)
    prompt = (
        "Evalua que tan fiel es el CONTENIDO a la FUENTE.\n"
        "anclaje_fuente_score: decimal entre 0.0 y 1.0 (ejemplo: 0.85). Nunca un numero entero como 4 o 5.\n"
        "claridad_pedagogica: responde exactamente una de estas tres palabras: Alta, Media o Baja.\n"
        "observaciones: maximo 2 frases cortas.\n\n"
        f"FUENTE:\n{contexto}\n\nCONTENIDO:\n{contenido.model_dump_json()}"
    )
    return _invocar(prompt, EvaluacionCalidad)

def _nodo_investigador(estado: EstadoAgente) -> dict:
    return {"hallazgos": _investigar(estado["solicitud"], estado["chunks"])}

def _nodo_redactor(estado: EstadoAgente) -> dict:
    contenido = _redactar(estado["solicitud"], estado["hallazgos"])
    return {"contenido": contenido, "intentos": estado["intentos"] + 1}

def _nodo_critico(estado: EstadoAgente) -> dict:
    return {"evaluacion": _criticar(estado["contenido"], estado["chunks"])}

def _debe_reintentar(estado: EstadoAgente) -> str:
    if estado["evaluacion"].anclaje_fuente_score < UMBRAL_ANCLAJE and estado["intentos"] < MAX_INTENTOS:
        return "redactor"
    return END

def _construir_grafo():
    grafo = StateGraph(EstadoAgente)
    grafo.add_node("investigador", _nodo_investigador)
    grafo.add_node("redactor", _nodo_redactor)
    grafo.add_node("critico", _nodo_critico)
    grafo.add_edge(START, "investigador")
    grafo.add_edge("investigador", "redactor")
    grafo.add_edge("redactor", "critico")
    grafo.add_conditional_edges("critico", _debe_reintentar, {"redactor": "redactor", END: END})
    return grafo.compile()

_grafo = _construir_grafo()

def generar(solicitud: Solicitud, chunks: list[Chunk]) -> tuple[Contenido, EvaluacionCalidad]:
    estado_final = _grafo.invoke({"solicitud": solicitud, "chunks": chunks, "hallazgos": "", "intentos": 0})
    return estado_final["contenido"], estado_final["evaluacion"]
