from __future__ import annotations

import logging
import re
import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

PerfilDestinatario = Literal["Principiante", "Junior", "Lider Tecnico", "Ejecutivo"]
FormatoSalida = Literal["Flashcards", "Tutorial", "Quiz", "TLDR", "Guion"]
NichoSector = Literal["General", "Fintech", "Salud", "E-commerce"]
NivelDetalle = Literal["Didactico", "Intermedio", "Profundo"]
IdiomaSalida = Literal["Español", "Português", "English"]
AjusteRegeneracion = Literal["mas_ejemplos", "mas_corto", "mas_tecnico", "menos_jerga", "mas_elementos"]

# Instruccion extra que recibe el redactor por cada ajuste pedido al regenerar
INSTRUCCIONES_AJUSTE: dict[str, str] = {
    "mas_ejemplos": "Incluye mas ejemplos concretos y practicos tomados de los hallazgos.",
    "mas_corto": "Se mas breve: frases cortas y solo lo esencial.",
    "mas_tecnico": "Usa un tono mas tecnico y preciso, con la terminologia correcta del documento.",
    "menos_jerga": "Evita la jerga tecnica; si un termino es imprescindible, explicalo con palabras simples.",
    "mas_elementos": "Genera la cantidad maxima de elementos permitida para este formato.",
}


class Solicitud(BaseModel):
    documento_titulo: str
    documento_contenido: str
    perfil_destinatario: PerfilDestinatario
    formato_salida: FormatoSalida
    nicho_sector: NichoSector
    nivel_detalle: NivelDetalle
    idioma_salida: IdiomaSalida = "Español"
    ajustes: list[AjusteRegeneracion] = Field(default_factory=list, max_length=5)


class Chunk(BaseModel):
    texto: str
    fuente: str


class Metadatos(BaseModel):
    perfil_aplicado: str
    formato_generado: str
    tiempo_estimado_estudio_minutos: int
    conceptos_clave: list[str]
    prerrequisitos: list[str]
    idioma_salida: str = "Español"


TextoNoVacio = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ItemFlashcard(BaseModel):
    frente: TextoNoVacio
    dorso: TextoNoVacio
    pista_didactica: str


class ContenidoAdaptado(BaseModel):
    titulo: TextoNoVacio
    introduccion_contextualizada: TextoNoVacio
    items: list[ItemFlashcard] = Field(min_length=1)


class PasoTutorial(BaseModel):
    titulo: TextoNoVacio
    explicacion: TextoNoVacio
    ejemplo: str = Field(default="", description="Codigo o ejemplo concreto. Vacio si no aplica.")
    consejo: str = Field(default="", description="Consejo practico o error comun a evitar. Vacio si no aplica.")


class ContenidoTutorial(BaseModel):
    titulo: TextoNoVacio
    introduccion_contextualizada: TextoNoVacio
    objetivos: list[TextoNoVacio] = Field(description="Lo que el lector sabra hacer al terminar. Entre 2 y 5.")
    pasos: list[PasoTutorial] = Field(min_length=1)
    conclusion: TextoNoVacio


class PreguntaQuiz(BaseModel):
    enunciado: TextoNoVacio
    opciones: list[TextoNoVacio] = Field(
        min_length=2,
        max_length=5,
        description="Opciones de respuesta sin letras ni numeros al inicio. Para verdadero/falso usa ['Verdadero', 'Falso'].",
    )
    indice_correcto: int = Field(ge=0, description="Posicion (empezando en 0) de la opcion correcta dentro de opciones.")
    explicacion: TextoNoVacio = Field(description="Por que la respuesta correcta lo es, citando la fuente.")
    pista: str = Field(default="", description="Ayuda breve que no revela la respuesta.")

    @model_validator(mode="after")
    def _validar_opciones(self) -> PreguntaQuiz:
        if self.indice_correcto >= len(self.opciones):
            raise ValueError("indice_correcto fuera del rango de opciones")
        normalizadas = [opcion.strip().lower() for opcion in self.opciones]
        if len(set(normalizadas)) != len(normalizadas):
            raise ValueError("las opciones no pueden repetirse")
        return self


