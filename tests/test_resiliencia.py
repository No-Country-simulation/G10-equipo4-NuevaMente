import pytest

from nuevamente import resiliencia


class LLMFalso:
    """Imita la parte de la API de LangChain que usa invocar_con_espera."""

    def __init__(self, errores, respuesta="ok"):
        self.errores = list(errores)
        self.respuesta = respuesta
        self.llamadas = 0

    def with_retry(self, **_kwargs):
        return self

    def invoke(self, _prompt):
        self.llamadas += 1
        if self.errores:
            raise self.errores.pop(0)
        return self.respuesta


@pytest.fixture
def esperas_registradas(monkeypatch):
    registro = []
    monkeypatch.setattr(resiliencia, "dormir", registro.append)
    return registro


@pytest.mark.parametrize(
    "mensaje",
    [
        "429 Too Many Requests",
        "RESOURCE_EXHAUSTED: cuota excedida",
        "You exceeded your current quota",
        "Rate limit reached",
    ],
)
def test_detecta_errores_de_cuota(mensaje):
    assert resiliencia.es_limite_de_cuota(RuntimeError(mensaje)) is True


def test_no_confunde_otros_errores_con_cuota():
    assert resiliencia.es_limite_de_cuota(RuntimeError("503 Service Unavailable")) is False
    assert resiliencia.es_limite_de_cuota(ValueError("JSON invalido")) is False


def test_sin_errores_no_espera(esperas_registradas):
    llm = LLMFalso([], respuesta="listo")

    assert resiliencia.invocar_con_espera(llm, "p") == "listo"
    assert esperas_registradas == []


def test_espera_y_reintenta_ante_cuota(esperas_registradas):
    llm = LLMFalso([RuntimeError("429 quota"), RuntimeError("429 quota")], respuesta="listo")

    assert resiliencia.invocar_con_espera(llm, "p") == "listo"
    assert esperas_registradas == [5, 15]
    assert llm.llamadas == 3


def test_agotadas_las_esperas_propaga_el_error(esperas_registradas):
    llm = LLMFalso([RuntimeError("429 quota")] * 10)

    with pytest.raises(RuntimeError, match="429"):
        resiliencia.invocar_con_espera(llm, "p", esperas=(1, 2))

    assert esperas_registradas == [1, 2]
    assert llm.llamadas == 3


def test_error_que_no_es_de_cuota_no_espera(esperas_registradas):
    llm = LLMFalso([ValueError("JSON invalido")])

    with pytest.raises(ValueError):
        resiliencia.invocar_con_espera(llm, "p")

    assert esperas_registradas == []
    assert llm.llamadas == 1