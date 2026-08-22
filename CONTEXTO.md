# CONTEXTO DEL PROYECTO — AI Video Automator

## Qué es esto

Pipeline autónomo idea → Short vertical 9:16: research (web+LLM) → script (LLM)
→ storyboard (LLM) → assets (stock/IA/color) → voice (edge-tts) → animate
(clips de personaje) → editing (whisper + ASS) → rendering (ffmpeg) → QC
(ffprobe). Docs: README.md, docs/ARQUITECTURA.md, docs/MVP.md, docs/SETUP.md.

## Visión del producto (declarada 22 ago 2026)

El objetivo NO es el carrusel narrado que produce hoy: es **automatizar
frutinovelas / mini historias con un personaje que habla** para YouTube Shorts.
Diseño en `docs/M2-frutinovelas.md`; comparativa de generadores verificada en
`docs/proveedores-clips.md`.

**Ruta de clips (investigada y decidida el 22-ago):**

- **Por defecto: Meta AI / Vibes MANUAL** (`animate.provider: meta`). Flujo
  oficial: prompt "Imagina..." → imagen → **Animate** → vibe, con **lip sync**
  y opción de animar una imagen **subida**. Gratis durante el rollout.
- Alternativa: **Google Flow** (50 créditos/día, Veo 3.1 Lite = 10/clip, sin
  marca de agua). ANIMATE escribe las DOS guías siempre → se salta de una a
  otra al agotar cuota.
- Ilimitado real (pendiente): **Colab + SadTalker** sobre nuestro TTS.
- Pago 100% automático: **Gemini API Veo 3.1 Lite** (~$0.05/s ≈ $1.5-2/video).
- El audio maestro SIEMPRE es nuestro edge-tts → cambiar de proveedor de clips
  no toca el montaje.

**"Ilimitado" — conclusión honesta:** ningún generador gratis de calidad es
ilimitado hoy. Meta AI es "gratis durante el rollout" con tope diario, colas,
posible marca de agua, disponibilidad por región y pruebas de suscripción de
pago en curso. Lo único ilimitado de verdad es GPU propia/prestada (Colab).
La estrategia del repo es apilar cuotas diarias gratis y automatizar TODO lo
demás.

## Estado actual (22 ago 2026, ~23:30 UTC)

**M1 CERRADO. M2 v1 CONSTRUIDO [no verificado en corrida real]:**

- SCRIPT modo historia (8-14 líneas, giro, réplica/contrarréplica), VOICE
  multi-voz con `voice/lines.json`, plantilla `templates/frutinovela/`.
- ANIMATE: manifiesto + `prompts_meta.md` + `prompts_flow.md` + pausa limpia
  (PipelinePaused, reanudable, admite subir clips de a pocos). Acepta
  .mp4/.mov/.webm.
- EDITING por línea usando el manifiesto para localizar cada clip.
- Calidad de imágenes: `prompt_suffix` de estilo (3D Pixar, sin texto) +
  cascada FLUX.1-dev → schnell → SD3-medium.
- Bug corregido: storyboard.json guarda `template` (antes EDITING/ASSETS
  cargaban siempre "roblox").
- `video-0001` COMPLETED (89 s, 6/6 fallback_color — primer éxito histórico).
- `video-0002` COMPLETED (~121 s, 5/5 `ia:hf` — fix de imágenes verificado).

## Diagnóstico del bug de imágenes (historial, ya resuelto)

1. video-0001: 6/6 escenas en `fallback_color` y QC dio verde (QC es técnico,
   no estético). ASSETS tardó 1 s — la señal de que no generó nada.
2. Causa: `api-inference.huggingface.co` retirado; en el router nuevo cada
   modelo lo sirve un proveedor distinto y `hf-inference` ya NO sirve FLUX.
3. Agravante: `except Exception: return None` se tragaba el fallo.
4. Consola muda: el orquestador solo escribía a `logs/<id>.log`.

**Arreglos en `main`:** text-to-image vía `huggingface_hub` con respaldo HTTP;
cascada de modelos en `configs/images.yml`; todo fallo deja motivo en stdout y
en `assets_map.json["_warnings"]`; `scripts/probar-imagen.py`; progreso por
etapa con tiempos.

## Cómo continuar (siguiente paso real)

1. `cd ~/ai-video-automator && git pull`
2. `python -m src.main new "<idea de mini drama>" --template frutinovela`
   → corre hasta ANIMATE y hace **PAUSA** (no es error: falta el paso manual).
3. Abrir `projects/<id>/prompts_meta.md` (Open Editor) y seguirla en
   [meta.ai](https://www.meta.ai/): imagen del personaje con "Imagina..." →
   Animate por línea (+ lip sync) → descargar.
   Si se agota la cuota del día → `prompts_flow.md` (Google Flow).
4. Renombrar EXACTO (`l002_limon.mp4`, ...) y subir a `projects/<id>/clips/`
   (menú ⋮ → Upload). Se puede de a pocos.
5. `python -m src.main resume <id>` → EDITING/RENDERING/QC → COMPLETED.
6. Verificar: `cat projects/<id>/manifiesto_animacion.json` (todo
   `"listo": true`).

Operativa base: `resume` no re-ejecuta etapas completadas; opcional
`PEXELS_API_KEY` para stock real; ver videos con menú ⋮ → Download pegando la
ruta en el CUADRO, nunca en el prompt.

## Reglas aprendidas — no repetir

1. **Cloud Shell es una terminal remota: NO abre páginas web NI ejecuta
   archivos.** URLs y rutas de descarga van en el navegador o en el cuadro del
   menú ⋮, nunca en el prompt.
2. Al pegar en la terminal, copiar solo el bloque de comando; una comilla
   suelta deja el shell colgado en `>` (Ctrl+C).
3. `sh s.sh` / `setup-env.sh` recrea el `.env` y su chequeo `1 y 1` solo valida
   formato, NO hace llamada real.
4. **GitHub Models retirado el 30-jul-2026.** Vivos y gratis: `hf` (un token =
   LLM + imágenes) y `pollinations` [no verificado].
5. La carga de plantillas no cae por una YAML rota (avisa y sigue). `9be89d85`.
6. `nano` corrompió el `.env` dos veces: usar el script, no editores.
7. PAT de GitHub quemado en el chat (2 veces): rotarlo tras cada prueba.
8. Endpoints solo desde doc viva (`api-inference.huggingface.co` murió sin
   aviso).
9. **Ningún generador de video gratis tiene API pública**: ni Meta AI (Meta
   Model API = solo texto/Muse Spark; Muse Video "coming soon") ni Flow. Las
   librerías tipo `meta-ai-api` / `metaai-sdk` / `meta-ai-mcp` son ingeniería
   inversa o automatización del navegador: violan ToS, arriesgan la cuenta y
   se rompen solas (Meta migró a WebSocket DGW y tumbó los métodos HTTP).
   La integración legal es generar a mano → importar clips.
10. No publicar los episodios en el feed de Vibes: es público y se usa para
    entrenar. Generar y descargar; publicar solo en el canal propio.

## Pendientes transversales

- M2: notebook SadTalker (ruta ilimitada real), subtítulos por personaje,
  check QC de clips, proveedor Gemini API opcional.
- Transiciones xfade, SFX, QC con LLM, verificación de las 8 plantillas.
- Confirmar endpoints de Pollinations contra la doc viva.
- Colab: SOLO cómputo del pipeline; NUNCA navegador remoto (ToS).
- Mapa del navegador remoto en `navegador-remoto`; reglas de sesión en
  `maximizador-ia` (privado).
