<p align="center"><img src="app/frontend/assets/logo-nuevamente.svg" alt="NuevaMente" height="48"></p>

# NuevaMente

Sistema de RAG + agentes que adapta documentación técnica en contenido educativo personalizado (flashcards, tutoriales, quiz, TL;DR, guiones), según el perfil del destinatario, el nicho y el nivel de detalle deseado.

Proyecto para el **Hackathon ONE Grupo 10** (Oracle Next Education & Alura). Despliegue objetivo: OCI (Oracle Cloud Infrastructure), tier Always Free.

## Cómo funciona

1. **Ingesta**: se sube un documento (PDF, MD o TXT) y se extrae el texto.
2. **RAG**: el texto se divide en chunks y se indexa en ChromaDB (persistente). Se recuperan los chunks más relevantes según el formato/perfil solicitado.
3. **Agentes (LangGraph)**: un grafo de 3 nodos — Investigador → Redactor → Crítico — genera el contenido adaptado. El Crítico evalúa fidelidad a la fuente (`anclaje_fuente_score`) y si es baja, reintenta (máximo 2 veces).
4. **Almacenamiento**: el documento original y el resultado se guardan en Supabase Storage. Es opcional: si no hay credenciales o falla, la generacion continua y la UI muestra "No se guardo en la nube".
5. **UI**: componente custom de Streamlit (HTML/CSS/JS propio, sin React/npm) con diseño Neo-Brutalista, organizado en tres pestañas — **Crear contenido** (formulario en 3 pasos), **Estudiar** (resultado generado) y **Mis materiales** (lo generado en la sesión) — en modo claro, con un interruptor para el modo oscuro. La app cambia de pestaña sola: salta a "Estudiar" al generar y vuelve a "Crear contenido" si algo falla.

## Stack tecnológico

- **Backend**: Python, Pydantic v2 (contratos de datos), LangChain, LangGraph
- **RAG**: ChromaDB, pypdf
- **LLM**: switchable entre Google Gemini (`langchain-google-genai`) y Ollama local (`langchain-ollama`), vía variable de entorno `LLM_PROVEEDOR`
- **Almacenamiento**: Supabase Storage (SDK `supabase`)
- **UI**: Streamlit + componente bidireccional custom (HTML/JS puro)
- **Testing**: pytest

## Estructura del proyecto

```
G10-equipo4-NuevaMente
├─ .streamlit
│  └─ config.toml         # Configuracion de Streamlit (barra de herramientas minima)
├─ app
│  ├─ assets              # Favicon de la pestaña del navegador (favicon.png / .ico, apple-touch-icon)
│  ├─ componente.py       # Componente custom + configurar_pagina() (titulo, favicon, layout)
│  ├─ demo.py             # Modo demo: UI completa sin LLM ni almacenamiento
│  ├─ frontend
│  │  ├─ assets           # Logotipo, isotipo y marca "vo" en SVG (y PNG de respaldo)
│  │  ├─ fonts            # Montserrat, JetBrains Mono y Material Symbols (locales, con sus licencias)
│  │  └─ index.html       # UI Neo-Brutalista (HTML/CSS/JS): Crear / Estudiar / Mis materiales
│  ├─ flujo.py            # Acciones de la UI (generar, ruta, comparar, preguntar, valorar), comun a main y demo
│  ├─ historial.py        # Historial de la sesion para "Mis materiales"
│  └─ main.py             # Entry point de Streamlit
├─ nuevamente
│  ├─ agentes
│  │  └─ __init__.py      # Grafo LangGraph (Investigador/Redactor/Critico)
│  ├─ almacenamiento
│  │  └─ __init__.py      # Supabase Storage (guardar/leer)
│  ├─ cache.py            # Cache en disco de generaciones de buena calidad
│  ├─ config.py           # Lectura de configuracion (.env o st.secrets)
│  ├─ contratos.py        # Modelos Pydantic + orquestacion (procesar())
│  ├─ errores.py          # Traduce excepciones a mensajes claros para la UI
│  ├─ preguntas.py        # Pregúntale al documento: respuestas con los fragmentos citados
│  ├─ ingesta
│  │  └─ __init__.py      # Lectura de PDF/MD/TXT
│  ├─ rag
│  │  └─ __init__.py      # Chunking + ChromaDB (indexar/recuperar con MMR)
│  ├─ resiliencia.py      # Reintentos con espera ante limites de cuota del LLM
│  └─ __init__.py
├─ pytest.ini
├─ README.md
├─ requirements.txt
└─ tests                  # Suite de pytest (206 tests)
   ├─ test_agentes.py
   ├─ test_almacenamiento.py
   ├─ test_cache.py
   ├─ test_contratos.py
   ├─ test_demo.py         # Modo demo, recursos de marca, fuentes locales y tildes en la UI
   ├─ test_e2e.py
   ├─ test_errores.py
   ├─ test_flujo.py        # Generar, ruta, comparar, preguntar y valorar (sin red ni LLM)
   ├─ test_formatos.py
   ├─ test_historial.py
   ├─ test_ingesta.py
   ├─ test_preguntas.py    # Preguntas con fuentes, idioma y ajustes en los prompts, indice por huella
   ├─ test_rag.py
   ├─ test_resiliencia.py
   ├─ test_robustez.py     # Configuracion, ingesta, nombres de coleccion, re-indexado, respaldo Ollama
   └─ test_tema.py         # Modo claro por defecto e interruptor de modo oscuro
```

