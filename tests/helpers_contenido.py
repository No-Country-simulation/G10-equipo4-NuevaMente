"""Contenidos y solicitudes de ejemplo validos para las pruebas de integracion."""

from nuevamente.contratos import (
    ContenidoAdaptado,
    ContenidoGuion,
    ContenidoQuiz,
    ContenidoTLDR,
    ContenidoTutorial,
    EscenaGuion,
    EvaluacionCalidad,
    ItemFlashcard,
    PasoTutorial,
    PreguntaQuiz,
    PuntoClave,
    Solicitud,
)


def solicitud(formato="Flashcards", perfil="Principiante", nivel="Didactico", nicho="General"):
    return Solicitud(
        documento_titulo="Intro a VCN en OCI",
        documento_contenido="Una VCN es una red privada en la nube. " * 20,
        perfil_destinatario=perfil,
        formato_salida=formato,
        nicho_sector=nicho,
        nivel_detalle=nivel,
    )


def contenido(formato="Flashcards"):
    intro = "Intro de prueba"
    return {
        "Flashcards": ContenidoAdaptado(
            titulo="T", introduccion_contextualizada=intro,
            items=[ItemFlashcard(frente="Que es VCN?", dorso="Una red privada", pista_didactica="Un barrio cercado")],
        ),
        "Tutorial": ContenidoTutorial(
            titulo="T", introduccion_contextualizada=intro, objetivos=["Crear una VCN", "Crear una subred"],
            pasos=[PasoTutorial(titulo="Paso 1", explicacion="Explica")], conclusion="Fin",
        ),
        "Quiz": ContenidoQuiz(
            titulo="T", introduccion_contextualizada=intro,
            preguntas=[PreguntaQuiz(enunciado="2+2?", opciones=["3", "4"], indice_correcto=1, explicacion="Suma")],
        ),
        "TLDR": ContenidoTLDR(
            titulo="T", introduccion_contextualizada=intro, resumen_una_linea="Todo en una linea",
            puntos_clave=[PuntoClave(titulo="P", detalle="D")],
        ),
        "Guion": ContenidoGuion(
            titulo="T", introduccion_contextualizada=intro, cierre="Gracias",
            escenas=[EscenaGuion(titulo="E1", narracion="Hola", apoyo_visual="Logo", duracion_segundos=30)],
        ),
    }[formato]


def evaluacion(score=0.9):
    return EvaluacionCalidad(anclaje_fuente_score=score, claridad_pedagogica="Alta", observaciones="ok")