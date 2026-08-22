# M2 — Frutinovelas: personajes que hablan (diseño)

Decisiones del 22-ago-2026: **ruta gratis** y **formato narrador + escenas de
personajes**. Comparativa completa y verificada de generadores en
`docs/proveedores-clips.md`.

- **v1 (hoy, gratis, por defecto): Meta AI / Vibes MANUAL.** Flujo oficial:
  prompt "Imagina..." → imagen → **Animate** → vibe, con **lip sync** y
  soporte para animar una imagen **subida**. Encaja con nuestras hojas de
  personaje. Gratis durante el rollout, con tope diario y posible marca de
  agua. `animate.provider: meta` en configs/pipeline.yml.
- **v1-bis: Google Flow MANUAL.** 50 créditos/día, Veo 3.1 Lite = 10 por clip
  (~5 clips/día), sin marca de agua. ANIMATE escribe SIEMPRE las dos guías,
  así que se salta de una a otra cuando una cuota se agota.
- **v2 (ilimitado real, gratis): Colab + SadTalker** contra NUESTRO audio TTS
  → lip-sync exacto. Pendiente (`notebooks/animar.ipynb`).
- **Opción de pago 100% automática:** Gemini API con Veo 3.1 Lite (~$0.05/s,
  ≈ $1.5-2/episodio).
- **NUNCA** automatizar las webs de Meta/Flow ni usar las "APIs" de terceros
  de ingeniería inversa (ToS + se rompen solas). Ver el detalle en
  `docs/proveedores-clips.md`.

**Decisión de audio:** los clips NO aportan la voz. El master es nuestro TTS
(edge-tts multi-voz) y RENDERING ignora el audio de los videos (concat a=0).
Si el lip sync de Meta acepta subir nuestro mp3 de línea, la boca coincide
exacto; si no, el clip actúa y nuestra voz habla [no verificado].

## Formato del producto

Mini historias verticales 9:16 de ~30 s: un narrador conduce la trama y los
personajes (frutas/objetos antropomórficos con cara) hablan en escenas clave.
Subtítulos siempre. Destino: YouTube Shorts.

## Pipeline extendido

```
IDEA → RESEARCH → SCRIPT(historia) → STORYBOARD → ASSETS → VOICE(multi-voz)
     → ANIMATE(manual: Meta AI / Flow) → EDITING → RENDERING → QC
```

### SCRIPT — modo historia

`mode: historia` en la plantilla. El LLM devuelve `personajes[]` (nombre,
especie, personalidad, descriptor visual FIJO, voz edge-tts) y `lineas[]`
(quien/texto/emocion/escena, 8-14 líneas, giro obligatorio, réplica y
contrarréplica, gancho de serie). Rellena además `narration` y `beats` para
que STORYBOARD siga funcionando. Plantilla: `templates/frutinovela/`.

### VOICE — multi-voz

Una pista por línea con la voz de su `quien` (edge-tts): `voice/lNNN_quien.mp3`
+ `voice/lines.json` (offset y duración por línea). Además ensambla
`assets/voice.mp3` para EDITING/RENDERING. Idempotente por archivo.

### ANIMATE — manual con import (v1, construido)

1. Carrusel → no-op.
2. Historia: construye `manifiesto_animacion.json` (clip ↔ línea ↔ personaje
   ↔ contexto visual) y busca `clips/lNNN_quien.*` (.mp4/.mov/.webm, ≥ 100 KB).
3. Si falta alguno: escribe `prompts_meta.md` y `prompts_flow.md` (prompts
   listos para copiar, con reglas anti-"horrible") y PAUSA el proyecto
   (PipelinePaused — NO es FAILED; `resume` vuelve exactamente a ANIMATE).
   Se puede subir de a pocos: cada `resume` vuelve a pausar pidiendo el resto.
4. Con todos los clips, completa y EDITING los monta.

### EDITING / RENDERING / QC

EDITING modo historia: un segmento por LÍNEA con los tiempos reales del audio
(`lines.json`); diálogos → su clip según el manifiesto (`kind: video`),
narrador → imagen de su escena (Ken Burns). RENDERING no cambia: recorta o
repite el clip a la duración de la línea e ignora su audio. QC sigue técnico;
pendiente un check de clips y subtítulos con color por personaje.

## Orden de construcción

1. ~~SCRIPT modo historia + plantilla frutinovela + VOICE multi-voz~~
   **CONSTRUIDO (22-ago)** [no verificado en corrida real].
2. ~~ANIMATE: manifiesto + pausa + import de clips~~ **CONSTRUIDO (22-ago)**.
3. ~~EDITING por línea con clips~~ **CONSTRUIDO (22-ago)**.
4. ~~Guía de prompts Meta AI (imagen → Animate → lip sync) como ruta por
   defecto~~ **CONSTRUIDO (22-ago)** [no verificado].
5. `notebooks/animar.ipynb` (SadTalker en Colab) — pendiente: la única ruta
   verdaderamente ilimitada y con lip-sync exacto.
6. Subtítulos por personaje + check QC de clips — pendiente.
7. Proveedor Gemini API (Veo 3.1 Lite) para automatización total — opcional.
