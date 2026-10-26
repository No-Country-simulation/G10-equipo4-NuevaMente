"""Acciones de la UI: generar, ruta de estudio, comparar perfiles, preguntar y valorar."""

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from flujo import (  # va despues de agregar app/ al path
    MAX_PREGUNTAS_POR_MATERIAL,
    RUTA_FORMATOS,
    ejecutar_accion,
    iniciar_estado,
)

from nuevamente.contratos import (
    AlmacenamientoOCI,
    EvaluacionCalidad,
    Metadatos,
    Respuesta,
    _prerrequisitos,
    _resumir_contenido,
)
from tests.helpers_contenido import contenido

TEXTO = "# VCN\n\nUna VCN es una red privada.\n\nEl NAT Gateway da salida a internet."


class Registro:
    """Dobles de procesar / preguntar que anotan con que se los llamo."""

    def __init__(self, falla=None):
        self.solicitudes, self.usar_cache, self.preguntas = [], [], []
        self.falla = falla

    def procesar(self, solicitud, usar_cache=True):
        if self.falla:
            raise self.falla
        self.solicitudes.append(solicitud)
        self.usar_cache.append(usar_cache)
        cont = contenido(solicitud.formato_salida)
        minutos, conceptos = _resumir_contenido(cont)
        return Respuesta(
            status="exito",
            metadatos=Metadatos(
                perfil_aplicado=solicitud.perfil_destinatario, formato_generado=solicitud.formato_salida,
                tiempo_estimado_estudio_minutos=minutos, conceptos_clave=conceptos,
                prerrequisitos=_prerrequisitos(solicitud), idioma_salida=solicitud.idioma_salida,
            ),
            contenido_adaptado=cont,
            evaluacion_calidad=EvaluacionCalidad(anclaje_fuente_score=0.9, claridad_pedagogica="Alta", observaciones="ok"),
            almacenamiento_oci=AlmacenamientoOCI(bucket="b", objeto_id="o", status_upload="completado"),
        )

    def preguntar(self, titulo, texto, pregunta, idioma):
        self.preguntas.append((titulo, texto, pregunta, idioma))
        return {"respuesta": f"R: {pregunta}", "en_documento": True, "fuentes": [{"texto": "t", "fuente": "f"}]}


def valor(accion="generar", id_=1, **extra):
    base = {
        "accion": accion, "id": id_, "archivo_nombre": "vcn.md",
        "archivo_base64": base64.b64encode(TEXTO.encode()).decode(),
        "perfil": "Principiante", "formato": "Quiz", "nicho": "General", "nivel": "Didactico", "idioma": "Español",
    }
    return {**base, **extra}


@pytest.fixture
def estado():
    datos = {}
    iniciar_estado(datos)
    return datos


def correr(estado, registro, v, **kwargs):
    return ejecutar_accion(v, estado, procesar=registro.procesar, preguntar=registro.preguntar, **kwargs)


# ---------- generar ----------


def test_generar_guarda_resultado_historial_y_documento(estado):
    registro = Registro()
    assert correr(estado, registro, valor()) is True

    assert estado["resultado"]["id_solicitud"] == 1
    assert estado["error"] is None
    assert [m["id"] for m in estado["historial"]] == [1]
    assert estado["documentos"][1]["texto"] == TEXTO


def test_la_misma_accion_no_se_ejecuta_dos_veces(estado):
    registro = Registro()
    correr(estado, registro, valor())
    assert correr(estado, registro, valor()) is False
    assert len(registro.solicitudes) == 1


def test_idioma_llega_a_la_solicitud(estado):
    registro = Registro()
    correr(estado, registro, valor(idioma="Português"))

    assert registro.solicitudes[0].idioma_salida == "Português"
    assert estado["resultado"]["metadatos"]["idioma_salida"] == "Português"


def test_idioma_no_soportado_es_un_error_claro(estado):
    correr(estado, Registro(), valor(idioma="Klingon"))
    assert "idioma" in estado["error"]["mensaje"].lower()


def test_regenerar_con_ajustes_no_usa_la_cache(estado):
    registro = Registro()
    correr(estado, registro, valor(id_=1))
    correr(estado, registro, valor(id_=2, regenerar=True, ajustes=["mas_ejemplos", "mas_corto"]))

    assert registro.usar_cache == [True, False]
    assert registro.solicitudes[1].ajustes == ["mas_ejemplos", "mas_corto"]
    assert estado["resultado"]["ajustes"] == ["mas_ejemplos", "mas_corto"]


def test_ajuste_desconocido_es_rechazado(estado):
    correr(estado, Registro(), valor(ajustes=["borrar_todo"]))
    assert estado["error"] is not None
    assert estado["historial"] == []


def test_si_procesar_falla_se_guarda_el_error(estado):
    correr(estado, Registro(falla=RuntimeError("503 Service Unavailable")), valor())

    assert estado["error"]["id"] == 1
    assert "conectar" in estado["error"]["titulo"].lower()
    assert estado["historial"] == []


# ---------- ruta de estudio ----------


