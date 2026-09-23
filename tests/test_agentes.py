from unittest.mock import patch

from nuevamente.agentes import generar
from nuevamente.contratos import Chunk, ContenidoAdaptado, EvaluacionCalidad, ItemFlashcard, Solicitud


def hacer_solicitud() -> Solicitud:
    return Solicitud(
        documento_titulo="Titulo",
        documento_contenido="Contenido",
        perfil_destinatario="Principiante",
        formato_salida="Flashcards",
        nicho_sector="General",
        nivel_detalle="Didactico",
    )


def hacer_contenido(titulo: str) -> ContenidoAdaptado:
    return ContenidoAdaptado(
        titulo=titulo,
        introduccion_contextualizada="Intro",
        items=[ItemFlashcard(frente="P", dorso="R", pista_didactica="Pista")],
    )


def test_generar_no_reintenta_si_el_anclaje_es_bueno():
    chunks = [Chunk(texto="fuente", fuente="doc1")]
    with (
        patch("nuevamente.agentes._investigar", return_value="hallazgos"),
        patch("nuevamente.agentes._redactar", return_value=hacer_contenido("v1")) as redactar,
        patch(
            "nuevamente.agentes._criticar",
            return_value=EvaluacionCalidad(anclaje_fuente_score=0.9, claridad_pedagogica="Alta", observaciones="ok"),
        ) as criticar,
    ):
        contenido, evaluacion = generar(hacer_solicitud(), chunks)

    assert contenido.titulo == "v1"
    assert evaluacion.anclaje_fuente_score == 0.9
    redactar.assert_called_once()
    criticar.assert_called_once()


def test_generar_reintenta_si_el_anclaje_es_bajo():
    chunks = [Chunk(texto="fuente", fuente="doc1")]
    with (
        patch("nuevamente.agentes._investigar", return_value="hallazgos"),
        patch(
            "nuevamente.agentes._redactar",
            side_effect=[hacer_contenido("v1"), hacer_contenido("v2")],
        ) as redactar,
        patch(
            "nuevamente.agentes._criticar",
            side_effect=[
                EvaluacionCalidad(anclaje_fuente_score=0.3, claridad_pedagogica="Baja", observaciones="mal"),
                EvaluacionCalidad(anclaje_fuente_score=0.9, claridad_pedagogica="Alta", observaciones="ok"),
            ],
        ) as criticar,
    ):
        contenido, evaluacion = generar(hacer_solicitud(), chunks)

    assert contenido.titulo == "v2"
    assert evaluacion.anclaje_fuente_score == 0.9
    assert redactar.call_count == 2
    assert criticar.call_count == 2


def test_generar_para_en_el_maximo_de_intentos():
    chunks = [Chunk(texto="fuente", fuente="doc1")]
    evaluacion_mala = EvaluacionCalidad(anclaje_fuente_score=0.1, claridad_pedagogica="Baja", observaciones="mal")
    with (
        patch("nuevamente.agentes._investigar", return_value="hallazgos"),
        patch(
            "nuevamente.agentes._redactar",
            side_effect=[hacer_contenido("v1"), hacer_contenido("v2")],
        ) as redactar,
        patch("nuevamente.agentes._criticar", return_value=evaluacion_mala) as criticar,
    ):
        contenido, evaluacion = generar(hacer_solicitud(), chunks)

    assert contenido.titulo == "v2"
    assert evaluacion.anclaje_fuente_score == 0.1
    assert redactar.call_count == 2
    assert criticar.call_count == 2
