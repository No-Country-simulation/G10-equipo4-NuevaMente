from __future__ import annotations

import os
import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

PerfilDestinatario = Literal["Principiante", "Junior", "Lider Tecnico", "Ejecutivo"]
FormatoSalida = Literal["Flashcards", "Tutorial", "Quiz", "TLDR", "Guion"]
NichoSector = Literal["General", "Fintech", "Salud", "E-commerce"]
NivelDetalle = Literal["Didactico", "Intermedio", "Profundo"]


class Solicitud(BaseModel):
    documento_titulo: str
    documento_contenido: str
    perfil_destinatario: PerfilDestinatario
    formato_salida: FormatoSalida
    nicho_sector: NichoSector
    nivel_detalle: NivelDetalle


class Chunk(BaseModel):
    texto: str
    fuente: str


class Metadatos(BaseModel):
    perfil_aplicado: str
    formato_generado: str
    tiempo_estimado_estudio_minutos: int
    conceptos_clave: list[str]


class ItemFlashcard(BaseModel):
    frente: str
    dorso: str
    pista_didactica: str


class ContenidoAdaptado(BaseModel):
    titulo: str
    introduccion_contextualizada: str
    items: list[ItemFlashcard]


class PasoTutorial(BaseModel):
    titulo: str
    explicacion: str
    ejemplo: str = Field(default="", description="Codigo o ejemplo concreto. Vacio si no aplica.")
    consejo: str = Field(default="", description="Consejo practico o error comun a evitar. Vacio si no aplica.")


class ContenidoTutorial(BaseModel):
    titulo: str
    introduccion_contextualizada: str
    objetivos: list[str] = Field(description="Lo que el lector sabra hacer al terminar. Entre 2 y 5.")
    pasos: list[PasoTutorial] = Field(min_length=1)
    conclusion: str


class PreguntaQuiz(BaseModel):
    enunciado: str
    opciones: list[str] = Field(
        min_length=2,
        max_length=5,
        description="Opciones de respuesta sin letras ni numeros al inicio. Para verdadero/falso usa ['Verdadero', 'Falso'].",
    )
    indice_correcto: int = Field(ge=0, description="Posicion (empezando en 0) de la opcion correcta dentro de opciones.")
    explicacion: str = Field(description="Por que la respuesta correcta lo es, citando la fuente.")
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
    titulo: str
    introduccion_contextualizada: str
    preguntas: list[PreguntaQuiz] = Field(min_length=1)


class PuntoClave(BaseModel):
    titulo: str
    detalle: str


class ContenidoTLDR(BaseModel):
    titulo: str
    introduccion_contextualizada: str
    resumen_una_linea: str = Field(description="La idea central en una sola frase.")
    puntos_clave: list[PuntoClave] = Field(min_length=1)
    acciones_recomendadas: list[str] = Field(default_factory=list)


class EscenaGuion(BaseModel):
    titulo: str
    narracion: str = Field(description="Texto que se lee en voz alta.")
    apoyo_visual: str = Field(description="Que se muestra en pantalla mientras se narra.")
    duracion_segundos: int = Field(ge=5, le=600)


class ContenidoGuion(BaseModel):
    titulo: str
    introduccion_contextualizada: str
    escenas: list[EscenaGuion] = Field(min_length=1)
    cierre: str = Field(description="Llamado a la accion o mensaje final.")


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


def _generar_doc_id(titulo: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", titulo).strip("-").lower()
    return slug[:60] or "documento"


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


def procesar(solicitud: Solicitud) -> Respuesta:
    from nuevamente.agentes import generar
    from nuevamente.almacenamiento import guardar
    from nuevamente.rag import indexar, recuperar

    doc_id = _generar_doc_id(solicitud.documento_titulo)
    indexar(doc_id, solicitud.documento_contenido)

    consulta = f"Puntos clave para un {solicitud.formato_salida} de nivel {solicitud.nivel_detalle}"
    chunks = recuperar(doc_id, consulta, k=5)

    contenido, evaluacion = generar(solicitud, chunks)
    tiempo_estimado, conceptos_clave = _resumir_contenido(contenido)

    clave = f"{doc_id}-{solicitud.perfil_destinatario}-{solicitud.formato_salida}.json".lower()
    try:
        guardar(clave, contenido.model_dump_json().encode("utf-8"))
        status_upload = "completado"
    except Exception:  # noqa: BLE001
        status_upload = "fallido"

    return Respuesta(
        status="exito",
        metadatos=Metadatos(
            perfil_aplicado=solicitud.perfil_destinatario,
            formato_generado=solicitud.formato_salida,
            tiempo_estimado_estudio_minutos=tiempo_estimado,
            conceptos_clave=conceptos_clave,
        ),
        contenido_adaptado=contenido,
        evaluacion_calidad=evaluacion,
        almacenamiento_oci=AlmacenamientoOCI(
            bucket=os.environ.get("OCI_BUCKET_NAME", ""),
            objeto_id=clave,
            status_upload=status_upload,
        ),
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
