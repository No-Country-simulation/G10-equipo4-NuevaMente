import pytest
from pydantic import BaseModel, ValidationError

from nuevamente.errores import MAX_DETALLE, describir_error


class _Modelo(BaseModel):
    numero: int


def _error_de_validacion():
    with pytest.raises(ValidationError) as info:
        _Modelo(numero="no es numero")
    return info.value


def test_error_de_validacion_es_reintentable():
    resultado = describir_error(_error_de_validacion())

    assert "formato" in resultado["titulo"].lower()
    assert resultado["reintentable"] is True


def test_valueerror_propio_conserva_su_mensaje():
    resultado = describir_error(ValueError("No se pudo extraer texto del documento."))

    assert resultado["mensaje"] == "No se pudo extraer texto del documento."
    assert resultado["reintentable"] is False


def test_variable_de_entorno_faltante_se_explica_sin_jerga():
    resultado = describir_error(KeyError("GEMINI_API_KEY"))

    assert "configuracion" in resultado["titulo"].lower()
    assert resultado["reintentable"] is False
    assert "GEMINI_API_KEY" in resultado["detalle"]  # el dato tecnico queda disponible para quien programa


@pytest.mark.parametrize("mensaje", ["429 Too Many Requests", "RESOURCE_EXHAUSTED", "quota exceeded"])
def test_cuota_se_explica_y_se_puede_reintentar(mensaje):
    resultado = describir_error(RuntimeError(mensaje))

    assert "limite" in resultado["titulo"].lower()
    assert resultado["reintentable"] is True


@pytest.mark.parametrize("mensaje", ["401 UNAUTHENTICATED", "ACCESS_TOKEN_TYPE_UNSUPPORTED", "API key not valid"])
def test_credenciales_invalidas_no_son_reintentables(mensaje):
    resultado = describir_error(RuntimeError(mensaje))

    assert "configuracion" in resultado["mensaje"].lower()
    assert resultado["reintentable"] is False


@pytest.mark.parametrize("mensaje", ["Connection refused", "503 Service Unavailable", "Read timed out"])
def test_fallas_de_conexion_son_reintentables(mensaje):
    resultado = describir_error(RuntimeError(mensaje))

    assert "conectar" in resultado["titulo"].lower()
    assert resultado["reintentable"] is True


def test_error_desconocido_tiene_mensaje_generico_y_detalle():
    resultado = describir_error(RuntimeError("algo raro"))

    assert resultado["titulo"] == "Algo salio mal"
    assert "algo raro" in resultado["detalle"]


def test_el_detalle_se_recorta():
    resultado = describir_error(RuntimeError("x" * 5000))

    assert len(resultado["detalle"]) == MAX_DETALLE


@pytest.mark.parametrize(
    "exc",
    [
        KeyError("GEMINI_API_KEY"),
        RuntimeError("401 UNAUTHENTICATED"),
        RuntimeError("429 quota"),
        RuntimeError("Connection refused"),
        RuntimeError("algo raro"),
    ],
)
def test_el_usuario_final_no_ve_jerga_tecnica(exc):
    resultado = describir_error(exc)
    visible = f"{resultado['titulo']} {resultado['mensaje']}"

    for jerga in (".env", "GEMINI", "API_KEY", "variable", "terminal"):
        assert jerga not in visible