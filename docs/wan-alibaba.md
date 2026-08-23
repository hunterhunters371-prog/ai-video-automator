# Clips automáticos con Wan (Alibaba Cloud Model Studio)

Wan es el motor de vídeo de Alibaba. **Qwen** —el modelo que ya usamos para los
guiones— es su LLM; **Wan** es el de imagen y vídeo. Misma casa, misma clave,
misma consola.

Es la única ruta que hemos verificado que sea a la vez **gratis para empezar**,
**automática** (sin navegador) y **con la calidad del formato**.

## Lo que hay que saber antes de nada

- La cuota gratis de estreno es de **50 segundos de vídeo por modelo**, válida
  **90 días** desde que activas Model Studio.
- Solo la dan en la **región Singapur** con ámbito *International*. Una clave
  de Pekín contra el dominio internacional **falla siempre**: modelo, dominio y
  clave tienen que ser de la misma región.
- Un episodio de 6 clips × 8 s = **48 s**: entra entero en la cuota gratis.
- Después de la cuota, con el modelo por defecto (`wan2.6-i2v-flash`, 1080P,
  mudo): **0,0375 $/s ≈ 1,80 $ por episodio**. En 720P baja a 0,025 $/s ≈
  1,20 $. El más barato de todos es `wan2.2-i2v-flash` en 480P (0,015 $/s ≈
  0,72 $), pero sus clips son de 5 s fijos.
- La URL del vídeo que devuelve la API **caduca a las 24 h**. El pipeline lo
  descarga siempre en el momento; no hay nada que recuperar después.

## Alta y clave (una vez)

1. Entra en **Alibaba Cloud Model Studio, región Singapur**:
   <https://modelstudio.console.alibabacloud.com/>
   Acepta el acuerdo de servicio: al activarlo, la cuota gratis se asigna sola.
2. Genera una **API key** en esa misma región (pestaña API key de la consola).
3. Guárdala en el `.env` del proyecto, **sin pegarla nunca en un chat**:

   ```
   cd ~/ai-video-automator && printf 'DASHSCOPE_API_KEY=%s\n' 'sk-TU_CLAVE' >> .env
   ```

4. Comprueba que responde, gastando solo 2 s de cuota:

   ```
   cd ~/ai-video-automator && python scripts/probar-wan.py
   ```

   Deja el resultado en `/tmp/prueba-wan.mp4`. Para verlo:
   `cloudshell download /tmp/prueba-wan.mp4`

## Cómo lo usa el pipeline

Con `animate.provider: wan` en `configs/pipeline.yml`, la etapa ANIMATE:

1. Busca la **imagen maestra** de cada personaje en `projects/<id>/refs/`
   (`limon.png`, `fresa.jpg`). Si no existe, **la genera** con el proveedor de
   imagen de `configs/images.yml` y la guarda ahí.
2. Genera **un clip por línea de diálogo** partiendo siempre de esa imagen
   (imagen → vídeo, nunca texto → vídeo). Por eso el personaje no cambia de
   cara entre escenas: todos los clips salen del mismo archivo.
3. Descarga cada mp4 a `projects/<id>/clips/` y lo valida con ffprobe.
4. EDITING y RENDERING los montan con las voces, la música y los subtítulos.

La duración de cada clip se ajusta a la de su línea de voz (2-15 s con el
modelo por defecto), así que no hay que estirar ni repetir vídeo en el montaje.

**Las imágenes de `refs/` son tuyas y se reutilizan entre episodios.** Si una
no te convence, bórrala y se regenera; si tienes una mejor, súbela con el
nombre del personaje y se usará esa.

## Ajustes (`configs/pipeline.yml` → `animate.wan`)

| Campo | Para qué |
| --- | --- |
| `modelo` | `wan2.6-i2v-flash` (2-15 s), `wan2.2-i2v-flash` (5 s fijos, más barato), `wan2.5-i2v-preview` (5 o 10 s) |
| `resolucion` | `1080P` o `720P`. La cuota gratis se mide en segundos, no en píxeles: a igual gasto, mejor 1080P |
| `max_segundos_por_run` | Ponlo en `50` para no pasar de la cuota gratis en una tanda |
| `max_clips_por_run` | Tope de clips por ejecución, para probar con uno o dos |
| `prompt_extend` | Qwen reescribe el prompt antes de animar. Mejora los prompts cortos y cuesta algo más de tiempo |

## Si algo falla

- **`InvalidApiKey`**: la clave no es de Singapur, o le falta el prefijo `sk-`.
- **Se agotó la cuota**: cambia de `modelo` (cada uno tiene sus propios 50 s
  gratis) o añade saldo. También puedes terminar a mano: ANIMATE deja escritas
  `prompts_meta.md` y `prompts_flow.md` con los prompts de los clips que falten.
- **Quieres ver el episodio ya, sin gastar nada**:
  `SIN_CLIPS=1 python -m src.main resume <id>` lo monta con imágenes fijas.
- **El personaje sale raro**: borra su imagen de `refs/` y vuelve a reanudar, o
  sube tú una imagen mejor con el nombre del personaje.
