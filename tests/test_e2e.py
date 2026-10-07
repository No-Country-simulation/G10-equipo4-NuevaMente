"""Flujo completo procesar(): ingesta -> RAG -> agentes -> almacenamiento, con las
piezas externas (ChromaDB, LLM, OCI) reemplazadas por dobles."""

import pytest

from nuevamente.contratos import Chunk, Respuesta, procesar
from tests.helpers_contenido import contenido, evaluacion, solicitud


@pytest.fixture
def piezas(monkeypatch):
    """Parchea indexar/recuperar/generar/guardar y cuenta cuantas veces se llama a cada uno."""
    llamadas = {"indexar": 0, "recuperar": 0, "generar": 0, "guardar": []}
    estado = {"score": 0.9, "guardar_falla": False}

    def indexar(doc_id, texto):
        llamadas["indexar"] += 1
        return 3

    def recuperar(doc_id, consulta, k=5):
        llamadas["recuperar"] += 1
        return [Chunk(texto="fragmento", fuente=f"{doc_id} · fragmento 1 de 3")]

    def generar(sol, chunks):
        llamadas["generar"] += 1
        return contenido(sol.formato_salida), evaluacion(estado["score"])

    def guardar(clave, datos):
        if estado["guardar_falla"]:
            raise RuntimeError("OCI no disponible")
        llamadas["guardar"].append(clave)

    monkeypatch.setattr("nuevamente.rag.indexar", indexar)
    monkeypatch.setattr("nuevamente.rag.recuperar", recuperar)
    monkeypatch.setattr("nuevamente.agentes.generar", generar)
    monkeypatch.setattr("nuevamente.almacenamiento.guardar", guardar)
    return llamadas, estado


@pytest.mark.parametrize("formato", ["Flashcards", "Tutorial", "Quiz", "TLDR", "Guion"])
def test_flujo_completo_por_formato(piezas, formato):
    respuesta = procesar(solicitud(formato=formato))

    assert isinstance(respuesta, Respuesta)
    assert respuesta.status == "exito"
    assert respuesta.metadatos.formato_generado == formato
    assert respuesta.metadatos.tiempo_estimado_estudio_minutos >= 1
    assert respuesta.metadatos.conceptos_clave
    assert respuesta.almacenamiento_oci.status_upload == "completado"


@pytest.mark.parametrize("perfil", ["Principiante", "Junior", "Lider Tecnico", "Ejecutivo"])
def test_cada_perfil_trae_prerrequisitos(piezas, perfil):
    respuesta = procesar(solicitud(perfil=perfil))

    assert respuesta.metadatos.perfil_aplicado == perfil
    assert respuesta.metadatos.prerrequisitos


def test_la_salida_json_se_puede_volver_a_validar(piezas):
    original = procesar(solicitud(formato="Quiz"))

    reconstruida = Respuesta.model_validate_json(original.model_dump_json())

    assert reconstruida == original


def test_si_guardar_falla_la_respuesta_marca_fallido(piezas):
    _, estado = piezas
    estado["guardar_falla"] = True

    respuesta = procesar(solicitud())

    assert respuesta.status == "exito"
    assert respuesta.almacenamiento_oci.status_upload == "fallido"


def test_segunda_solicitud_igual_sale_de_la_cache(piezas):
    llamadas, _ = piezas

    primera = procesar(solicitud())
    segunda = procesar(solicitud())

    assert llamadas["generar"] == 1
    assert llamadas["indexar"] == 1
    assert segunda.contenido_adaptado == primera.contenido_adaptado
    assert len(llamadas["guardar"]) == 2  # aun con cache, el resultado se sigue almacenando


def test_resultado_de_baja_calidad_no_se_cachea(piezas):
    llamadas, estado = piezas
    estado["score"] = 0.4

    procesar(solicitud())
    procesar(solicitud())

    assert llamadas["generar"] == 2


def test_solicitud_distinta_no_reutiliza_la_cache(piezas):
    llamadas, _ = piezas

    procesar(solicitud(perfil="Principiante"))
    procesar(solicitud(perfil="Ejecutivo"))

    assert llamadas["generar"] == 2
    
def test_la_respuesta_incluye_las_fuentes_usadas(piezas):
    respuesta = procesar(solicitud())

    assert [f.fuente for f in respuesta.fuentes] == ["intro-a-vcn-en-oci · fragmento 1 de 3"]


def test_las_fuentes_sobreviven_a_la_cache(piezas):
    primera = procesar(solicitud())
    segunda = procesar(solicitud())

    assert segunda.fuentes == primera.fuentes
    assert segunda.fuentes


def test_sin_cache_se_vuelve_a_generar(piezas):
    llamadas, _ = piezas

    procesar(solicitud())
    procesar(solicitud(), usar_cache=False)

    assert llamadas["generar"] == 2


def test_regenerar_deja_la_nueva_version_en_cache(piezas):
    llamadas, _ = piezas

    procesar(solicitud(), usar_cache=False)
    procesar(solicitud())

    assert llamadas["generar"] == 1