def test_ruta_genera_tldr_tarjetas_y_quiz_en_orden(estado):
    registro = Registro()
    correr(estado, registro, valor("ruta", formato="Guion"))

    resultado = estado["resultado"]
    assert resultado["tipo"] == "ruta"
    assert [s.formato_salida for s in registro.solicitudes] == list(RUTA_FORMATOS) == ["TLDR", "Flashcards", "Quiz"]
    assert [p["metadatos"]["formato_generado"] for p in resultado["pasos"]] == ["TLDR", "Flashcards", "Quiz"]
    assert resultado["metadatos"]["tiempo_estimado_estudio_minutos"] == sum(
        p["metadatos"]["tiempo_estimado_estudio_minutos"] for p in resultado["pasos"]
    )
    assert estado["historial"][0]["formato"] == "Ruta"


# ---------- comparar perfiles ----------


def test_comparar_genera_una_version_por_perfil(estado):
    registro = Registro()
    correr(estado, registro, valor("comparar", perfil_b="Lider Tecnico"))

    resultado = estado["resultado"]
    assert resultado["tipo"] == "comparacion"
    assert [s.perfil_destinatario for s in registro.solicitudes] == ["Principiante", "Lider Tecnico"]
    assert [v["metadatos"]["perfil_aplicado"] for v in resultado["versiones"]] == ["Principiante", "Lider Tecnico"]
    assert estado["historial"][0]["perfil"] == "Principiante vs Líder técnico"


@pytest.mark.parametrize("perfil_b", ["Principiante", None, "Astronauta"])
def test_comparar_exige_otro_perfil_valido(estado, perfil_b):
    correr(estado, Registro(), valor("comparar", perfil_b=perfil_b))
    assert "perfil distinto" in estado["error"]["mensaje"]


# ---------- preguntas ----------


def test_preguntar_usa_el_documento_del_material(estado):
    registro = Registro()
    correr(estado, registro, valor(idioma="English"))
    correr(estado, registro, {"accion": "preguntar", "id": "p1", "id_material": 1, "pregunta": "¿Qué es NAT?"})

    assert registro.preguntas == [("vcn.md", TEXTO, "¿Qué es NAT?", "English")]
    mensajes = estado["conversaciones"][1]
    assert mensajes[0]["respuesta"] == "R: ¿Qué es NAT?"
    assert mensajes[0]["fuentes"]


def test_preguntar_sin_documento_deja_un_error_en_la_conversacion(estado):
    correr(estado, Registro(), {"accion": "preguntar", "id": "p1", "id_material": 99, "pregunta": "hola que tal"})
    assert "vuelve a generarlo" in estado["conversaciones"][99][0]["error"]["mensaje"].lower()


def test_preguntar_tiene_un_maximo_por_material(estado):
    registro = Registro()
    correr(estado, registro, valor())
    for i in range(MAX_PREGUNTAS_POR_MATERIAL + 1):
        correr(estado, registro, {"accion": "preguntar", "id": f"p{i}", "id_material": 1, "pregunta": f"pregunta {i}"})

    mensajes = estado["conversaciones"][1]
    assert len(registro.preguntas) == MAX_PREGUNTAS_POR_MATERIAL
    assert "máximo" in mensajes[-1]["error"]["mensaje"]


# ---------- valoraciones ----------


def test_valorar_guarda_y_registra_sin_datos_del_documento(estado):
    registro, registradas = Registro(), []
    correr(estado, registro, valor())
    correr(estado, registro, {"accion": "valorar", "id": "v1", "id_material": 1, "valor": "no_util"},
           registrar_valoracion=registradas.append)

    assert estado["valoraciones"] == {1: "no_util"}
    assert registradas == [{"id_material": 1, "valor": "no_util", "formato": "Quiz", "perfil": "Principiante", "ajustes": []}]


def test_valoracion_invalida_se_ignora(estado):
    correr(estado, Registro(), {"accion": "valorar", "id": "v1", "id_material": 1, "valor": "<script>"})
    assert estado["valoraciones"] == {}


def test_si_registrar_falla_la_app_sigue(estado):
    def registrar(_datos):
        raise RuntimeError("sin red")

    correr(estado, Registro(), valor())
    correr(estado, Registro(), {"accion": "valorar", "id": "v1", "id_material": 1, "valor": "util"}, registrar_valoracion=registrar)
    assert estado["valoraciones"] == {1: "util"}


# ---------- limpieza ----------


def test_documentos_y_conversaciones_se_limpian_con_el_historial(estado):
    registro = Registro()
    for i in range(1, 11):  # el historial guarda 8
        correr(estado, registro, valor(id_=i))
        correr(estado, registro, {"accion": "preguntar", "id": f"p{i}", "id_material": i, "pregunta": "¿qué es?"})

    vigentes = {m["id"] for m in estado["historial"]}
    assert set(estado["documentos"]) == vigentes
    assert set(estado["conversaciones"]) <= vigentes | {10}
    assert 1 not in estado["documentos"]


def test_valores_que_no_son_acciones_se_ignoran(estado):
    for v in (None, "texto", {}, {"accion": "tema", "tema": "oscuro"}, {"accion": "desconocida", "id": 1}):
        assert ejecutar_accion(v, estado, procesar=Registro().procesar, preguntar=Registro().preguntar) is False
