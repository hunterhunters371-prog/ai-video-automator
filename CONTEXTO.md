# CONTEXTO DEL PROYECTO — AI Video Automator
> Archivo de transferencia entre chats. Si eres un **chat nuevo de Notion AI** leyendo esto: aquí está el estado completo. El usuario (Oven, Bogotá, habla español) continúa desde este punto. No le pidas repetir diagnósticos ya hechos.

## Instrucciones para el chat nuevo (importantes)

1. **NUNCA bloques grandes para pegar en la terminal** — se corrompen (pasó 3 veces el 22 ago). Un comando por línea. La configuración del entorno ya está resuelta con `setup-env.sh` (raíz del repo): token por lectura oculta, sin editores.
2. **NUNCA aceptes tokens en el chat.** Si aparece un secreto, primera acción = ROTARLO (regla del usuario, repo maximizador-ia núcleo 3). Ya pasó 2 veces el 22 ago (token HF y PAT de GitHub).
3. El usuario corre el pipeline en **Google Cloud Shell** (VM ~4 GB RAM, sudo disponible, duerme ~20 min sin uso, `$HOME` persiste entre sesiones). ffmpeg 6.1.1 ya instalado. Los contenedores del navegador (`navegador`/`navegador2`) pueden correr ahí: antes de RENDERING, `docker stop navegador navegador2` libera RAM (si no existen, el error es inofensivo).
4. Si algo falla: pide la salida exacta del error, no adivines. `python -m src.main resume <id>` nunca repite trabajo (checkpoints por etapa en `projects/<id>/project.json`).
5. Repo público (clone/pull anónimo funciona).

## Qué es esto

Pipeline autónomo idea → Short vertical 9:16: research (web+LLM) → script (LLM) → storyboard (LLM) → assets (stock/IA/color) → voice (edge-tts) → editing (whisper + ASS) → rendering (ffmpeg) → QC (ffprobe). Docs: README.md, docs/ARQUITECTURA.md, docs/MVP.md, docs/SETUP.md.

## Estado actual (22 ago 2026, ~19:50 UTC)

**M1 implementado; bloqueado en la clave LLM del usuario.**

- M0 ✅. M1 en código: 8 etapas + CLI (`new`/`resume`/`status`) + capa config/llm/websearch.
- **Verificado en sandbox offline** (ffmpeg real): sintaxis de los 13 módulos, funciones puras (números en letra, preprocesado TTS, parseo de tiempos, ASS/SRT con safe zones, resync), RENDERING+QC end-to-end en verde. Bugs hallados por la prueba y corregidos: fps de salida (normalización final explícita a 30) y falso positivo de pantalla negra con fondo oscuro (blackdetect `pix_th=0.04`).
- **Verificado en el entorno del usuario**: clone, pip install, `status`, checkpoints (video-0001 quedó en FAILED conservando el trabajo; `resume` reanuda).
- **BLOQUEO ACTUAL**: `hf HTTP 401 Invalid username or password` en RESEARCH. Causa: token HF muerto o sin permiso. Solución (doc oficial HF): token fine-grained CON «Make calls to Inference Providers»: <https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained> → luego `sh s.sh` (ya descargado en su máquina) → Enter (hf) → pegar token nuevo → `python -m src.main resume video-0001`. Un token de solo *read* NO sirve (401/403). Diagnóstico sin exponer el token: `awk -F= '/^HF_TOKEN=/{print length($2)}' .env` (~37-40 esperado).

## Qué pasó el 22 ago — reglas aprendidas, no repetir

1. YAML roto en `templates/announcement/template.yml` (dos puntos sin comillas, línea 3) tumbaba RESEARCH → corregido con comillas + carga de plantillas endurecida (una rota se salta con aviso, no tumba el pipeline). Commit `9be89d85`.
2. **GitHub Models fue retirado permanentemente el 30-jul-2026** → el proveedor `github` en `src/llm.py` ahora muere con aviso claro. Proveedores gratis vivos: `hf` (recomendado: un token = LLM + imágenes IA) y `pollinations` (ruta de texto marcada [no verificado]).
3. `setup-env.sh` v2 configura el `.env` sin nano (nano le corrompió el archivo al usuario 2 veces: escribió comandos dentro del editor). Probado en sandbox: 4 caminos OK.
4. ASSETS con imágenes IA gratis: HF Inference / Pollinations vía `configs/images.yml`. Orden por escena: ruta explícita → video stock → imagen IA → foto stock → fondo de color. Endpoints de Pollinations (texto e imágenes) [no verificado]: confirmar contra gen.pollinations.ai/docs en la primera ejecución que los use.
5. PAT de GitHub quemado en el chat (2 veces): el usuario lo rota tras la prueba; como el proveedor github ya no existe, puede borrarlo cuando quiera.

## Cómo continuar (siguiente paso real)

1. El usuario crea el token HF con el enlace de arriba (permiso de inferencia ya marcado).
2. `cd ~/ai-video-automator && sh s.sh` → Enter → pega el token (no se ve) → comprobación `1` y `1`.
3. `python -m src.main resume video-0001`.
4. Esperado: RESEARCH→SCRIPT→STORYBOARD (~3 llamadas LLM), ASSETS (con HF_TOKEN: imágenes IA; sin él: fondos de color), VOICE (edge-tts, gratis), EDITING (baja whisper ~150 MB la 1ª vez — minutos, normal), RENDERING, QC → `renders/video-0001.mp4`.
5. Si falla: salida exacta del error. Si QC falla en algo real, ajustar según `qc_report.json`.

## Pendientes después del primer Short

- M2: transiciones xfade, SFX, loop QC con LLM, verificación de las 8 plantillas (todas las YAML ya parsean).
- Confirmar endpoints de Pollinations (texto e imagen) contra la doc viva.
- Colab: SOLO como entorno de render del pipeline (uso legítimo); NUNCA navegador remoto (ToS de Colab lo prohíben → suspendería la cuenta Google que sostiene Cloud Shell).
- El mapa de instancias del navegador remoto vive en el repo `navegador-remoto` (CONTEXTO.md propio, actualizado el 22 ago).
