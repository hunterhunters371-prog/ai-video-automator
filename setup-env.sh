#!/bin/sh
# ============================================================
#  setup-env.sh v2 — configura el .env del ai-video-automator
#  SIN nano, SIN editores, SIN mostrar el token en pantalla
#  ni dejarlo en el historial del shell.
#
#  Proveedores LLM gratis (sin tarjeta):
#    1) hf           — Hugging Face (huggingface.co/settings/tokens).
#                      El mismo token activa las imagenes IA en ASSETS.
#    2) pollinations — Pollinations (enter.pollinations.ai).
#  (github quedo fuera: GitHub Models fue retirado el 30-jul-2026)
#
#  Uso (desde la raíz del repo clonado):
#    sh setup-env.sh
#
#  Directo desde GitHub:
#    curl -fsSL https://raw.githubusercontent.com/hunterhunters371-prog/ai-video-automator/main/setup-env.sh -o s.sh && sh s.sh
#
#  OJO: recrea .env desde la plantilla. Si ya tenías otras
#  claves (PEXELS...), vuelve a añadirlas después.
# ============================================================
set -eu

[ -f configs/pipeline.yml ] || {
  echo "[x] Ejecuta desde la carpeta del repo: cd ~/ai-video-automator"
  exit 1
}

cp .env.example .env
echo "[+] .env recreado desde la plantilla (limpio)"

echo "Proveedor LLM gratis (sin tarjeta):"
echo "  1) hf           — Hugging Face (recomendado: sirve para LLM e imagenes)"
echo "  2) pollinations — Pollinations"
printf 'Elige [1/2] (Enter = 1): '
read -r OP
case "${OP:-1}" in
  1|""|hf)           PROV=hf;           KEYNAME=HF_TOKEN ;;
  2|pollinations)    PROV=pollinations; KEYNAME=POLLINATIONS_KEY ;;
  *) echo "[x] opcion invalida"; exit 1 ;;
esac

if [ "$PROV" = "hf" ]; then
  printf 'Pega el HF_TOKEN y pulsa Enter (no se vera): '
else
  printf 'Pega el POLLINATIONS_KEY y pulsa Enter (no se vera): '
fi
trap 'stty echo 2>/dev/null || true' EXIT INT TERM
stty -echo 2>/dev/null || true
read -r T
stty echo 2>/dev/null || true
trap - EXIT INT TERM
printf '\n'

[ -n "$T" ] || { echo "[x] token vacio — nada escrito"; exit 1; }
if [ "$PROV" = "hf" ]; then
  case "$T" in
    hf_*) ;;
    *) echo "[x] no parece un token de HF (empieza por hf_)"; exit 1 ;;
  esac
else
  case "$T" in
    pk_*|sk_*) ;;
    *) echo "[!] aviso: las llaves de Pollinations suelen empezar por pk_ o sk_ — se guarda igual" ;;
  esac
fi

sed -i "s/^LLM_PROVIDER=.*/LLM_PROVIDER=$PROV/" .env
grep -q '^LLM_PROVIDER=' .env || echo "LLM_PROVIDER=$PROV" >> .env
sed -i "/^$KEYNAME=/d" .env
printf '%s=%s\n' "$KEYNAME" "$T" >> .env
unset T
echo "[+] proveedor: $PROV — token guardado"

echo "[+] comprobacion (esperado: 1 y 1):"
grep -c "^LLM_PROVIDER=$PROV" .env
grep -c "^$KEYNAME=" .env

if command -v ffmpeg >/dev/null 2>&1; then
  echo "[+] ffmpeg OK: $(ffmpeg -version 2>/dev/null | head -1)"
else
  echo "[!] falta ffmpeg: sudo apt-get update && sudo apt-get install -y ffmpeg"
fi

echo "[=] listo. Siguiente: python -m src.main resume video-0001"
