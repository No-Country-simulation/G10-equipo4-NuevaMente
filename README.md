# NuevaMente

Sistema de RAG + agentes que adapta documentación técnica en contenido educativo personalizado (flashcards, tutoriales, quiz, TL;DR, guiones), según el perfil del destinatario, el nicho y el nivel de detalle deseado.

Proyecto para el **Hackathon ONE Grupo 10** (Oracle Next Education & Alura). Despliegue objetivo: OCI (Oracle Cloud Infrastructure), tier Always Free.

## Cómo funciona

1. **Ingesta**: se sube un documento (PDF, MD o TXT) y se extrae el texto.
2. **RAG**: el texto se divide en chunks y se indexa en ChromaDB (persistente). Se recuperan los chunks más relevantes según el formato/perfil solicitado.
3. **Agentes (LangGraph)**: un grafo de 3 nodos — Investigador → Redactor → Crítico — genera el contenido adaptado. El Crítico evalúa fidelidad a la fuente (`anclaje_fuente_score`) y si es baja, reintenta (máximo 2 veces).
4. **Almacenamiento**: el resultado se guarda en OCI Object Storage (con fallback a autenticación por instancia si corre en OCI).
5. **UI**: componente custom de Streamlit (HTML/CSS/JS propio, sin React/npm) con diseño Neo-Brutalista, incluyendo flashcards con flip 3D.

## Stack tecnológico

- **Backend**: Python, Pydantic v2 (contratos de datos), LangChain, LangGraph
- **RAG**: ChromaDB, pypdf
- **LLM**: switchable entre Google Gemini (`langchain-google-genai`) y Ollama local (`langchain-ollama`), vía variable de entorno `LLM_PROVEEDOR`
- **Almacenamiento**: OCI Object Storage (SDK `oci`)
- **UI**: Streamlit + componente bidireccional custom (HTML/JS puro)
- **Testing**: pytest

## Estructura del proyecto

```
G10-equipo4-NuevaMente
├─ app
│  ├─ componente.py       # Declaracion del componente custom de Streamlit
│  ├─ demo.py             # Modo demo: UI completa sin LLM ni OCI
│  ├─ frontend
│  │  └─ index.html       # UI Neo-Brutalista (HTML/CSS/JS)
│  └─ main.py             # Entry point de Streamlit
├─ ejemplos
├─ nuevamente
│  ├─ agentes
│  │  └─ __init__.py      # Grafo LangGraph (Investigador/Redactor/Critico)
│  ├─ almacenamiento
│  │  └─ __init__.py      # OCI Object Storage (guardar/leer)
│  ├─ contratos.py        # Modelos Pydantic + orquestacion (procesar())
│  ├─ ingesta
│  │  └─ __init__.py      # Lectura de PDF/MD/TXT
│  ├─ rag
│  │  └─ __init__.py      # Chunking + ChromaDB (indexar/recuperar)
│  └─ __init__.py
├─ pytest.ini
├─ README.md
├─ requirements.txt
└─ tests                  # Suite de pytest (36 tests)
   ├─ test_agentes.py
   ├─ test_almacenamiento.py
   ├─ test_contratos.py
   ├─ test_formatos.py
   ├─ test_ingesta.py
   └─ test_rag.py
```

## Formatos de salida

Cada formato tiene su propio modelo Pydantic (`MODELOS_POR_FORMATO` en `contratos.py`) y su propia vista en la UI:

| Formato | Modelo | Vista en la UI |
|---|---|---|
| Flashcards | `ContenidoAdaptado` | Tarjetas con flip 3D que crecen segun el texto, boton "Voltear todas" y soporte de teclado |
| Tutorial | `ContenidoTutorial` | Objetivos, pasos numerados con ejemplo (bloque de codigo si aplica), consejo y progreso marcando pasos |
| Quiz | `ContenidoQuiz` | Una pregunta a la vez, opciones mezcladas, pista, correccion con explicacion, puntaje final, revision y "Repasar errores" |
| TLDR | `ContenidoTLDR` | Idea central destacada, puntos clave y acciones recomendadas |
| Guion | `ContenidoGuion` | Escenas con marcas de tiempo, narracion y apoyo visual, y modo "Solo narracion" |

`PreguntaQuiz` valida que `indice_correcto` exista entre las opciones y que no haya opciones repetidas; si el LLM devuelve una pregunta invalida, el reintento de `with_retry` la vuelve a pedir.

## Como correr el proyecto localmente

### 1. Entorno virtual

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Variables de entorno

Crear un archivo `.env` en la raiz con:

```
GEMINI_API_KEY=tu_api_key
OCI_BUCKET_NAME=nuevamente-contenidos-educativos
OCI_NAMESPACE=tu_namespace
OCI_REGION=tu_region
LLM_PROVEEDOR=gemini          # o "ollama" para usar un modelo local
OLLAMA_BASE_URL=               # solo si LLM_PROVEEDOR=ollama
OLLAMA_MODEL=qwen2.5:7b        # solo si LLM_PROVEEDOR=ollama
```

**Nota sobre proveedores**: Gemini puede devolver errores 503 por saturacion en el tier gratuito. Como alternativa, el proyecto soporta correr un modelo local (`qwen2.5:7b`) via Ollama en Google Colab con GPU, expuesto con un tunel de ngrok (ver `ollama_colab_nuevamente.ipynb`). Cambiando `LLM_PROVEEDOR=ollama` en el `.env` se usa esa alternativa sin tocar codigo.

### 3. Correr la app

```powershell
streamlit run app/main.py
```

### 4. Probar la UI sin LLM (modo demo)

```powershell
streamlit run app/demo.py
```

Usa el mismo componente y la misma lectura de archivos que `main.py`, pero responde con contenido de ejemplo de cada formato. No necesita `.env`, Gemini, Ollama ni OCI.

### 5. Correr los tests

```powershell
pytest
```

## Estado actual (Sprint 1)

- [x] Contratos de datos (Pydantic)
- [x] Ingesta de documentos (PDF/MD/TXT)
- [x] RAG con ChromaDB
- [x] Agentes con LangGraph (Investigador/Redactor/Critico)
- [x] Almacenamiento en OCI
- [x] UI custom con diseno Neo-Brutalista
- [x] Integracion end-to-end verificada (PDF real -> flashcards generadas)
- [ ] CI en GitHub Actions
- [x] Manejo de errores en UI (aviso en el formulario y boton con estado de carga)
- [x] Contrato y vista propia para cada formato de salida

## Flujo de trabajo

- Rama de integracion: `develop`
- Ramas de feature: `feature/<nombre-corto>`
- Commits en ingles, siguiendo conventional commits
- PRs contra `develop`
