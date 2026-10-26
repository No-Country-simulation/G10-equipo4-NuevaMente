"""Acciones que la UI le pide al servidor, compartidas por main.py (IA real) y demo.py (contenido de ejemplo).

No depende de Streamlit: `estado` es cualquier diccionario (en la app, st.session_state), y
las funciones que generan o responden se reciben como parametros. Asi se prueba sin red ni LLM.
"""

from __future__ import annotations

import base64
import binascii
import logging
from collections.abc import Callable, MutableMapping

from historial import agregar_material

from nuevamente.contratos import Respuesta, Solicitud
from nuevamente.errores import describir_error
from nuevamente.ingesta import leer_documento

logger = logging.getLogger(__name__)

ACCIONES_DE_GENERACION = ("generar", "ruta", "comparar")
RUTA_FORMATOS = ("TLDR", "Flashcards", "Quiz")  # entender -> memorizar -> comprobar
PERFILES = ("Principiante", "Junior", "Lider Tecnico", "Ejecutivo")
IDIOMAS = ("Español", "Português", "English")
VALORACIONES = ("util", "no_util")
MAX_PREGUNTAS_POR_MATERIAL = 20
ETIQUETAS = {"Lider Tecnico": "Líder técnico"}

Procesar = Callable[..., Respuesta]
Preguntar = Callable[..., dict]


def etiqueta(valor: str) -> str:
    return ETIQUETAS.get(valor, valor)


def iniciar_estado(estado: MutableMapping) -> None:
    for clave in ("resultado", "ultimo_id", "ultimo_id_accion", "error"):
        estado.setdefault(clave, None)
    for clave in ("historial",):
        estado.setdefault(clave, [])
    for clave in ("documentos", "conversaciones", "valoraciones"):
        estado.setdefault(clave, {})


# ---------- Lectura del archivo ----------


def leer_archivo(valor: dict) -> tuple[str, bytes, str]:
    nombre = valor.get("archivo_nombre") or ""
    try:
        contenido = base64.b64decode(valor["archivo_base64"], validate=True)
    except (binascii.Error, TypeError, KeyError) as exc:
        raise ValueError("No se pudo leer el archivo enviado. Vuelve a seleccionarlo e inténtalo de nuevo.") from exc
    texto = leer_documento(nombre, contenido)
    if not texto.strip():
        raise ValueError(
            "No se pudo extraer texto del documento. "
            "Si es un PDF escaneado, prueba con uno que tenga texto seleccionable."
        )
    return nombre, contenido, texto


def _solicitud(valor: dict, texto: str, *, formato: str | None = None, perfil: str | None = None,
               ajustes: list[str] | None = None) -> Solicitud:
    idioma = valor.get("idioma") or "Español"
    if idioma not in IDIOMAS:
        raise ValueError("Idioma de salida no soportado.")
    return Solicitud(
        documento_titulo=valor["archivo_nombre"],
        documento_contenido=texto,
        perfil_destinatario=perfil or valor["perfil"],
        formato_salida=formato or valor["formato"],
        nicho_sector=valor["nicho"],
        nivel_detalle=valor["nivel"],
        idioma_salida=idioma,
        ajustes=list(ajustes or []),
    )


# ---------- Generacion: un material, una ruta o una comparacion ----------


def _generar(valor: dict, texto: str, procesar: Procesar) -> dict:
    ajustes = valor.get("ajustes") or []
    solicitud = _solicitud(valor, texto, ajustes=ajustes)
    # Regenerar (con o sin ajustes) siempre pide una version nueva al modelo
    respuesta = procesar(solicitud, usar_cache=not (valor.get("regenerar") or ajustes))
    return {**respuesta.model_dump(), "id_solicitud": valor["id"], "ajustes": list(ajustes)}


def _ruta(valor: dict, texto: str, procesar: Procesar) -> dict:
    pasos = []
    for formato in RUTA_FORMATOS:
        respuesta = procesar(_solicitud(valor, texto, formato=formato), usar_cache=True)
        pasos.append({**respuesta.model_dump(), "id_solicitud": f"{valor['id']}-{formato}"})
    minutos = sum(paso["metadatos"]["tiempo_estimado_estudio_minutos"] for paso in pasos)
    return {
        "tipo": "ruta",
        "id_solicitud": valor["id"],
        "contenido_adaptado": {"titulo": f"Ruta de estudio · {valor['archivo_nombre']}"},
        "metadatos": {
            "formato_generado": "Ruta",
            "perfil_aplicado": valor["perfil"],
            "tiempo_estimado_estudio_minutos": minutos,
            "idioma_salida": valor.get("idioma") or "Español",
        },
        "pasos": pasos,
    }


def _comparar(valor: dict, texto: str, procesar: Procesar) -> dict:
    perfil_a, perfil_b = valor["perfil"], valor.get("perfil_b")
    if perfil_b not in PERFILES or perfil_b == perfil_a:
        raise ValueError("Elige un perfil distinto al tuyo para comparar.")
    versiones = []
    for perfil in (perfil_a, perfil_b):
        respuesta = procesar(_solicitud(valor, texto, perfil=perfil), usar_cache=True)
        versiones.append({**respuesta.model_dump(), "id_solicitud": f"{valor['id']}-{perfil}"})
    return {
        "tipo": "comparacion",
        "id_solicitud": valor["id"],
        "contenido_adaptado": {"titulo": f"Comparación de perfiles · {valor['archivo_nombre']}"},
        "metadatos": {
            "formato_generado": "Comparacion",
            "formato_comparado": valor["formato"],
            "perfil_aplicado": f"{etiqueta(perfil_a)} vs {etiqueta(perfil_b)}",
            "idioma_salida": valor.get("idioma") or "Español",
        },
        "versiones": versiones,
    }


