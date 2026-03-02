# Blipr: YouTube -> Clips Virales Automatizado

Pipeline end-to-end para convertir un video largo de YouTube en clips verticales (9:16) listos para TikTok/Instagram:

1. Descarga de YouTube (`yt-dlp`, con opciones para anti-bot por cookies)
2. Transcripcion automatica (`Whisper API` + timestamps por segmento)
3. Seleccion inteligente de momentos virales (LLM + fallback heuristico)
4. Render de clips con `ffmpeg` (dimensiones configurables, fondo blur, video centrado, subtitulos dinamicos)
5. Web app con updates en tiempo real (SSE)

## Requisitos

- Python 3.11+
- `ffmpeg` instalado y disponible en `PATH`
- API key de OpenAI

## Instalacion

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

Completa `.env` con tu `OPENAI_API_KEY` (y el resto de variables de configuracion).

## Ejecutar (desarrollo)

Terminal 1 (backend):

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Docs API: `http://127.0.0.1:8000/docs`

Frontend is a separate Next.js app (`blipr-web/`) deployed to Vercel.

## Postiz self-hosted local (TikTok)

Setup oficial de Postiz via Docker Compose con todos los servicios necesarios.

### Arquitectura (9 containers)

| Container | Imagen | Funcion |
|-----------|--------|---------|
| postiz | ghcr.io/gitroomhq/postiz-app:latest | App principal (frontend + backend + orchestrator) |
| postiz-postgres | postgres:17-alpine | Base de datos de Postiz |
| postiz-redis | redis:7.2 | Cache y queues |
| temporal | temporalio/auto-setup:1.28.1 | Orquestacion de workflows (posts programados) |
| temporal-elasticsearch | opensearchproject/opensearch:2.18.0 | Search para Temporal (OpenSearch por compatibilidad ARM64) |
| temporal-postgresql | postgres:16 | Base de datos de Temporal (separada de Postiz) |
| temporal-admin-tools | temporalio/admin-tools | CLI de administracion Temporal |
| temporal-ui | temporalio/ui:2.34.0 | Dashboard web de Temporal |
| spotlight | ghcr.io/getsentry/spotlight:latest | Debugging/monitoring (Sentry) |

### URLs de acceso

| Servicio | URL |
|----------|-----|
| Postiz UI (principal) | http://localhost:4007 |
| Postiz API | http://localhost:4007/api |
| Temporal UI | http://localhost:8080 |
| Spotlight (Sentry) | http://localhost:8969 |

### Prerequisitos

```bash
brew install colima docker docker-compose
```

### Levantar Postiz

```bash
# Iniciar Colima (runtime Docker para macOS)
colima start --cpu 2 --memory 4 --disk 50

# Levantar todos los servicios
cd postiz
docker compose up -d
```

### Verificar que todo funciona

```bash
# Todos los containers corriendo
docker compose ps

# Backend respondiendo
curl -s http://localhost:4007/api/auth/register -X POST -H "Content-Type: application/json" -d '{}'
# Debe devolver JSON con errores de validacion (400), NO un 502

# Frontend accesible
open http://localhost:4007
```

### Detener / reiniciar

```bash
docker compose down          # detener todo
docker compose up -d         # levantar todo
docker compose restart postiz  # reiniciar solo postiz
docker compose logs -f postiz  # ver logs en tiempo real
```

### Nota sobre Apple Silicon (ARM64)

El `docker-compose.yml` usa **OpenSearch 2.18.0** en lugar de Elasticsearch 7.17.27 porque la imagen oficial de ES 7.17 tiene un binario `tini` roto en ARM64. OpenSearch es API-compatible y funciona nativamente en Apple Silicon.

Para deploy en produccion (x86_64, ej. Hetzner VPS), se puede volver a Elasticsearch 7.17.27 sin problemas.

### Configuracion

Las credenciales y secretos se mantienen en archivos `.env` gitignoreados:

- `postiz/.env`: credenciales de PostgreSQL y Redis
- `postiz/.postiz.env`: configuracion de la app Postiz (JWT_SECRET, DATABASE_URL, REDIS_URL, APIs de redes sociales, etc.)

Para configurar, copiar los ejemplos y editar:

```bash
cp postiz/.env.example postiz/.env
cp postiz/.postiz.env.example postiz/.postiz.env
# Generar JWT_SECRET:
openssl rand -hex 32
# Pegar el resultado en postiz/.postiz.env como JWT_SECRET=...
```

Variables principales en `postiz/.postiz.env`:

- `JWT_SECRET`: secreto para autenticacion (generar con `openssl rand -hex 32`)
- `MAIN_URL` / `FRONTEND_URL`: `http://localhost:4007`
- `DATABASE_URL`: PostgreSQL interno
- `REDIS_URL`: Redis interno
- `TEMPORAL_ADDRESS`: `temporal:7233`
- APIs de redes sociales: `TIKTOK_CLIENT_ID`, `TIKTOK_CLIENT_SECRET`, etc. (vacias por defecto, configurar segun necesidad)

### Integrar con Blipr

1. Abrir http://localhost:4007 y crear usuario.
2. Conectar TikTok y generar API key de la Public API.
3. Configurar en `.env` de este proyecto:

```bash
TIKTOK_PUBLISH_MODE=postiz
POSTIZ_BASE_URL=http://localhost:4007/api
POSTIZ_API_KEY=tu_api_key
# opcional (si no se define, usa la primera integracion TikTok encontrada)
POSTIZ_TIKTOK_INTEGRATION_ID=tu_integration_id
```

4. Verificar integraciones TikTok detectadas:

