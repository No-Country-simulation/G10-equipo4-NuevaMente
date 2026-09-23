from __future__ import annotations

import os
import re
from typing import Literal

from pydantic import BaseModel, Field

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
    contenido_adaptado: ContenidoAdaptado
    evaluacion_calidad: EvaluacionCalidad
    almacenamiento_oci: AlmacenamientoOCI


def _generar_doc_id(titulo: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", titulo).strip("-").lower()
    return slug[:60] or "documento"


def procesar(solicitud: Solicitud) -> Respuesta:
    from nuevamente.agentes import generar
    from nuevamente.almacenamiento import guardar
    from nuevamente.rag import indexar, recuperar

    doc_id = _generar_doc_id(solicitud.documento_titulo)
    indexar(doc_id, solicitud.documento_contenido)

    consulta = f"Puntos clave para un {solicitud.formato_salida} de nivel {solicitud.nivel_detalle}"
    chunks = recuperar(doc_id, consulta, k=5)

    contenido, evaluacion = generar(solicitud, chunks)

    clave = f"{doc_id}-{solicitud.perfil_destinatario}-{solicitud.formato_salida}.json".lower()
    try:
        guardar(clave, contenido.model_dump_json().encode("utf-8"))
        status_upload = "completado"
    except Exception:
        status_upload = "fallido"

    return Respuesta(
        status="exito",
        metadatos=Metadatos(
            perfil_aplicado=solicitud.perfil_destinatario,
            formato_generado=solicitud.formato_salida,
            tiempo_estimado_estudio_minutos=max(1, len(contenido.items) * 2),
            conceptos_clave=[item.frente for item in contenido.items],
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
