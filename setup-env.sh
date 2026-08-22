#!/bin/sh
# ============================================================
#  setup-env.sh — configura el .env del ai-video-automator
#  SIN nano, SIN editores, SIN mostrar el token en pantalla
#  ni dejarlo en el historial del shell.
#
#  Uso (desde la raíz del repo clonado):
#    sh setup-env.sh
#
#  Directo desde GitHub:
#    curl -fsSL https://raw.githubusercontent.com/hunterhunters371-prog/ai-video-automator/main/setup-env.sh -o s.sh && sh s.sh
#
#  OJO: recrea .env desde la plantilla. Si ya tenías otras
#  claves (HF_TOKEN, PEXELS...), vuelve a añadirlas después.
# ============================================================
set -eu

[ -f configs/pipeline.yml ] || {
  echo "[x] Ejecuta desde la carpeta del repo: cd ~/ai-video-automator"
  exit 1
}

cp .env.example .env
echo "[+] .env recreado desde la plantilla (limpio)"

sed -i 's/^LLM_PROVIDER=.*/LLM_PROVIDER=github/' .env
grep -q '^LLM_PROVIDER=github' .env || echo 'LLM_PROVIDER=github' >> .env

printf 'Pega el token de GitHub Models y pulsa Enter (no se vera): '
trap 'stty echo 2>/dev/null || true' EXIT INT TERM
stty -echo 2>/dev/null || true
read -r T
stty echo 2>/dev/null || true
trap - EXIT INT TERM
printf '\n'

[ -n "$T" ] || { echo "[x] token vacio — nada escrito"; exit 1; }
case "$T" in
  ghp_*|github_pat_*|gho_*|ghu_*) ;;
  *) echo "[x] eso no parece un token de GitHub (debe empezar por ghp_ o github_pat_)"; exit 1 ;;
esac

sed -i '/^GITHUB_MODELS_TOKEN=/d' .env
printf 'GITHUB_MODELS_TOKEN=%s\n' "$T" >> .env
unset T
echo "[+] token guardado"

echo "[+] comprobacion (esperado: 1 y 1):"
grep -c '^LLM_PROVIDER=github' .env
grep -cE '^GITHUB_MODELS_TOKEN=(ghp_|github_pat_|gho_|ghu_)' .env

if command -v ffmpeg >/dev/null 2>&1; then
  echo "[+] ffmpeg OK: $(ffmpeg -version 2>/dev/null | head -1)"
else
  echo "[!] falta ffmpeg: sudo apt-get update && sudo apt-get install -y ffmpeg"
fi

echo "[=] listo. Siguiente: python -m src.main resume video-0001"
