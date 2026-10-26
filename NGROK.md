# Ollama por un túnel ngrok

La app usa Ollama como proveedor principal (`LLM_PROVEEDOR=ollama`) a través de una URL HTTPS pública que crea ngrok hacia el puerto 11434 de Ollama. Si el túnel o Ollama fallan, la app usa Gemini como respaldo cuando hay `GEMINI_API_KEY`.

> Para un sitio publicado que funcione todo el tiempo conviene usar Gemini como principal (ver "Despliegue en la web" en el README): el túnel solo funciona mientras el equipo con Ollama (o el Colab) y ngrok estén encendidos.

## 1. Preparar Ollama

En el equipo (o Colab) que va a correr el modelo:

```bash
ollama pull qwen2.5:7b   # el modelo por defecto de la app (OLLAMA_MODEL)
ollama serve             # escucha en http://localhost:11434
```

## 2. Abrir el túnel

1. Crear una cuenta en https://ngrok.com e instalar ngrok.
2. Registrar el token de la cuenta (una sola vez):

   ```bash
   ngrok config add-authtoken TU_TOKEN
   ```

3. Abrir el túnel hacia Ollama. `--host-header` es necesario porque Ollama solo acepta peticiones dirigidas a `localhost`:

   ```bash
   ngrok http 11434 --host-header="localhost:11434"
   ```

4. Copiar la URL HTTPS que muestra ngrok (por ejemplo `https://tu-dominio.ngrok-free.dev`).

Con el plan gratuito la URL cambia cada vez que se reinicia ngrok, salvo que se use el dominio estático gratuito de la cuenta (`ngrok http 11434 --url=tu-dominio.ngrok-free.dev --host-header="localhost:11434"`).

## 3. Configurar la app

En `.env` (local) o en los Secrets de Streamlit Cloud:

```
LLM_PROVEEDOR=ollama
OLLAMA_BASE_URL=https://tu-dominio.ngrok-free.dev
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_TIMEOUT_SECONDS=60
GEMINI_API_KEY=tu_api_key        # respaldo si el túnel falla
```

- `OLLAMA_BASE_URL` va **sin** `/api` ni `/api/chat` al final.
- La app ya envía la cabecera `ngrok-skip-browser-warning`, así que la página de aviso de ngrok no interfiere.
- Si cambia la URL del túnel, hay que actualizar `OLLAMA_BASE_URL` y reiniciar la app.

## 4. Comprobar la conexión

Desde la raíz del proyecto:

```bash
python scripts/verificar_servicios.py            # conexión y modelo disponible
python scripts/verificar_servicios.py --inferir  # además, una llamada real a cada proveedor (consume cuota de Gemini)
```
