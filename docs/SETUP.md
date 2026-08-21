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

### Opción A: OpenAI

1. Entra en <https://platform.openai.com/api-keys> e inicia sesión (o crea cuenta).
2. Pulsa **Create new secret key**, dale un nombre (ej. `ai-video-automator`).
3. **Cópiala en ese momento**: OpenAI solo la muestra una vez. Si la pierdes, crea otra.
4. Asegúrate de tener crédito/facturación activa en <https://platform.openai.com/settings/organization/billing> (la API es pago por uso).

Referencia oficial: <https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key>

### Opción B: Anthropic (Claude)

1. Entra en <https://platform.claude.com/> e inicia sesión (o crea cuenta).
2. Ve a **Settings → API keys**: <https://platform.claude.com/settings/keys>
3. Pulsa **Create key**, ponle nombre y cópiala al instante (empieza por `sk-ant-...`).

Referencia oficial: <https://platform.claude.com/docs/en/get-api-key>

> **Recomendación para el MVP:** OpenAI cubre más piezas del pipeline con un solo proveedor (LLM ahora; Whisper y TTS en fases posteriores). Ambas son pago por uso.

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
