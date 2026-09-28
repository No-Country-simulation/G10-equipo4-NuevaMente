from __future__ import annotations

import os
from typing import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from nuevamente.contratos import Chunk, ContenidoAdaptado, EvaluacionCalidad, Solicitud

UMBRAL_ANCLAJE = 0.7
MAX_INTENTOS = 2

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
        return llm.with_retry(stop_after_attempt=3).invoke(prompt)
    except Exception:
        if os.environ.get("LLM_PROVEEDOR", "gemini") != "ollama":
            raise
        llm_fallback = _obtener_llm_fallback()
        if modelo_salida is not None:
            llm_fallback = llm_fallback.with_structured_output(modelo_salida)
        return llm_fallback.with_retry(stop_after_attempt=3).invoke(prompt)

class EstadoAgente(TypedDict):
    solicitud: Solicitud
    chunks: list[Chunk]
    hallazgos: str
    contenido: ContenidoAdaptado
    evaluacion: EvaluacionCalidad
    intentos: int

def _investigar(solicitud: Solicitud, chunks: list[Chunk]) -> str:
    contexto = "\n".join(chunk.texto for chunk in chunks)
    prompt = f"Extrae los puntos clave para un perfil '{solicitud.perfil_destinatario}':\n\n{contexto}"
    return _invocar(prompt).content

def _redactar(solicitud: Solicitud, hallazgos: str) -> ContenidoAdaptado:
    prompt = (
        f"Genera contenido en formato '{solicitud.formato_salida}' "
        f"para un perfil '{solicitud.perfil_destinatario}' a partir de estos hallazgos:\n\n{hallazgos}"
    )
    return _invocar(prompt, ContenidoAdaptado)

def _criticar(contenido: ContenidoAdaptado, chunks: list[Chunk]) -> EvaluacionCalidad:
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

def generar(solicitud: Solicitud, chunks: list[Chunk]) -> tuple[ContenidoAdaptado, EvaluacionCalidad]:
    estado_final = _grafo.invoke({"solicitud": solicitud, "chunks": chunks, "hallazgos": "", "intentos": 0})
    return estado_final["contenido"], estado_final["evaluacion"]
