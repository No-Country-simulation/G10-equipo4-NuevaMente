from unittest.mock import patch

import pytest
from pydantic import ValidationError

from nuevamente.agentes import INSTRUCCIONES_POR_FORMATO, _redactar
from nuevamente.contratos import (
    MODELOS_POR_FORMATO,
    Chunk,
    ContenidoGuion,
    ContenidoQuiz,
    ContenidoTLDR,
    ContenidoTutorial,
    EscenaGuion,
    EvaluacionCalidad,
    PasoTutorial,
    PreguntaQuiz,
    PuntoClave,
    Solicitud,
    procesar,
)


def hacer_solicitud(formato: str) -> Solicitud:
    return Solicitud(
        documento_titulo="Titulo",
        documento_contenido="Contenido",
        perfil_destinatario="Junior",
        formato_salida=formato,
        nicho_sector="Fintech",
        nivel_detalle="Profundo",
    )


def hacer_pregunta(**overrides) -> PreguntaQuiz:
    base = {
        "enunciado": "Que es una VCN?",
        "opciones": ["Una red privada", "Una base de datos", "Un balanceador"],
        "indice_correcto": 0,
        "explicacion": "La fuente la define como red privada.",
    }
    base.update(overrides)
    return PreguntaQuiz(**base)


def test_hay_modelo_e_instrucciones_para_cada_formato():
    formatos = ["Flashcards", "Tutorial", "Quiz", "TLDR", "Guion"]
    assert sorted(MODELOS_POR_FORMATO) == sorted(formatos)
    assert sorted(INSTRUCCIONES_POR_FORMATO) == sorted(formatos)


def test_pregunta_quiz_valida():
    pregunta = hacer_pregunta()
    assert pregunta.opciones[pregunta.indice_correcto] == "Una red privada"


def test_pregunta_quiz_acepta_verdadero_falso():
    pregunta = hacer_pregunta(opciones=["Verdadero", "Falso"], indice_correcto=1)
    assert pregunta.indice_correcto == 1


def test_pregunta_quiz_falla_si_el_indice_no_existe():
    with pytest.raises(ValidationError):
        hacer_pregunta(indice_correcto=3)


def test_pregunta_quiz_falla_con_indice_negativo():
    with pytest.raises(ValidationError):
        hacer_pregunta(indice_correcto=-1)


def test_pregunta_quiz_falla_con_opciones_repetidas():
    with pytest.raises(ValidationError):
        hacer_pregunta(opciones=["Red", "red ", "Base"])


def test_pregunta_quiz_falla_con_una_sola_opcion():
    with pytest.raises(ValidationError):
        hacer_pregunta(opciones=["Unica"])


def test_quiz_sin_preguntas_falla():
    with pytest.raises(ValidationError):
        ContenidoQuiz(titulo="T", introduccion_contextualizada="I", preguntas=[])


@pytest.mark.parametrize("formato", ["Flashcards", "Tutorial", "Quiz", "TLDR", "Guion"])
def test_redactar_usa_el_modelo_del_formato(formato):
    with patch("nuevamente.agentes._invocar") as invocar:
        _redactar(hacer_solicitud(formato), "hallazgos")

    prompt, modelo = invocar.call_args.args
    assert modelo is MODELOS_POR_FORMATO[formato]
    assert INSTRUCCIONES_POR_FORMATO[formato] in prompt
    assert "Fintech" in prompt
    assert "Profundo" in prompt


CONTENIDOS = {
    "Tutorial": ContenidoTutorial(
        titulo="T",
        introduccion_contextualizada="I",
        objetivos=["Crear una VCN"],
        pasos=[PasoTutorial(titulo="Paso 1", explicacion="E"), PasoTutorial(titulo="Paso 2", explicacion="E")],
        conclusion="C",
    ),
    "Quiz": ContenidoQuiz(titulo="T", introduccion_contextualizada="I", preguntas=[hacer_pregunta(), hacer_pregunta()]),
    "TLDR": ContenidoTLDR(
        titulo="T",
        introduccion_contextualizada="I",
        resumen_una_linea="R",
        puntos_clave=[PuntoClave(titulo="Punto", detalle="D")],
    ),
    "Guion": ContenidoGuion(
        titulo="T",
        introduccion_contextualizada="I",
        escenas=[
            EscenaGuion(titulo="Escena", narracion="N", apoyo_visual="V", duracion_segundos=90),
            EscenaGuion(titulo="Otra", narracion="N", apoyo_visual="V", duracion_segundos=90),
        ],
        cierre="C",
    ),
}

ESPERADO = {
    "Tutorial": (8, ["Paso 1", "Paso 2"]),
    "Quiz": (3, ["Que es una VCN?", "Que es una VCN?"]),
    "TLDR": (1, ["Punto"]),
    "Guion": (3, ["Escena", "Otra"]),
}


@pytest.mark.parametrize("formato", list(CONTENIDOS))
def test_procesar_devuelve_el_contenido_de_cada_formato(formato):
    contenido = CONTENIDOS[formato]
    with (
        patch("nuevamente.rag.indexar", return_value=3),
        patch("nuevamente.rag.recuperar", return_value=[Chunk(texto="fuente", fuente="doc1")]),
        patch(
            "nuevamente.agentes.generar",
            return_value=(
                contenido,
                EvaluacionCalidad(anclaje_fuente_score=0.9, claridad_pedagogica="Alta", observaciones="ok"),
            ),
        ),
        patch("nuevamente.almacenamiento.guardar", return_value="clave.json"),
    ):
        respuesta = procesar(hacer_solicitud(formato))

    assert type(respuesta.contenido_adaptado) is type(contenido)
    assert respuesta.metadatos.formato_generado == formato
    assert (respuesta.metadatos.tiempo_estimado_estudio_minutos, respuesta.metadatos.conceptos_clave) == ESPERADO[formato]
    assert respuesta.model_dump()["contenido_adaptado"] == contenido.model_dump()
