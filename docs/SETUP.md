# Guía de instalación — requisitos para M1

Todo verificado en las páginas oficiales (agosto 2026). Solo necesitas hacer esto una vez.

---

## 1. FFmpeg (obligatorio)

FFmpeg no se instala con `pip`; es un binario externo. Página oficial: <https://ffmpeg.org/download.html>

### Windows

1. Entra en <https://www.gyan.dev/ffmpeg/builds/> (builds oficiales recomendados en ffmpeg.org).
2. Descarga **`ffmpeg-release-essentials.zip`**.
3. Extrae el ZIP en una carpeta permanente, por ejemplo `C:\ffmpeg`.
4. Añade `C:\ffmpeg\bin` al PATH:
   - Clic derecho en **Este PC** → **Propiedades** → **Configuración avanzada del sistema** → **Variables de entorno**.
   - En **Variables del sistema**, edita `Path` → **Nuevo** → `C:\ffmpeg\bin` → Aceptar todo.
5. Abre una terminal **nueva** y verifica:

   ```bash
   ffmpeg -version
   ffprobe -version
   ```

### macOS

```bash
brew install ffmpeg
```

(o builds estáticos en <https://evermeet.cx/ffmpeg/>)

### Linux

```bash
sudo apt install ffmpeg        # Debian/Ubuntu
sudo dnf install ffmpeg        # Fedora (RPM Fusion)
```

---

## 2. Clave de LLM (obligatoria — elige UNA)

> **Ojo:** GitHub Models fue **retirado permanentemente el 30-jul-2026**
> (<https://github.blog/changelog/2026-07-30-github-models-is-now-retired>).
> Ya no es opción; el código lo rechaza con ese aviso.

**Atajo sin editores:** `sh setup-env.sh` configura proveedor + token sin nano
(el token se pega en lectura oculta: no se muestra ni queda en el historial).

### Gratis, sin tarjeta

**Opción A: Hugging Face** (recomendada — un solo token sirve para LLM **e imágenes IA**)

1. Crea el token con este enlace directo (abre el formulario con el permiso
   de inferencia YA marcado):
   <https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained>
   El permiso necesario es **«Make calls to Inference Providers»**
   (referencia oficial: <https://huggingface.co/docs/inference-providers>).
2. **Un token de solo *read* NO sirve para el LLM**: responde 401/403.
3. En `.env`: `HF_TOKEN=<tu token>` y `LLM_PROVIDER=hf` (o corre `sh setup-env.sh`).
4. El mismo token activa las imágenes IA en ASSETS (ver `configs/images.yml`).

**Opción B: Pollinations**

1. Llave gratis en <https://enter.pollinations.ai>.
2. En `.env`: `POLLINATIONS_KEY=<tu llave>` y `LLM_PROVIDER=pollinations`.
3. La ruta de texto quedó marcada `[no verificado]` en `src/llm.py`: si falla, confirmar en <https://gen.pollinations.ai/docs>.

### De pago (mayor calidad)

**Opción C: OpenAI**

1. Entra en <https://platform.openai.com/api-keys> e inicia sesión (o crea cuenta).
2. Pulsa **Create new secret key**, dale un nombre (ej. `ai-video-automator`).
3. **Cópiala en ese momento**: OpenAI solo la muestra una vez. Si la pierdes, crea otra.
4. Asegúrate de tener crédito/facturación activa en <https://platform.openai.com/settings/organization/billing> (la API es pago por uso).
5. En `.env`: `OPENAI_API_KEY=<tu clave>` y `LLM_PROVIDER=openai`.

Referencia oficial: <https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key>

**Opción D: Anthropic (Claude)**

1. Entra en <https://platform.claude.com/> e inicia sesión (o crea cuenta).
2. Ve a **Settings → API keys**: <https://platform.claude.com/settings/keys>
3. Pulsa **Create key**, ponle nombre y cópiala al instante (empieza por `sk-ant-...`).
4. En `.env`: `ANTHROPIC_API_KEY=<tu clave>` y `LLM_PROVIDER=anthropic`.

Referencia oficial: <https://platform.claude.com/docs/en/get-api-key>

---

## 3. Clave de Pexels (opcional, gratuita)

Para imágenes y videos de stock en la etapa ASSETS. Gratis e inmediata:

1. Crea cuenta en <https://www.pexels.com/join-consumer/>
2. Pide tu clave en <https://www.pexels.com/api/key>
3. La recibes al instante. Una clave por cuenta.

Referencia oficial: <https://help.pexels.com/hc/en-us/articles/900004904026-How-do-I-get-an-API-key>

---

## 4. Configurar el proyecto

```bash
git clone https://github.com/hunterhunters371-prog/ai-video-automator.git
cd ai-video-automator
python -m venv .venv && source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # en Windows: copy .env.example .env
```

Edita `.env` y pega tus claves. **El `.env` está en `.gitignore`: nunca se sube a GitHub.**

## 5. Verificación final

```bash
ffmpeg -version          # FFmpeg OK
python -m src.main --help  # CLI OK
```
