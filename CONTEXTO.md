# CONTEXTO DEL PROYECTO — AI Video Automator

## Qué es esto

Pipeline autónomo idea → Short vertical 9:16: research (web+LLM) → script (LLM)
→ storyboard (LLM) → assets (stock/IA/color) → voice (edge-tts) → editing
(whisper + ASS) → rendering (ffmpeg) → QC (ffprobe). Docs: README.md,
docs/ARQUITECTURA.md, docs/MVP.md, docs/SETUP.md.

## Visión del producto (declarada 22 ago 2026)

El objetivo NO es el carrusel narrado que produce hoy: es **automatizar
frutinovelas / mini historias con un personaje que habla** para YouTube Shorts
(formato viral 2026: frutas antropomórficas con ojos/boca en mini dramas de
10-30 s). Brecha técnica frente al pipeline actual — 3 capacidades nuevas:

1. **Personaje consistente**: la misma fruta/personaje en todas las escenas y
   episodios. Estrategia base: descriptor fijo + hoja de personaje reutilizable.
2. **Diálogo multi-voz**: guion por líneas de personaje; edge-tts tiene voces
   ES suficientes para asignar una por personaje (gratis, trivial).
3. **Animación / boca que habla** (lo más caro en cómputo):
   - **ELEGIDO**: SadTalker (Apache-2.0, foto+audio→cabeza parlante) en Colab
     free; MuseTalk queda para v2. Cloud Shell NO tiene GPU → ANIMATE corre en
     Colab con 2 transferencias manuales de zip por video.
   - HF Inference Providers tiene tarea text-to-video con algunos proveedores;
     free tier pequeño que el video agota rápido [no verificado]. Descartado
     como v1 por costo, queda como opción de pago futura.
   - La comunidad hace frutinovelas a mano con Google Flow (gratis con cuenta
     Google). NO automatizar Flow con navegador remoto (ToS); solo referencia.
   - **Formato elegido: narrador + escenas de personajes.** Diseño completo en
     `docs/M2-frutinovelas.md`.

## Estado actual (22 ago 2026, ~22:30 UTC)

**M1 CERRADO, imágenes IA verificadas, y M2 paso 1 CONSTRUIDO [no verificado]:
SCRIPT modo historia + VOICE multi-voz + plantilla frutinovela.**

- `video-0001` COMPLETED (89 s): primer Short de punta a punta, pero con las 6
  escenas en `fallback_color` (destapó el bug de imágenes). Primer éxito
  histórico.
- `video-0002` COMPLETED (~121 s): **las 5 escenas en `ia:hf`** — el fix de
  imágenes funciona contra la cuenta real. Verificados también los avisos
  nuevos (`[!] PEXELS_API_KEY vacía`) y el progreso por etapa en consola. Fue
  video de prueba con el placeholder literal "tu idea aquí".
- Token HF fine-grained CON el permiso «Make calls to Inference Providers»:
  validado en ambas vías (LLM 200 OK + imágenes 200 OK). Un token de solo
  *read* da 401/403.
- M2 paso 1: `templates/frutinovela/template.yml` (`mode: historia`),
  script.py genera `personajes` (descriptor fijo + voz) y `lineas`
  (narrador/diálogo) manteniendo `narration`/`beats` de compatibilidad;
  voice.py sintetiza una pista por línea con la voz de su personaje
  (`voice/lNNN_quien.mp3` + `voice/lines.json`) y ensambla `assets/voice.mp3`
  con ffmpeg. El modo carrusel quedó intacto.

## Diagnóstico del bug de imágenes (historial, ya resuelto)

1. video-0001: 6/6 escenas en `fallback_color` y el pipeline dio verde: QC es
   técnico, no estético. ASSETS tardó 1 s — la señal de que no generó nada.
2. Causa: `api-inference.huggingface.co` retirado; en el router nuevo cada
   modelo lo sirve un proveedor distinto y `hf-inference` ya NO sirve FLUX
   (410 verificado con curl).
3. Causa agravante: `except Exception: return None` se tragaba el fallo sin
   dejar rastro en el log.
4. Consola muda: el orquestador solo escribía a `logs/<id>.log`; una corrida
   exitosa era indistinguible de un cuelgue.

**Arreglos en `main` (commits f0c540e y 514204d):**

- `src/stages/assets.py`: text-to-image vía `huggingface_hub` (enruta solo al
  proveedor vivo de cada modelo) con respaldo HTTP al router; lista de modelos
  en `configs/images.yml`; todo fallo deja motivo en stdout y en
  `assets_map.json["_warnings"]`, con aviso explícito si TODAS las escenas caen
  al fondo de color.