```bash
curl http://127.0.0.1:8000/api/publishing/tiktok/integrations
```

Si `TIKTOK_PUBLISH_MODE=mock`, el flujo de publicacion sigue en modo simulado (sin Postiz).

## Flujo de uso

1. Pega un link de YouTube en la UI.
2. Elige cantidad de clips, duracion minima/maxima y dimensiones de salida por clip.
3. El sistema crea un job y muestra progreso en tiempo real.
4. Al finalizar, aparecen los clips solicitados en cards compactas.
5. Click en cada card para abrir modal de preview.
6. Aproba/rechaza cada clip. Si rechazas, agrega motivo para que el sistema aprenda que evitar.
7. Usa "Publicar aprobados".
8. Si no te gustan y los rechazas, usa "Regenerar clips" para crear nuevas opciones reutilizando cache y feedback.
9. Si el proceso queda inactivo o falla, usa "Reiniciar proceso" (cancela el task actual y relanza).

Los outputs se guardan en `jobs/<job_id>/`:

- `source.mp4` (o extension equivalente)
- `transcript.json`
- `moments.json`
- `moments_pool.json` (pool de candidatos cacheados para regeneracion)
- `used_moments.json` (momentos ya usados para evitar repetir)
- `rejection_feedback.json` (motivos de rechazo acumulados para evitar temas similares)
- `clip_g01_01.mp4 ...` (cada regeneracion crea `g02`, `g03`, etc.)
- `clip_g01_01.srt ...`

## Configuracion util (`.env`)

- `CLIPS_COUNT`: cantidad de clips (default 4)
- `MAX_CLIPS_PER_JOB`: maximo permitido por request desde el front (default 12)
- `MIN_CLIP_SECONDS`, `MAX_CLIP_SECONDS`: rango recomendado de duracion por clip (default 12-95s, con cierre natural de idea)
- `OUTPUT_WIDTH`, `OUTPUT_HEIGHT`: resolucion de salida por defecto (default 1080x1920)
- `SUBTITLE_CHUNK_MIN_WORDS`, `SUBTITLE_CHUNK_MAX_WORDS`: rango de palabras por frase de subtitulo (default 2-5)
- `SUBTITLE_MAX_CHARS_PER_LINE`: maximo de caracteres por linea de subtitulo (default 28)
- `SUBTITLE_MAX_LINES`: maximo de lineas visibles por cue para evitar bloques altos (default 2)
- `SUBTITLE_PHRASE_PAUSE_SPLIT_SECONDS`: pausa minima para cortar frase en silencio (default 0.34)
- `SUBTITLE_FONT_NAME`: fuente de subtitulos (default `Inter`)
- `SUBTITLE_FONT_FILE`: ruta al archivo `.ttf/.otf` para forzar fuente en ffmpeg/libass (ej. `static/fonts/Inter-VariableFont_opsz,wght.ttf`)
- `SUBTITLE_FONT_SIZE`: tamano de fuente de subtitulos (default 10)
- `SUBTITLE_MARGIN_VERTICAL`: separacion inferior de subtitulos (default 46)
- `SUBTITLE_MARGIN_HORIZONTAL`: padding lateral de subtitulos (default 56)
- `SUBTITLE_TIMING_SHIFT_SECONDS`: corrimiento global de subtitulos para evitar adelanto (default 0.08)
- `TRANSCRIPTION_CHUNK_SECONDS`: tamano de chunk de audio para Whisper (default 480)
- `TRANSCRIPTION_AUDIO_BITRATE`: bitrate del audio temporal (default `48k`)
- `TRANSCRIPTION_MAX_UPLOAD_MB`: limite de seguridad por chunk (default 24MB)
- `TRANSCRIPTION_HINT_TERMS`: nombres de marcas/personas para guiar Whisper (ej. `Uala,Ualá`)
- `TRANSCRIPTION_ENTITY_REPLACEMENTS`: correcciones de alias `mal_escrito=>canonico` separadas por `;` (ej. `wallah=>Ualá;walah=>Ualá`)
- `TIKTOK_PUBLISH_MODE`: `mock` (simulado) o `postiz` (publicacion real via Postiz)
- `POSTIZ_BASE_URL`: base URL de Postiz (`http://localhost:4007/api` con setup oficial)
- `POSTIZ_API_KEY`: API key de Postiz Public API
- `POSTIZ_TIKTOK_INTEGRATION_ID`: ID de integracion TikTok (opcional si hay una sola)
- `POSTIZ_TIKTOK_PRIVACY_STATUS`: privacidad TikTok (default `PUBLIC_TO_EVERYONE`)
- `POSTIZ_TIKTOK_DISABLE_DUET`: deshabilita duetos (`false` por defecto)
- `POSTIZ_TIKTOK_DISABLE_COMMENT`: deshabilita comentarios (`false` por defecto)
- `POSTIZ_TIKTOK_DISABLE_STITCH`: deshabilita stitch (`false` por defecto)
- `POSTIZ_REQUEST_TIMEOUT_SECONDS`: timeout de llamadas Postiz (default `60`)
- `YTDLP_COOKIES_FILE`: archivo cookies.txt para casos anti-bot
- `YTDLP_COOKIES_BROWSER`: ejemplo `chrome` o `firefox` para extraer cookies del browser

## Notas

- Si la descarga falla por proteccion de YouTube, proba configurar cookies en `.env`.
- Si no hay `OPENAI_API_KEY`, el selector viral usa fallback heuristico.
- En UI podes previsualizar fuente y padding de subtitulos antes de generar clips.
- El pipeline guarda estado en memoria; al reiniciar el servidor se pierde el tracking de jobs activos.
