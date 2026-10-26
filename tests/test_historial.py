"""Historial de la sesion ("Mis materiales")."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from historial import (  # va despues de agregar app/ al path
    MAXIMO_MATERIALES,
    agregar_material,
)

SOLICITUD = {"archivo_nombre": "vcn.md", "perfil": "Junior", "formato": "Quiz", "nivel": "Didactico"}


def resultado(id_solicitud, titulo="VCN"):
    return {
        "id_solicitud": id_solicitud,
        "contenido_adaptado": {"titulo": titulo},
        "metadatos": {"formato_generado": "Quiz", "perfil_aplicado": "Junior"},
    }


def test_agrega_al_principio_con_los_datos_para_la_tarjeta():
    historial = agregar_material([], resultado(1, "Redes VCN"), SOLICITUD, ahora_ms=123)

    assert historial == [
        {
            "id": 1,
            "titulo": "Redes VCN",
            "formato": "Quiz",
            "perfil": "Junior",
            "nivel": "Didactico",
            "archivo": "vcn.md",
            "creado_ms": 123,
            "resultado": resultado(1, "Redes VCN"),
        }
    ]


def test_lo_mas_nuevo_va_primero_y_no_modifica_la_lista_original():
    original = agregar_material([], resultado(1), SOLICITUD)
    nuevo = agregar_material(original, resultado(2), SOLICITUD)

    assert [m["id"] for m in nuevo] == [2, 1]
    assert [m["id"] for m in original] == [1]


def test_el_mismo_id_no_se_duplica():
    historial = agregar_material([], resultado(1, "v1"), SOLICITUD)
    historial = agregar_material(historial, resultado(1, "v2"), SOLICITUD)

    assert len(historial) == 1
    assert historial[0]["titulo"] == "v2"


def test_respeta_el_maximo():
    historial = None
    for i in range(MAXIMO_MATERIALES + 3):
        historial = agregar_material(historial, resultado(i), SOLICITUD)

    assert len(historial) == MAXIMO_MATERIALES
    assert historial[0]["id"] == MAXIMO_MATERIALES + 2


@pytest.mark.parametrize("contenido", [{}, {"titulo": ""}])
def test_sin_titulo_usa_el_nombre_del_archivo(contenido):
    datos = {**resultado(1), "contenido_adaptado": contenido}
    assert agregar_material([], datos, SOLICITUD)[0]["titulo"] == "vcn.md"
