"""Traduce excepciones tecnicas a mensajes claros para la UI."""

from __future__ import annotations

from pydantic import ValidationError

from nuevamente.resiliencia import es_limite_de_cuota

PALABRAS_CREDENCIALES = ("401", "403", "api key", "api_key", "unauthenticated", "permission_denied", "access_token")
PALABRAS_CONEXION = (
    "connection", "connect", "timeout", "timed out", "refused", "unreachable",
    "name resolution", "502", "503", "504", "unavailable", "overloaded",
)
MAX_DETALLE = 300


def _resultado(titulo: str, mensaje: str, reintentable: bool, detalle: str = "") -> dict:
    return {"titulo": titulo, "mensaje": mensaje, "reintentable": reintentable, "detalle": detalle[:MAX_DETALLE]}


def describir_error(exc: BaseException) -> dict:
    """Devuelve {titulo, mensaje, reintentable, detalle} para mostrar al usuario."""
    detalle = f"{type(exc).__name__}: {exc}"
    texto = detalle.lower()

    if isinstance(exc, ValidationError):
        return _resultado(
            "El modelo devolvio un formato invalido",
            "La IA no respeto la estructura pedida. Suele arreglarse volviendo a generar.",
            True,
            detalle,
        )
    if isinstance(exc, ValueError):
        # Errores propios de la app (documento vacio, formato no soportado): ya vienen redactados para el usuario
        return _resultado("Documento no valido", str(exc), False)
    if isinstance(exc, KeyError) and exc.args and str(exc.args[0]).isupper():
        # El nombre de la variable queda solo en el detalle tecnico: el usuario final no necesita saberlo
        return _resultado(
            "Configuracion incompleta",
            "La aplicacion no esta configurada del todo. Avisa a quien administra la app.",
            False,
            detalle,
        )
    if es_limite_de_cuota(exc):
        return _resultado(
            "Limite de uso del modelo alcanzado",
            "El proveedor de IA recibio demasiadas solicitudes. Espera un minuto e intenta de nuevo.",
            True,
            detalle,
        )
    if any(palabra in texto for palabra in PALABRAS_CREDENCIALES):
        return _resultado(
            "El servicio de IA no esta disponible",
            "Hay un problema de configuracion con el servicio de IA. Avisa a quien administra la app.",
            False,
            detalle,
        )
    if any(palabra in texto for palabra in PALABRAS_CONEXION):
        return _resultado(
            "No se pudo conectar con el modelo",
            "El servicio de IA no responde o esta saturado. Intenta de nuevo en unos segundos.",
            True,
            detalle,
        )
    return _resultado(
        "Algo salio mal",
        "Ocurrio un error inesperado al generar el contenido. Intenta de nuevo; si el problema continua, avisa a quien administra la app.",
        True,
        detalle,
    )