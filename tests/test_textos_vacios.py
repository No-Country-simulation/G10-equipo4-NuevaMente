"""Un JSON bien formado sin contenido util tambien debe activar Gemini."""
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from nuevamente import agentes
from nuevamente.contratos import MODELOS_POR_FORMATO, RespuestaPregunta
from tests.helpers_contenido import contenido

CAMPOS = [
    ("Flashcards", "items", "dorso"),
    ("Tutorial", "pasos", "explicacion"),
    ("Quiz", "preguntas", "enunciado"),
    ("TLDR", "puntos_clave", "detalle"),
    ("Guion", "escenas", "narracion"),
]


@pytest.mark.parametrize("vacio", ["", " \n\t "])
@pytest.mark.parametrize("formato,lista,campo", CAMPOS)
def test_texto_principal_vacio_activa_gemini(monkeypatch, vacio, formato, lista, campo):
    valido = contenido(formato)
    invalido = valido.model_dump()
    invalido[lista][0][campo] = vacio
    primario, respaldo = Mock(), Mock()
    for cliente in (primario, respaldo):
        cliente.with_structured_output.return_value = cliente
        cliente.with_retry.return_value = cliente
    primario.invoke.return_value = invalido
    respaldo.invoke.return_value = valido
    monkeypatch.setenv("LLM_PROVEEDOR", "ollama")
    monkeypatch.setattr(agentes, "_obtener_llm_primario", lambda: primario)
    monkeypatch.setattr(agentes, "_obtener_llm_fallback", lambda: respaldo)
    assert agentes._invocar("contenido", MODELOS_POR_FORMATO[formato]) == valido
    respaldo.invoke.assert_called_once()


@pytest.mark.parametrize("vacio", ["", " \n\t "])
def test_respuesta_a_pregunta_vacia_no_es_valida(vacio):
    with pytest.raises(ValidationError):
        RespuestaPregunta(respuesta=vacio, en_documento=True, fragmentos_usados=[1])


@pytest.mark.parametrize("vacio", ["", " \n\t "])
def test_quiz_no_acepta_opcion_vacia(vacio):
    datos = contenido("Quiz").model_dump()
    datos["preguntas"][0]["opciones"][0] = vacio
    with pytest.raises(ValidationError):
        MODELOS_POR_FORMATO["Quiz"].model_validate(datos)