class ContenidoQuiz(BaseModel):
    titulo: TextoNoVacio
    introduccion_contextualizada: TextoNoVacio
    preguntas: list[PreguntaQuiz] = Field(min_length=1)


class PuntoClave(BaseModel):
    titulo: TextoNoVacio
    detalle: TextoNoVacio


class ContenidoTLDR(BaseModel):
    titulo: TextoNoVacio
    introduccion_contextualizada: TextoNoVacio
    resumen_una_linea: TextoNoVacio = Field(description="La idea central en una sola frase.")
    puntos_clave: list[PuntoClave] = Field(min_length=1)
    acciones_recomendadas: list[TextoNoVacio] = Field(default_factory=list)


class EscenaGuion(BaseModel):
    titulo: TextoNoVacio
    narracion: TextoNoVacio = Field(description="Texto que se lee en voz alta.")
    apoyo_visual: TextoNoVacio = Field(description="Que se muestra en pantalla mientras se narra.")
    duracion_segundos: int = Field(ge=5, le=600)


class ContenidoGuion(BaseModel):
    titulo: TextoNoVacio
    introduccion_contextualizada: TextoNoVacio
    escenas: list[EscenaGuion] = Field(min_length=1)
    cierre: TextoNoVacio = Field(description="Llamado a la accion o mensaje final.")


Contenido = ContenidoAdaptado | ContenidoTutorial | ContenidoQuiz | ContenidoTLDR | ContenidoGuion

MODELOS_POR_FORMATO: dict[str, type[BaseModel]] = {
    "Flashcards": ContenidoAdaptado,
    "Tutorial": ContenidoTutorial,
    "Quiz": ContenidoQuiz,
    "TLDR": ContenidoTLDR,
    "Guion": ContenidoGuion,
}


class EvaluacionCalidad(BaseModel):
    anclaje_fuente_score: float = Field(
        ge=0.0, le=1.0, description="Fidelidad a la fuente. Decimal entre 0.0 y 1.0, nunca un entero como 4 o 5."
    )
    claridad_pedagogica: Literal["Alta", "Media", "Baja"]
    observaciones: str = Field(description="Maximo 2 frases.")


class RespuestaPregunta(BaseModel):
    """Respuesta a una pregunta libre sobre el documento, citando los fragmentos usados."""

    respuesta: TextoNoVacio = Field(description="Respuesta breve (maximo 4 frases) basada solo en los fragmentos.")
    fragmentos_usados: list[int] = Field(
        default_factory=list, description="Numeros de los fragmentos que respaldan la respuesta, por ejemplo [1, 3]."
    )
    en_documento: bool = Field(description="false si la respuesta no esta en los fragmentos.")


class AlmacenamientoOCI(BaseModel):
    bucket: str
    objeto_id: str
    status_upload: str


class Respuesta(BaseModel):
    status: str
    metadatos: Metadatos
    contenido_adaptado: Contenido
    evaluacion_calidad: EvaluacionCalidad
    almacenamiento_oci: AlmacenamientoOCI
    fuentes: list[Chunk] = Field(default_factory=list)


def _generar_doc_id(titulo: str) -> str:
    # Se usa como nombre de coleccion en ChromaDB: 3 a 63 caracteres [a-z0-9-] que
    # empiecen y terminen en letra o numero. Las tildes se quitan en vez de perder la letra.
    sin_tildes = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sin_tildes).strip("-").lower()[:60].strip("-")
    if len(slug) < 3:
        slug = f"doc-{slug}".strip("-") if slug else "documento"
    return slug


def _resumir_contenido(contenido: Contenido) -> tuple[int, list[str]]:
    if isinstance(contenido, ContenidoTutorial):
        return max(1, len(contenido.pasos) * 4), [paso.titulo for paso in contenido.pasos]
    if isinstance(contenido, ContenidoQuiz):
        return max(1, round(len(contenido.preguntas) * 1.5)), [pregunta.enunciado for pregunta in contenido.preguntas]
    if isinstance(contenido, ContenidoTLDR):
        return max(1, len(contenido.puntos_clave)), [punto.titulo for punto in contenido.puntos_clave]
    if isinstance(contenido, ContenidoGuion):
        segundos = sum(escena.duracion_segundos for escena in contenido.escenas)
        return max(1, round(segundos / 60)), [escena.titulo for escena in contenido.escenas]
    return max(1, len(contenido.items) * 2), [item.frente for item in contenido.items]


