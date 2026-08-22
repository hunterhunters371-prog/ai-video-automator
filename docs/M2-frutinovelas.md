# M2 — Frutinovelas: personajes que hablan (diseño)

Decisiones del 22-ago-2026: **ruta gratis** y **formato narrador + escenas de
personajes**. Ruta de clips elegida tras verificar el mercado:

- **v1 (hoy, gratis): Google Flow MANUAL.** 50 créditos/día gratis, Veo 3.1
  Lite cuesta 10 por clip → ~5 clips/día (un episodio diario). Ingredients
  (hasta 3 imágenes de referencia, 9:16) da la consistencia de personaje. El
  pipeline genera `prompts_flow.md` con el prompt detallado de cada clip y
  PAUSA en ANIMATE; el usuario sube los clips y `resume` monta todo.
- **v2 (gratis, lip-sync exacto): Colab + SadTalker** contra NUESTRO audio
  TTS. Cloud Shell no tiene GPU → notebook `notebooks/animar.ipynb`.
- **Opción de pago (100% automática): Gemini API con Veo 3.1 Lite**, ~$0.05/s
  a 720p (≈ $1.5-2 por episodio). Requiere billing en AI Studio; se enchufa
  como proveedor de ANIMATE sin tocar el resto.
- **Descartado: Meta/Vibes.** Sin API pública para video (Movie Gen no tiene
  acceso de desarrollador): solo manual desde la app → no integrable.
- **NUNCA** automatizar la web de Flow/Meta con el navegador remoto (ToS;
  arriesga la cuenta Google que sostiene Cloud Shell y Colab).

**Decisión de audio (22-ago):** los clips NO aportan la voz. El master de
audio es nuestro TTS (edge-tts multi-voz) y RENDERING ignora el audio de los
videos (concat a=0). Consecuencia: el lip-sync v1 es aproximado (el clip
actúa, nuestra voz habla); el exacto llega en v2 con SadTalker.

## Formato del producto

Mini historias verticales 9:16 de ~30 s: un narrador conduce la trama y los
personajes (frutas/objetos antropomórficos con cara) hablan en escenas clave.
Subtítulos siempre, con color por personaje. Destino: YouTube Shorts.

## Pipeline extendido

```
IDEA → RESEARCH → SCRIPT(historia) → PERSONAJE → STORYBOARD → ASSETS
     → VOICE(multi-voz) → ANIMATE(Flow manual/Colab) → EDITING → RENDERING → QC
```

### SCRIPT — modo historia

`mode: historia` en la plantilla. El LLM devuelve `personajes[]` (nombre,
especie, personalidad, descriptor visual FIJO, voz edge-tts) y `lineas[]`
(quien/texto/emocion/escena, 8-14 líneas, giro obligatorio, réplica y
contrarréplica, gancho de serie). Rellena además `narration` y `beats` para
que STORYBOARD siga funcionando. Plantilla: `templates/frutinovela/`.

### PERSONAJE — etapa nueva (pendiente)

En v1 su papel lo cubre el paso manual de Ingredients en Flow (la guía
`prompts_flow.md` incluye el prompt del ingrediente por personaje). Sigue en
el roadmap para el modo Colab: hoja de personaje reutilizable en
`projects/<id>/characters/<nombre>.png`.

### VOICE — multi-voz

Una pista por línea con la voz de su `quien` (edge-tts): `voice/lNNN_quien.mp3`
+ `voice/lines.json` (offset y duración por línea). Además se ensambla
`assets/voice.mp3` con ffmpeg para EDITING/RENDERING. Idempotente por archivo.

### ANIMATE — Flow manual (v1, construido) / Colab (v2, pendiente)

1. Si script es carrusel → no-op.
2. Historia: construye `manifiesto_animacion.json` (clip ↔ línea ↔ personaje
   ↔ contexto visual del storyboard) y verifica `clips/lNNN_quien.mp4`
   (≥ 100 KB). Si falta alguno: escribe `prompts_flow.md` (ingredientes +
   prompt por clip, listo para pegar) y PAUSA el proyecto (PipelinePaused —
   NO es FAILED; `resume` vuelve exactamente a ANIMATE).
3. Cuando los clips están, la etapa completa y EDITING los monta.

### EDITING / RENDERING / QC

EDITING modo historia: un segmento por LÍNEA con los tiempos reales del audio
(`lines.json`); diálogos → su clip (`kind: video`), narrador → imagen de su
escena (Ken Burns). RENDERING no cambia: los clips se recortan/repiten a la
duración de la línea y su audio se ignora (el master es `voice.mp3`). QC sigue
técnico; pendiente un check de clips y subtítulos con color por personaje.

## Límites honestos

- Flow manual = ~5 clips/día gratis; clips de 4/6/8 s; el clip más largo que
  la línea se recorta y el más corto se repite (mejor pedir 8 s).
- Colab free: GPU T4 con sesiones de ~12 h y posibles cortes.
- Coherencia de personaje = descriptor fijo + Ingredients: buena, no perfecta.

## Orden de construcción

1. ~~SCRIPT modo historia + plantilla frutinovela + VOICE multi-voz~~
   **CONSTRUIDO (22-ago)** [no verificado en corrida real].
2. PERSONAJE (hoja consistente) — pendiente; en v1 lo cubre Ingredients.
3. ~~ANIMATE: manifiesto + prompts_flow.md + pausa PipelinePaused~~
   **CONSTRUIDO (22-ago)** [no verificado].
4. `notebooks/animar.ipynb` (SadTalker en Colab) — pendiente.
5. ~~EDITING por línea con clips + resume~~ **CONSTRUIDO (22-ago)**
   [no verificado].
6. Subtítulos por personaje + check QC de clips — pendiente.
7. Proveedor de pago Gemini API (Veo 3.1 Lite) en ANIMATE — opcional.
