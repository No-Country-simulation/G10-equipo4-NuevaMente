import json

from nuevamente import cache
from nuevamente.contratos import Chunk
from tests.helpers_contenido import contenido, evaluacion, solicitud


def test_guardar_y_obtener_devuelve_lo_mismo():
    sol = solicitud()
    assert cache.guardar(sol, contenido(), evaluacion(0.9)) is True

    obtenido = cache.obtener(sol)

    assert obtenido is not None
    assert obtenido[0] == contenido()
    assert obtenido[1].anclaje_fuente_score == 0.9
    assert obtenido[2] == []


def test_las_fuentes_se_guardan_y_se_recuperan():
    sol = solicitud()
    fuentes = [Chunk(texto="fragmento uno", fuente="doc · fragmento 1 de 2")]
    cache.guardar(sol, contenido(), evaluacion(), fuentes)

    assert cache.obtener(sol)[2] == fuentes


def test_entrada_sin_fuentes_de_una_version_vieja_se_ignora():
    sol = solicitud()
    cache.guardar(sol, contenido(), evaluacion())
    archivo = next(cache._directorio().glob("*.json"))
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    del datos["fuentes"]
    archivo.write_text(json.dumps(datos), encoding="utf-8")

    assert cache.obtener(sol) is None


def test_sin_entrada_devuelve_none():
    assert cache.obtener(solicitud()) is None


def test_no_guarda_si_el_anclaje_es_bajo():
    sol = solicitud()
    assert cache.guardar(sol, contenido(), evaluacion(0.5)) is False
    assert cache.obtener(sol) is None


def test_solicitudes_distintas_no_se_mezclan():
    cache.guardar(solicitud(perfil="Principiante"), contenido(), evaluacion())
    assert cache.obtener(solicitud(perfil="Ejecutivo")) is None


def test_entrada_corrupta_se_ignora():
    sol = solicitud()
    cache.guardar(sol, contenido(), evaluacion())
    archivo = next(cache._directorio().glob("*.json"))
    archivo.write_text("esto no es json", encoding="utf-8")

    assert cache.obtener(sol) is None


def test_entrada_con_esquema_viejo_se_ignora():
    sol = solicitud()
    cache.guardar(sol, contenido(), evaluacion())
    archivo = next(cache._directorio().glob("*.json"))
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    datos["contenido"] = {"titulo": "solo titulo"}  # faltan campos obligatorios
    archivo.write_text(json.dumps(datos), encoding="utf-8")

    assert cache.obtener(sol) is None