_PRERREQUISITOS_POR_PERFIL: dict[str, list[str]] = {
    "Principiante": ["Ninguno: el contenido se explica desde cero"],
    "Junior": ["Conceptos básicos de programación y uso de terminal"],
    "Lider Tecnico": ["Experiencia previa diseñando o manteniendo arquitecturas de software"],
    "Ejecutivo": ["Ninguno técnico: se explica en términos de negocio"],
}


def _prerrequisitos(solicitud: Solicitud) -> list[str]:
    prerrequisitos = list(_PRERREQUISITOS_POR_PERFIL.get(solicitud.perfil_destinatario, []))
    if solicitud.nivel_detalle == "Profundo" and solicitud.perfil_destinatario != "Ejecutivo":
        if solicitud.nicho_sector != "General":
            prerrequisitos.append(f"Familiaridad con el sector {solicitud.nicho_sector}")
        else:
            prerrequisitos.append("Familiaridad general con el tema del documento")
    return prerrequisitos


def procesar(solicitud: Solicitud, usar_cache: bool = True) -> Respuesta:
    from nuevamente import cache
    from nuevamente.agentes import generar
    from nuevamente.almacenamiento import guardar
    from nuevamente.config import leer_configuracion
    from nuevamente.rag import indexar, recuperar

    doc_id = _generar_doc_id(solicitud.documento_titulo)

    en_cache = cache.obtener(solicitud) if usar_cache else None
    if en_cache is not None:
        contenido, evaluacion, fuentes = en_cache
    else:
        indexar(doc_id, solicitud.documento_contenido)
        consulta = f"Puntos clave para un {solicitud.formato_salida} de nivel {solicitud.nivel_detalle}"
        chunks = recuperar(doc_id, consulta, k=5)
        contenido, evaluacion = generar(solicitud, chunks)
        fuentes = chunks
        cache.guardar(solicitud, contenido, evaluacion, fuentes)

    tiempo_estimado, conceptos_clave = _resumir_contenido(contenido)

    clave = (
        f"generados_nuevamente/{doc_id}-{solicitud.perfil_destinatario}-"
        f"{solicitud.formato_salida}.json"
    ).lower()
    try:
        guardar(clave, contenido.model_dump_json().encode("utf-8"))
        status_upload = "completado"
    except Exception:  # guardar en la nube es opcional: nunca debe tumbar la generacion
        logging.getLogger(__name__).warning("No se pudo guardar el resultado en el almacenamiento", exc_info=True)
        status_upload = "fallido"

    return Respuesta(
        status="exito",
        metadatos=Metadatos(
            perfil_aplicado=solicitud.perfil_destinatario,
            formato_generado=solicitud.formato_salida,
            tiempo_estimado_estudio_minutos=tiempo_estimado,
            conceptos_clave=conceptos_clave,
            prerrequisitos=_prerrequisitos(solicitud),
            idioma_salida=solicitud.idioma_salida,
        ),
        contenido_adaptado=contenido,
        evaluacion_calidad=evaluacion,
        almacenamiento_oci=AlmacenamientoOCI(
            bucket=leer_configuracion("SUPABASE_BUCKET", "") or "",
            objeto_id=clave,
            status_upload=status_upload,
        ),
        fuentes=fuentes,
    )


if __name__ == "__main__":
    ejemplo = Solicitud(
        documento_titulo="Introduccion a la Arquitectura de Redes VCN en OCI",
        documento_contenido="La Virtual Cloud Network (VCN) es una red privada y personalizable configurada en Oracle Cloud Infrastructure...",
        perfil_destinatario="Principiante",
        formato_salida="Flashcards",
        nicho_sector="General",
        nivel_detalle="Didactico",
    )
    print(procesar(ejemplo).model_dump_json(indent=2))