- `configs/images.yml`: cascada de modelos con proveedor vivo según la doc
  oficial de ago-2026 (nscale → FLUX.1-schnell, hf-inference → SD3-medium,
  fal-ai/replicate/wavespeed → FLUX.1-dev). Si un modelo muere (404/410 en los
  warnings): ajustar la lista mirando la doc viva
  (huggingface.co/docs/inference-providers/tasks/text-to-image) y re-probar con
  `python scripts/probar-imagen.py`.
- `requirements.txt`: `huggingface_hub` y `Pillow` explícitos.
- `scripts/probar-imagen.py`: prueba el MISMO camino de ASSETS en segundos, sin
  correr el pipeline y sin exponer el token.
- `src/orchestrator.py`: progreso por etapa con tiempos, aviso de que EDITING
  baja whisper la 1ª vez, y mensaje claro cuando un `resume` no tiene nada que
  reanudar.

## Cómo continuar (siguiente paso real)

Probar el paso 1 de M2 y seguir el orden de `docs/M2-frutinovelas.md`:

1. `cd ~/ai-video-automator && git pull`
2. `python -m src.main new "<idea de mini drama>" --template frutinovela`
   → video-0003: guion con personajes y una voz por personaje. Visualmente
   sigue siendo carrusel: es lo esperado hasta los pasos 2-4.
3. Verificación:
   - `cat projects/video-0003/voice/lines.json` → una entrada por línea, con
     `quien`, `offset_s` y `dur_s`.
   - `grep -o '"origin": "[^"]*"' projects/video-0003/assets_map.json`
     → debe decir `ia:hf`, no `fallback_color`.
4. Si sale bien → construir paso 2: PERSONAJE (hoja de personaje consistente).

Operativa del pipeline (modo carrusel sigue igual):

- `python -m src.main new "<idea>"` → video nuevo; `resume` no re-ejecuta
  etapas completadas.
- Opcional: `PEXELS_API_KEY` en `.env` (docs/SETUP.md §3) para stock real.
- Para VER un video: menú ⋮ de Cloud Shell → **Download** → pegar la ruta en
  el cuadro del diálogo, NUNCA en el prompt. O: Open Editor → árbol → clic
  derecho sobre el .mp4 → Download. Subir archivos: menú ⋮ → **Upload**.

## Reglas aprendidas — no repetir

1. **Cloud Shell es una terminal remota: NO abre páginas web NI ejecuta
   archivos.** Pegar una URL da `Exit 127`; pegar la ruta de un .mp4 da
   `Permission denied` (bash intenta ejecutarlo). Los enlaces van en el
   navegador y las rutas de descarga van en el cuadro del menú ⋮ → Download,
   nunca en el prompt.
2. Al pegar en la terminal, copiar solo el bloque de comando. Arrastrar salida
   anterior produce cascadas de `command not found` (inofensivas pero confusas)
   y una comilla suelta deja el shell colgado en `>` (salir con Ctrl+C).
3. `sh s.sh` / `setup-env.sh` **recrea el `.env` desde la plantilla**: reconfigura
   proveedor y token en cada corrida. Su comprobación `1 y 1` solo valida
   formato, NO hace una llamada real — por eso un token sin permiso pasa el
   setup y falla luego en RESEARCH.
4. **GitHub Models fue retirado permanentemente el 30-jul-2026**: el proveedor
   `github` muere con aviso claro. Vivos y gratis: `hf` (recomendado: un token =
   LLM + imágenes) y `pollinations` (ruta de texto [no verificado]).
5. YAML roto en `templates/announcement/template.yml` tumbaba RESEARCH →
   corregido; la carga de plantillas ya no cae por una rota (avisa y sigue).
   Commit `9be89d85`.
6. `nano` corrompió el `.env` del usuario dos veces: no usar editores, usar el
   script.
7. PAT de GitHub quemado en el chat (2 veces): rotarlo tras cada prueba.
8. Endpoints solo desde doc viva. `api-inference.huggingface.co` y
   `hf-inference`+FLUX son ejemplos de rutas que murieron sin aviso.

## Pendientes transversales

- Transiciones xfade, SFX, QC con LLM, verificación de las 8 plantillas.
- Confirmar endpoints de Pollinations contra la doc viva.
- Colab: SOLO como entorno de render del pipeline (uso legítimo); NUNCA
  navegador remoto (los ToS de Colab lo prohíben → suspenderían la cuenta Google
  que sostiene Cloud Shell).
- El mapa de instancias del navegador remoto vive en el repo `navegador-remoto`
  (CONTEXTO.md propio).
- Repo hermano `maximizador-ia` (privado): núcleo de reglas + roles para los
  prompts de estas sesiones.