## Formatos de salida

Cada formato tiene su propio modelo Pydantic (`MODELOS_POR_FORMATO` en `contratos.py`) y su propia vista en la UI:

| Formato | Modelo | Vista en la UI |
|---|---|---|
| Flashcards | `ContenidoAdaptado` | Tarjetas con flip 3D, "Voltear todas", soporte de teclado y modo repaso ("Lo sé" / "Repasar", ronda solo con las pendientes) |
| Tutorial | `ContenidoTutorial` | Objetivos, pasos numerados con ejemplo (bloque de codigo si aplica), consejo, progreso y logro al completar |
| Quiz | `ContenidoQuiz` | Una pregunta a la vez, opciones mezcladas, pista, correccion con explicacion, puntaje final, insignia desde 90%, revision y "Repasar errores" |
| TLDR | `ContenidoTLDR` | Idea central destacada, puntos clave y acciones recomendadas |
| Guion | `ContenidoGuion` | Escenas con marcas de tiempo, narracion y apoyo visual, y modo "Solo narracion" |

`PreguntaQuiz` valida que `indice_correcto` exista entre las opciones y que no haya opciones repetidas; si el LLM devuelve una pregunta invalida, el reintento de `with_retry` la vuelve a pedir.

### Mas formas de estudiar

Debajo del boton **Generar** hay un bloque "También puedes" con dos acciones propias:

- **Ruta de estudio**: genera TL;DR, flashcards y quiz del mismo documento y los presenta como 3 pasos (entender, memorizar, comprobar). Los pasos de tarjetas y quiz se marcan solos al terminarlos.
- **Comparar perfiles**: genera el formato elegido para tu perfil y para otro (por defecto, el mas distinto) y los muestra lado a lado: introduccion, primeros elementos, tiempo, fidelidad y prerrequisitos. Cada version se puede estudiar completa.

En cada material ademas:

- **Pregúntale al documento**: preguntas libres respondidas solo con el documento, con los fragmentos citados (hasta 20 por material). Si la respuesta no esta en el documento, lo dice. Las conversaciones viven aparte del material, asi que preguntar no reinicia el quiz ni las tarjetas.
- **¿Te sirvió? 👍/👎 y "Regenerar con ajustes"**: chips *Más ejemplos, Más corto, Más técnico, Menos jerga, Más elementos* que se agregan a las instrucciones del redactor. Un 👎 abre los ajustes directamente. Las valoraciones se guardan (sin datos del documento) en `valoraciones/` del almacenamiento.
- **Idioma del contenido**: Español, Português o English (paso 3 del formulario). La interfaz sigue en español.

Ademas del contenido, cada respuesta trae metadatos de aprendizaje (`Metadatos` en `contratos.py`): tiempo estimado de estudio, conceptos clave y **prerrequisitos** (que deberia saber el lector antes de empezar, segun su perfil y nivel de detalle elegido).

## Como correr el proyecto localmente

### 1. Entorno virtual

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Variables de entorno

Copiar `.env.example` a `.env` en la raiz y completar los valores:

```
LLM_PROVEEDOR=ollama           # principal: Ollama; respaldo: Gemini
GEMINI_API_KEY=tu_api_key
GEMINI_MODEL=gemini-flash-latest
OLLAMA_BASE_URL=https://tu-dominio.ngrok-free.dev
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_TIMEOUT_SECONDS=60
GEMINI_TIMEOUT_SECONDS=45
SUPABASE_URL=                  # opcional: almacenamiento en la nube
SUPABASE_KEY=
SUPABASE_BUCKET=documentos
```

En Streamlit Cloud las mismas claves pueden ir en `.streamlit/secrets.toml` (ignorado por git).

