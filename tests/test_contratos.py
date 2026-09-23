from unittest.mock import patch

import pytest
from pydantic import ValidationError

from nuevamente.contratos import Chunk, ContenidoAdaptado, EvaluacionCalidad, ItemFlashcard, Solicitud, procesar


def hacer_solicitud_de_ejemplo(**overrides) -> Solicitud:
    base = {
        "documento_titulo": "Introduccion a la Arquitectura de Redes VCN en OCI",
        "documento_contenido": "La VCN es una red privada en OCI...",
        "perfil_destinatario": "Principiante",
        "formato_salida": "Flashcards",
        "nicho_sector": "General",
        "nivel_detalle": "Didactico",
    }
    base.update(overrides)
    return Solicitud(**base)


def hacer_contenido() -> ContenidoAdaptado:
    return ContenidoAdaptado(
        titulo="VCN explicada",
        introduccion_contextualizada="Intro",
        items=[ItemFlashcard(frente="Que es VCN", dorso="Red privada", pista_didactica="Piensa en un barrio")],
    )


def test_solicitud_valida_no_falla():
    hacer_solicitud_de_ejemplo()


def test_perfil_invalido_falla():
    with pytest.raises(ValidationError):
        hacer_solicitud_de_ejemplo(perfil_destinatario="Astronauta")


def test_formato_invalido_falla():
    with pytest.raises(ValidationError):
        hacer_solicitud_de_ejemplo(formato_salida="Poema")


def test_procesar_devuelve_respuesta_completa():
    with (
        patch("nuevamente.rag.indexar", return_value=3),
        patch("nuevamente.rag.recuperar", return_value=[Chunk(texto="fuente", fuente="doc1")]),
        patch(
            "nuevamente.agentes.generar",
            return_value=(
                hacer_contenido(),
                EvaluacionCalidad(anclaje_fuente_score=0.9, claridad_pedagogica="Alta", observaciones="ok"),
            ),
        ),
        patch("nuevamente.almacenamiento.guardar", return_value="clave.json"),
    ):
        respuesta = procesar(hacer_solicitud_de_ejemplo())

    assert respuesta.status == "exito"
    assert respuesta.metadatos.perfil_aplicado == "Principiante"
    assert len(respuesta.contenido_adaptado.items) >= 1
    assert 0.0 <= respuesta.evaluacion_calidad.anclaje_fuente_score <= 1.0
    assert respuesta.almacenamiento_oci.status_upload == "completado"


def test_procesar_respeta_el_perfil_que_le_pasan():
    with (
        patch("nuevamente.rag.indexar", return_value=3),
        patch("nuevamente.rag.recuperar", return_value=[Chunk(texto="fuente", fuente="doc1")]),
        patch(
            "nuevamente.agentes.generar",
            return_value=(
                hacer_contenido(),
                EvaluacionCalidad(anclaje_fuente_score=0.9, claridad_pedagogica="Alta", observaciones="ok"),
            ),
        ),
        patch("nuevamente.almacenamiento.guardar", return_value="clave.json"),
    ):
        respuesta = procesar(hacer_solicitud_de_ejemplo(perfil_destinatario="Ejecutivo"))

    assert respuesta.metadatos.perfil_aplicado == "Ejecutivo"


def test_procesar_marca_fallido_si_almacenamiento_falla():
    with (
        patch("nuevamente.rag.indexar", return_value=3),
        patch("nuevamente.rag.recuperar", return_value=[Chunk(texto="fuente", fuente="doc1")]),
        patch(
            "nuevamente.agentes.generar",
            return_value=(
                hacer_contenido(),
                EvaluacionCalidad(anclaje_fuente_score=0.9, claridad_pedagogica="Alta", observaciones="ok"),
            ),
        ),
        patch("nuevamente.almacenamiento.guardar", side_effect=Exception("sin credenciales")),
    ):
        respuesta = procesar(hacer_solicitud_de_ejemplo())

    assert respuesta.almacenamiento_oci.status_upload == "fallido"
