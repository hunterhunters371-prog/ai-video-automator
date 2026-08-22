# Proveedores de clips de personaje — investigación verificada (22-ago-2026)

Qué necesitamos: un clip corto y vertical de un personaje que actúa/habla,
con el MISMO diseño en todos los clips, gratis y repetible a diario.
El audio no importa: el maestro es nuestro TTS (edge-tts multi-voz).

## La respuesta corta sobre "ilimitado"

No existe hoy un generador de video **ilimitado, gratis, de calidad y con
API**. Lo que sí existe:

1. **Ilimitado de verdad** = modelo local en GPU propia (WAN / LTX). Gratis en
   cómputo prestado (Colab free) pero con sesiones limitadas y sin API.
2. **"Ilimitado" práctico** = apilar cuotas diarias gratuitas de varias apps.
   Ninguna sola alcanza; juntas dan más clips por día de los que se publican.

Este repo implementa (2): ANIMATE escribe la guía de prompts para cada
proveedor y el usuario genera donde tenga cuota ese día.

## Meta AI / Vibes — PROVEEDOR POR DEFECTO (`animate.provider: meta`)

Fuente: Centro de ayuda de Meta, "Generate images and videos using Meta AI and
Vibes" (actualizado ~jun-2026) ·
https://www.meta.com/help/artificial-intelligence/1337455336906126/

Flujo oficial (el que usa nuestra guía `prompts_meta.md`):

1. Prompt que empieza por "Imagina" / "Crea una imagen", detallado → Meta AI
   devuelve varias imágenes.
2. Tocar la imagen → **Animate** (con prompt de animación) → "vibe".
3. **Lip sync**: se puede hacer que la imagen hable o cante. También se puede
   animar una imagen **subida por el usuario** — por eso encaja con nuestras
   hojas de personaje.

Ventajas: gratis, imagen→video (clave para consistencia), lip sync nativo,
calidad de Movie Gen (hasta 1080p, ~16 s en el modelo de investigación).

Límites honestos:

- **NO es ilimitado.** "Gratis durante el rollout", con topes de generación,
  colas y límites que Meta ajusta; el foro de creadores recomienda esperar
  ~24 h al toparse. Además The Verge (2026) reportó que Meta prueba
  suscripciones de pago que meterían parte de Vibes en un plan.
- **Marca de agua / branding** posible en los vibes; quitarla recortando
  degrada la imagen (y en 9:16 nos comería al personaje).
- **Disponibilidad por región**: la propia ayuda avisa de que las apps y webs
  "no están disponibles en todos lados" y algunas funciones tampoco.
- **Sin API pública de video.** Meta Model API sirve Muse Spark (texto/código,
  preview US); Muse Video está anunciado como "coming soon". No hay endpoint
  de video para desarrolladores.
- Lo que se publica en el feed de Vibes es público y puede usarse para
  entrenar. Generar y descargar sí; publicar ahí el episodio, no.

### Por qué NO usamos las librerías "API de Meta AI" de terceros

Existen `meta-ai-api` (Strvm), `metaai-sdk` y `meta-ai-mcp`. Todas son
**ingeniería inversa o automatización del navegador con la sesión del usuario**:

- Van contra los términos de servicio de Meta → riesgo de restringir o
  deshabilitar la cuenta (la propia ayuda lo advierte para contenido; el uso
  automatizado es igual de sancionable).
- Se rompen solas: `metaai-sdk` documenta que Meta migró de GraphQL HTTP a
  WebSocket (DGW) y los métodos antiguos dejaron de funcionar.
- Cubren chat e imágenes, **no** el generador de video.

Misma regla que con Flow y Colab: nada de automatizar webs de terceros con
navegador remoto. La integración legal es *generar a mano → importar clips*,
que es exactamente lo que hace ANIMATE.

## Google Flow (`animate.provider: flow`)

- 50 créditos gratis al día (se renuevan a diario); Veo 3.1 Lite = 10 créditos
  → ~5 clips/día. Ingredients acepta hasta 3 imágenes de referencia en 9:16
  para consistencia de personaje.
- Sin marca de agua visible de tipo feed; calidad alta.
- Sin API pública → también manual.
- De pago y 100% automatizable: Gemini API con Veo 3.1 Lite (~$0.05/s a 720p,
  ≈ $1.5-2 por episodio). Es la única vía legal totalmente automática hoy.

## Otras cuotas diarias apilables (para cuando se agoten las dos anteriores)

Datos de comparativas públicas de 2026 [no verificados en nuestra cuenta]:
Kling (~66 créditos/día), Hailuo (~10 videos/día), Pika (~150 créditos +
refresco diario), Vidu (créditos de registro, fuerte en consistencia de
personaje). Todas manuales; sirven como desempate, no como base.

## Ruta verdaderamente ilimitada (pendiente de construir)

SadTalker o WAN/LTX en Colab free: cómputo gratis, sin tope de generaciones
dentro de la sesión, y —con SadTalker— lip-sync exacto contra NUESTRO audio
TTS. Coste: 2 transferencias de zip por episodio y sesiones que se cortan.
Es el paso 4 de `docs/M2-frutinovelas.md`.

## Reglas de calidad que aplican a todos (válidas para el prompt)

1. **Imagen→video, nunca texto→video** para escenas con personaje: la imagen
   fija del personaje es la fuente de verdad y evita el "character drift".
2. **Una imagen por personaje**, reutilizada en todos los clips y episodios.
3. **Movimiento pequeño y lento**: preserva el parecido; la acción grande
   deforma caras.
4. **Prompt en capas**: qué se ve + qué hace + estilo explícito + qué NO
   (sin texto, sin subtítulos).
5. Presupuesta ~5 generaciones por clip usable.