Los archivos se aceptan hasta 10 MB. La primera vez que se indexa un documento, ChromaDB descarga su modelo de embeddings (unos 80 MB), por lo que esa primera generacion tarda mas y necesita salida a internet.

**Proveedores**: Ollama es el principal por defecto; Gemini se usa si falla la construccion del cliente, la preparacion del formato, la llamada o la validacion de la respuesta. Configure una clave real de Gemini para disponer del respaldo. La conexion principal se configura mediante la URL HTTPS de un tunel ngrok activo hacia Ollama. `OLLAMA_BASE_URL` es obligatoria para construir el cliente Ollama: ya no se sustituye silenciosamente por localhost. Si falta, se intenta Gemini. Consulte [NGROK.md](NGROK.md) para iniciar el tunel y configurar la app. El notebook de Colab no esta incluido.

Se realiza un intento por proveedor y por invocacion de agente. Ollama tiene un timeout de conexion de 5 segundos y un timeout de lectura configurable (60 segundos); Gemini usa 45 segundos y no acumula reintentos internos. Son limites de solicitudes/operaciones de red, no un plazo total de toda la generacion: el grafo tiene varias llamadas. Si ambos proveedores fallan se muestra un error; no se inventa contenido. Los materiales ya guardados en cache conservan su funcionamiento existente.

El modelo de respaldo predeterminado es `gemini-flash-latest`, alias documentado por Google (https://ai.google.dev/gemini-api/docs/models). Puede fijar otro modelo disponible para su cuenta mediante `GEMINI_MODEL`.

### 3. Correr la app

```powershell
streamlit run app/main.py
```

### 4. Probar la UI sin LLM (modo demo)

```powershell
streamlit run app/demo.py
```

Usa el mismo componente y la misma lectura de archivos que `main.py`, pero responde con contenido de ejemplo de cada formato. No necesita `.env`, Gemini, Ollama ni Supabase.

### 5. Correr los tests

```powershell
ruff check .
pytest
```

## Identidad visual

- **Logotipo e isotipo** en SVG (`app/frontend/assets/`): el logotipo va en linea dentro del HTML y toma el color del texto, asi se ve bien en modo claro y oscuro. Tambien aparece en el PDF exportado.
- **Favicon** (`app/assets/favicon.png`, `favicon.ico`, `apple-touch-icon.png`): se aplica con `st.set_page_config(page_icon=...)` desde `configurar_pagina()` en `app/componente.py`, junto con el titulo "NuevaMente" de la pestaña.
- **Colores**: azul `#0B57D0` para acciones, amarillo `#FEF08A` para pistas y consejos, y **lima `#C8F31D` (el del isotipo) para los logros**: puntaje alto del quiz, pasos completados, tarjetas dominadas y la animacion de carga, donde la marca "vo" se dibuja sola.
- **Modo claro por defecto** (aunque el sistema este en oscuro). El **modo oscuro** se activa con el interruptor "Modo oscuro" de la cabecera: mismos bordes gruesos, con contornos claros y sombras lima, y tambien oscurece la pagina de Streamlit alrededor del componente. La eleccion se recuerda en ese navegador. Si se cambia mientras se genera contenido, la generacion no se interrumpe: el fondo de la pagina se ajusta al terminar.
- **Fuentes locales** en `app/frontend/fonts/`: la app no depende de Google Fonts. Los iconos quedan invisibles hasta que su fuente carga, para que nunca se vea la palabra del icono ("upload_file").
- **Textos con tildes**: los valores internos de los contratos (`Lider Tecnico`, `Didactico`) no cambian; la UI los muestra como "Líder técnico" y "Didáctico".

## Seguridad

- Todo el contenido que genera el modelo se muestra como texto: la UI escapa el HTML antes de pintarlo (probado con inyecciones en los 5 formatos, en "Mis materiales", en los avisos y en las exportaciones).
- El componente solo acepta mensajes de la pagina de Streamlit que lo contiene; los de cualquier otra ventana se ignoran.
- La UI no carga recursos de terceros: fuentes, iconos y logos van dentro del proyecto. Streamlit tampoco envia estadisticas de uso (`gatherUsageStats = false`).
- El CI corre con permisos de solo lectura (`permissions: contents: read`).
- **ChromaDB**: `pip-audit` reporta vulnerabilidades (CVE-2026-45829, -45830, -45831, -45833) en el **servidor HTTP** de ChromaDB, todavia sin version corregida. Este proyecto no las expone porque usa ChromaDB embebido (`PersistentClient`), sin servidor. No levanten `chroma run` ni usen `HttpClient` hasta que haya una version corregida.
