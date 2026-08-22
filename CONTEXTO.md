# CONTEXTO DEL PROYECTO — AI Video Automator

## Qué es esto

Pipeline autónomo idea → Short vertical 9:16: research (web+LLM) → script (LLM)
→ storyboard (LLM) → assets (stock/IA/color) → voice (edge-tts) → animate
(clips de personaje) → editing (whisper + ASS) → rendering (ffmpeg) → QC
(ffprobe). Docs: README.md, docs/ARQUITECTURA.md, docs/MVP.md, docs/SETUP.md.

## Visión del producto (declarada 22 ago 2026)

El objetivo NO es el carrusel narrado que produce hoy: es **automatizar
frutinovelas / mini historias con un personaje que habla** para YouTube Shorts
(formato viral 2026). Diseño completo en `docs/M2-frutinovelas.md`.

**Ruta de clips elegida (verificada el 22-ago):**

- **v1 = Google Flow MANUAL (gratis, hoy)**: 50 créditos/día, Veo 3.1 Lite =
  10 créditos/clip → ~5 clips/día. Ingredients da consistencia de personaje.
  El pipeline escribe `prompts_flow.md` (prompt detallado por clip), PAUSA en
  ANIMATE, el usuario sube los clips a `projects/<id>/clips/` y `resume` monta.
- v2 = Colab + SadTalker sobre NUESTRO TTS (lip-sync exacto, gratis, GPU).
- Opción de pago = Gemini API Veo 3.1 Lite (~$0.05/s 720p ≈ $1.5-2/episodio,
  100% automatizable, requiere billing).
- Meta/Vibes DESCARTADO: sin API pública de video; solo app manual.
- El audio maestro SIEMPRE es nuestro edge-tts; RENDERING ignora el audio de
  los clips → cambiar de proveedor de clips no toca el montaje.

## Estado actual (22 ago 2026, ~23:00 UTC)

**M1 CERRADO, imágenes IA verificadas. M2 en construcción acelerada:**

- CONSTRUIDO [no verificado en corrida real]: SCRIPT modo historia (8-14
  líneas, giro, réplica/contrarréplica, personalidad por personaje), VOICE
  multi-voz con `voice/lines.json`, plantilla `templates/frutinovela/`, ANIMATE
  con manifiesto + `prompts_flow.md` + pausa limpia (PipelinePaused), EDITING
  por línea con clips, y etapa ANIMATE registrada (los proyectos viejos
  COMPLETED la heredan sin reabrirse).
- Calidad de imágenes: `prompt_suffix` de estilo en configs/images.yml
  (3D Pixar, sin texto) + cascada con FLUX.1-dev primero (calidad) y
  FLUX.1-schnell / SD3-medium de respaldo.
- Bug menor corregido: storyboard.json ahora guarda `template` para que
  EDITING/ASSETS carguen la plantilla correcta (antes caía a "roblox").
- `video-0001` COMPLETED (89 s, 6/6 fallback_color — primer éxito histórico).
- `video-0002` COMPLETED (~121 s, 5/5 `ia:hf` — fix de imágenes verificado).
- Token HF fine-grained con «Make calls to Inference Providers»: validado.

## Diagnóstico del bug de imágenes (historial, ya resuelto)

1. video-0001: 6/6 escenas en `fallback_color` y QC dio verde (QC es técnico,
   no estético). ASSETS tardó 1 s — la señal de que no generó nada.
2. Causa: `api-inference.huggingface.co` retirado; en el router nuevo cada
   modelo lo sirve un proveedor distinto y `hf-inference` ya NO sirve FLUX
   (410 verificado con curl).
3. Causa agravante: `except Exception: return None` se tragaba el fallo.
4. Consola muda: el orquestador solo escribía a `logs/<id>.log`.

