# CONTEXTO DEL PROYECTO — AI Video Automator

## Qué es esto

Pipeline autónomo idea → Short vertical 9:16: research (web+LLM) → script (LLM)
→ storyboard (LLM) → assets (stock/IA/color) → voice (edge-tts) → editing
(whisper + ASS) → rendering (ffmpeg) → QC (ffprobe). Docs: README.md,
docs/ARQUITECTURA.md, docs/MVP.md, docs/SETUP.md.

## Estado actual (22 ago 2026, ~22:00 UTC)

**M1 CERRADO y la generación de imágenes IA VERIFICADA en producción.**

- `video-0001` COMPLETED (89 s): primer Short de punta a punta, pero con las 6
  escenas en `fallback_color` (destapó el bug de imágenes). Se conserva como
  primer éxito histórico.
- `video-0002` COMPLETED (~121 s): **las 5 escenas en `ia:hf`** — el fix de
  imágenes funciona contra la cuenta real. También quedaron verificados los
  avisos nuevos (`[!] PEXELS_API_KEY vacía`) y el progreso por etapa en
  consola. Idea usada: el placeholder literal "tu idea aquí" → fue video de
  prueba; el primero con idea real será video-0003.
- Token HF fine-grained CON el permiso «Make calls to Inference Providers»:
  validado en ambas vías (LLM 200 OK + imágenes 200 OK). Un token de solo
  *read* da 401/403.

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

1. `python -m src.main new "<idea real>"` → video-0003, el primero con tema de
   verdad. No usar `resume` sobre videos COMPLETED: no re-ejecuta etapas.
2. Comprobación posterior:
   `grep -o '"origin": "[^"]*"' projects/video-0003/assets_map.json`
   → debe decir `ia:hf`, no `fallback_color`.
3. Opcional (2 min, gratis): `PEXELS_API_KEY` en `.env` (docs/SETUP.md §3)
   habilita video y foto de stock como recurso intermedio y elimina el aviso
   `[!] PEXELS_API_KEY vacía`.

## Reglas aprendidas — no repetir

1. **Cloud Shell es una terminal remota: NO abre páginas web.** Pegar una URL en
   el prompt solo produce `Exit 127`. Los enlaces (crear tokens, etc.) van en el
   navegador del usuario.
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

## Pendientes después del segundo Short

- M2: transiciones xfade, SFX, loop de QC con LLM (QC actual es técnico: un
  video feo pero válido pasa igual), verificación de las 8 plantillas.
- Confirmar endpoints de Pollinations (texto e imagen) contra la doc viva.
- Colab: SOLO como entorno de render del pipeline (uso legítimo); NUNCA
  navegador remoto (los ToS de Colab lo prohíben → suspenderían la cuenta Google
  que sostiene Cloud Shell).
- El mapa de instancias del navegador remoto vive en el repo `navegador-remoto`
  (CONTEXTO.md propio).
- Repo hermano `maximizador-ia` (privado): núcleo de reglas + roles para los
  prompts de estas sesiones.