_GENERADORES = {"generar": _generar, "ruta": _ruta, "comparar": _comparar}


def _podar(estado: MutableMapping) -> None:
    """Documentos y conversaciones solo se guardan para los materiales que siguen en el historial."""
    vigentes = {material["id"] for material in estado["historial"]}
    for clave in ("documentos", "conversaciones", "valoraciones"):
        estado[clave] = {k: v for k, v in estado[clave].items() if k in vigentes}


def _ejecutar_generacion(valor: dict, estado: MutableMapping, procesar: Procesar, guardar_original) -> None:
    try:
        nombre, contenido, texto = leer_archivo(valor)
        guardar_original(nombre, contenido)
        resultado = _GENERADORES[valor["accion"]](valor, texto, procesar)
        estado["resultado"] = resultado
        estado["error"] = None
        estado["historial"] = agregar_material(estado["historial"], resultado, valor)
        estado["documentos"] = {
            **estado["documentos"],
            resultado["id_solicitud"]: {"titulo": nombre, "texto": texto, "idioma": valor.get("idioma") or "Español"},
        }
        _podar(estado)
    except Exception as exc:  # cualquier fallo se traduce a un aviso claro en la UI
        logger.exception("Fallo al generar contenido")
        estado["error"] = {**describir_error(exc), "id": valor["id"]}


# ---------- Preguntas y valoraciones ----------


def _ejecutar_pregunta(valor: dict, estado: MutableMapping, preguntar: Preguntar) -> None:
    id_material = valor.get("id_material")
    pregunta = str(valor.get("pregunta") or "")[:1000]
    mensaje = {"id": valor["id"], "pregunta": pregunta}
    documento = estado["documentos"].get(id_material)
    try:
        if documento is None:
            raise ValueError("Este material ya no tiene su documento a mano. Vuelve a generarlo para hacer preguntas.")
        historial = estado["conversaciones"].get(id_material, [])
        if len(historial) >= MAX_PREGUNTAS_POR_MATERIAL:
            raise ValueError(f"Llegaste al máximo de {MAX_PREGUNTAS_POR_MATERIAL} preguntas para este material.")
        mensaje.update(preguntar(documento["titulo"], documento["texto"], pregunta, documento["idioma"]))
    except Exception as exc:
        logger.warning("No se pudo responder la pregunta", exc_info=True)
        mensaje["error"] = describir_error(exc)
    if id_material is not None:
        estado["conversaciones"] = {
            **estado["conversaciones"],
            id_material: [*estado["conversaciones"].get(id_material, []), mensaje],
        }


def _ejecutar_valoracion(valor: dict, estado: MutableMapping, registrar) -> None:
    id_material, calificacion = valor.get("id_material"), valor.get("valor")
    if calificacion not in VALORACIONES or id_material is None:
        return
    estado["valoraciones"] = {**estado["valoraciones"], id_material: calificacion}
    material = next((m for m in estado["historial"] if m["id"] == id_material), {})
    datos = {
        "id_material": id_material,
        "valor": calificacion,
        "formato": material.get("formato"),
        "perfil": material.get("perfil"),
        "ajustes": (material.get("resultado") or {}).get("ajustes", []),
    }
    try:
        registrar(datos)
    except Exception:  # la valoracion es opcional: nunca debe romper la app
        logger.warning("No se pudo registrar la valoracion", exc_info=True)


# ---------- Punto de entrada ----------


def ejecutar_accion(
    valor: dict | None,
    estado: MutableMapping,
    *,
    procesar: Procesar,
    preguntar: Preguntar,
    guardar_original: Callable[[str, bytes], None] = lambda _nombre, _contenido: None,
    registrar_valoracion: Callable[[dict], None] = lambda _datos: None,
) -> bool:
    """Ejecuta la accion nueva que envio la UI. Devuelve True si hizo algo (hay que redibujar).

    El componente conserva su ultimo valor entre recargas: cada accion trae un id y solo se
    ejecuta una vez.
    """
    if not isinstance(valor, dict):
        return False
    accion = valor.get("accion")
    if accion in ACCIONES_DE_GENERACION:
        if valor.get("id") == estado["ultimo_id"]:
            return False
        estado["ultimo_id"] = valor.get("id")
        _ejecutar_generacion(valor, estado, procesar, guardar_original)
        return True
    if accion in ("preguntar", "valorar"):
        if valor.get("id") == estado["ultimo_id_accion"]:
            return False
        estado["ultimo_id_accion"] = valor.get("id")
        if accion == "preguntar":
            _ejecutar_pregunta(valor, estado, preguntar)
        else:
            _ejecutar_valoracion(valor, estado, registrar_valoracion)
        return True
    return False