**Arreglos en `main` (commits f0c540e y 514204d):** text-to-image vía
`huggingface_hub` con respaldo HTTP al router; cascada de modelos en
`configs/images.yml`; todo fallo deja motivo en stdout y en
`assets_map.json["_warnings"]`; `scripts/probar-imagen.py` prueba el MISMO
camino sin exponer el token; progreso por etapa con tiempos en consola.

## Cómo continuar (siguiente paso real)

Probar la frutinovela completa con clips de Flow (M2 v1):

1. `cd ~/ai-video-automator && git pull`
2. `python -m src.main new "<idea de mini drama>" --template frutinovela`
   → corre hasta ANIMATE y hace PAUSA (NO es error: falta el paso manual).
3. Abrir `projects/<id>/prompts_flow.md` (Open Editor) y seguirla: crear el
   ingrediente de cada personaje en Flow (modo Image/Nano Banana con el
   descriptor) y generar cada clip (Video → Ingredients → Veo 3.1 Lite →
   9:16 → 8 s) pegando el prompt indicado.
4. Descargar los clips, renombrarlos EXACTO como pide el manifiesto
   (`l002_limon.mp4`, ...) y subirlos a `projects/<id>/clips/` (menú ⋮ →
   Upload en Cloud Shell).
5. `python -m src.main resume <id>` → EDITING monta por línea con los
   tiempos reales del audio → RENDERING → QC → COMPLETED.
6. Verificación post-ejecución: `cat projects/<id>/manifiesto_animacion.json`
   (todo `"listo": true`) y el grep de orígenes de siempre en assets_map.

Operativa base (sigue vigente):

- `resume` no re-ejecuta etapas completadas; una PAUSA se reanuda igual.
- Opcional: `PEXELS_API_KEY` en `.env` (docs/SETUP.md §3) para stock real.
- VER un video: menú ⋮ → Download → pegar la ruta en el CUADRO, nunca en el
  prompt. Subir archivos: menú ⋮ → Upload.

## Reglas aprendidas — no repetir

1. **Cloud Shell es una terminal remota: NO abre páginas web NI ejecuta
   archivos.** Pegar una URL da `Exit 127`; pegar la ruta de un .mp4 da
   `Permission denied`. Los enlaces van en el navegador y las rutas de
   descarga en el cuadro del menú ⋮ → Download, nunca en el prompt.
2. Al pegar en la terminal, copiar solo el bloque de comando. Una comilla
   suelta deja el shell colgado en `>` (salir con Ctrl+C).
3. `sh s.sh` / `setup-env.sh` **recrea el `.env` desde la plantilla** y su
   comprobación `1 y 1` solo valida formato, NO hace llamada real.
4. **GitHub Models fue retirado permanentemente el 30-jul-2026.** Vivos y
   gratis: `hf` (un token = LLM + imágenes) y `pollinations` [no verificado].
5. La carga de plantillas no cae por una YAML rota (avisa y sigue). `9be89d85`.
6. `nano` corrompió el `.env` dos veces: no usar editores, usar el script.
7. PAT de GitHub quemado en el chat (2 veces): rotarlo tras cada prueba.
8. Endpoints solo desde doc viva. `api-inference.huggingface.co` y
   `hf-inference`+FLUX murieron sin aviso.
9. **Flow y Meta/Vibes NO tienen API pública gratuita para video**: la
   integración es import manual de clips (prompts_flow.md) o Gemini API de
   pago. NUNCA automatizar sus webs con el navegador remoto (ToS; la cuenta
   Google sostiene Cloud Shell y Colab).

## Pendientes transversales

- M2: PERSONAJE (hoja para modo Colab), notebook SadTalker, subtítulos por
  personaje, check QC de clips, proveedor Gemini API opcional.
- Transiciones xfade, SFX, QC con LLM, verificación de las 8 plantillas.
- Confirmar endpoints de Pollinations contra la doc viva.
- Colab: SOLO cómputo del pipeline; NUNCA navegador remoto (ToS).
- El mapa del navegador remoto vive en `navegador-remoto`; reglas de sesión
  en `maximizador-ia` (privado).
