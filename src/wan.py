"""Cliente de Wan (Alibaba Cloud Model Studio) para imagen -> video.

Por que Wan y no Veo/Hailuo: es el unico de los grandes con CUOTA GRATIS real
por API para cuentas nuevas -- 50 s de video por modelo, 90 dias, region
Singapur (scope International). Un episodio de 6 clips x 8 s = 48 s: entra
justo. Despues, 1080P mudo cuesta 0,0375 $/s ~ 1,80 $ por episodio.

Documentacion oficial usada (revision del 16 jun 2026):
  alibabacloud.com/help/en/model-studio/image-to-video-api-reference
  - POST {BASE}/api/v1/services/aigc/video-generation/video-synthesis
    Cabecera OBLIGATORIA `X-DashScope-Async: enable`. Solo existe modo
    asincrono; sin esa cabecera responde "current user api does not support
    synchronous calls".
  - GET  {BASE}/api/v1/tasks/{task_id}
  - Estados: PENDING -> RUNNING -> SUCCEEDED | FAILED | CANCELED | UNKNOWN.
  - Sondeo recomendado por la doc: cada ~15 s. Cada clip tarda 1-5 min.
  - `input.img_url` acepta URL publica O base64 `data:<mime>;base64,<datos>`.
    Usamos base64: las referencias viven en el disco de Cloud Shell y no hay
    donde publicarlas.
  - La URL del video CADUCA A LAS 24 h: se descarga siempre, sin excepcion.
  - Imagen de entrada: JPEG/JPG/PNG (sin canal alfa), BMP o WEBP; ancho y alto
    entre 240 y 8000 px; 10 MB en wan2.2/2.1 y 20 MB en wan2.5/2.6.

La clave y el modelo tienen que ser de la MISMA region: una clave de Singapur
contra el dominio de Pekin falla siempre.
"""
from __future__ import annotations

import base64
import mimetypes
import time
from pathlib import Path

import requests

from . import config

# Singapur / internacional. La doc recomienda migrar al dominio propio del
# workspace ({WorkspaceId}.ap-southeast-1.maas.aliyuncs.com) por rendimiento,
# pero dice literalmente que este sigue funcionando -- y este no obliga a
# buscar el ID del workspace en la consola.
BASE = "https://dashscope-intl.aliyuncs.com"
CREAR = f"{BASE}/api/v1/services/aigc/video-generation/video-synthesis"
TAREAS = f"{BASE}/api/v1/tasks/"

# Duracion en segundos, por modelo (doc oficial). Fija = no se envia el campo.
DURACION_FIJA = {
    "wan2.2-i2v-flash": 5,
    "wan2.2-i2v-plus": 5,
    "wan2.1-i2v-plus": 5,
}
DURACION_RANGO = {
    "wan2.6-i2v-flash": (2, 15),
    "wan2.6-i2v": (2, 15),
    "wan2.1-i2v-turbo": (3, 5),
}
DURACION_ENUM = {
    "wan2.5-i2v-preview": (5, 10),
    "wan2.6-i2v-us": (5, 10, 15),
}
RESOLUCIONES = {
    "wan2.6-i2v-flash": ("720P", "1080P"),
    "wan2.6-i2v": ("720P", "1080P"),
    "wan2.6-i2v-us": ("720P", "1080P"),
    "wan2.5-i2v-preview": ("480P", "720P", "1080P"),
    "wan2.2-i2v-flash": ("480P", "720P"),
    "wan2.2-i2v-plus": ("480P", "1080P"),
    "wan2.1-i2v-turbo": ("480P", "720P"),
    "wan2.1-i2v-plus": ("720P",),
}
# Limite de caracteres del prompt (se trunca solo, pero avisando).
LIMITE_PROMPT = 1500
LIMITE_PROMPT_CORTO = 800  # wan2.2 y wan2.1
LIMITE_NEGATIVO = 500
# Unico modelo con parametro `audio`: hay que pedirle el mudo explicitamente
# (ademas cuesta la mitad). Los wan2.2/2.1 ya son mudos por defecto.
MUDO_EXPLICITO = ("wan2.6-i2v-flash",)
# $/s de video MUDO en Singapur, solo para estimar el gasto en pantalla.
PRECIO_MUDO_USD_S = {
    ("wan2.6-i2v-flash", "720P"): 0.025,
    ("wan2.6-i2v-flash", "1080P"): 0.0375,
    ("wan2.2-i2v-flash", "480P"): 0.015,
    ("wan2.2-i2v-flash", "720P"): 0.036,
    ("wan2.2-i2v-plus", "480P"): 0.02,
    ("wan2.2-i2v-plus", "1080P"): 0.10,
}
MIN_MP4_BYTES = 100_000


class WanError(RuntimeError):
    """Fallo de Wan con el motivo tal cual lo da la API (nunca en silencio)."""


def _b64(ruta: Path) -> str:
    mime = mimetypes.guess_type(ruta.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(ruta.read_bytes()).decode('ascii')}"


def _cabeceras(async_: bool = False) -> dict:
    if not config.DASHSCOPE_API_KEY:
        raise WanError(
            "DASHSCOPE_API_KEY vacia. Saca la clave en la consola de Alibaba "
            "Cloud Model Studio (region Singapur) y anadela al .env "
            "(ver docs/wan-alibaba.md)"
        )
    h = {
        "Authorization": f"Bearer {config.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }
    if async_:
        h["X-DashScope-Async"] = "enable"
    return h


def duracion_real(modelo: str, pedida: float) -> float:
    """Segundos que va a durar el clip de verdad (para el coste y el aviso)."""
    if modelo in DURACION_FIJA:
        return float(DURACION_FIJA[modelo])
    if modelo in DURACION_ENUM:
        opciones = DURACION_ENUM[modelo]
        return float(min(opciones, key=lambda o: abs(o - pedida)))
    lo, hi = DURACION_RANGO.get(modelo, (2, 15))
    return float(max(lo, min(hi, int(round(pedida)))))


def _duracion_param(modelo: str, pedida: float) -> int | None:
    """Valor del campo `duration`, o None si el modelo la tiene fija."""
    if modelo in DURACION_FIJA:
        return None
    return int(duracion_real(modelo, pedida))


def resolucion_valida(modelo: str, pedida: str) -> str:
    """Devuelve una resolucion que el modelo acepte, avisando si se cambia."""
    validas = RESOLUCIONES.get(modelo)
    if not validas or pedida in validas:
        return pedida
    print(
        f"    [!] {modelo} no acepta {pedida} (validas: {', '.join(validas)}); "
        f"uso {validas[-1]}",
        flush=True,
    )
    return validas[-1]


def precio_s(modelo: str, resolucion: str) -> float | None:
    return PRECIO_MUDO_USD_S.get((modelo, resolucion))


def crear_tarea(
    modelo: str,
    prompt: str,
    imagen: Path,
    resolucion: str = "1080P",
    segundos: float = 5,
    negativo: str | None = None,
    prompt_extend: bool = True,
    semilla: int | None = None,
    timeout_s: int = 120,
    intentos: int = 3,
) -> str:
    """Crea la tarea asincrona y devuelve el task_id."""
    if not imagen.exists():
        raise WanError(f"no existe la imagen de origen {imagen}")
    tam_mb = imagen.stat().st_size / 1_048_576
    if tam_mb > 10:
        raise WanError(
            f"{imagen.name} pesa {tam_mb:.1f} MB; el limite es 10 MB "
            "(20 MB en wan2.5/2.6). Reduce la imagen antes de animarla"
        )
    limite = LIMITE_PROMPT if modelo.startswith(("wan2.6", "wan2.5")) else LIMITE_PROMPT_CORTO
    if len(prompt) > limite:
        print(f"    [!] prompt de {len(prompt)} caracteres truncado a {limite}", flush=True)
    cuerpo: dict = {
        "model": modelo,
        "input": {"prompt": prompt[:limite], "img_url": _b64(imagen)},
        "parameters": {
            "resolution": resolucion_valida(modelo, resolucion),
            "prompt_extend": bool(prompt_extend),
            "watermark": False,
        },
    }
    if negativo:
        cuerpo["input"]["negative_prompt"] = negativo[:LIMITE_NEGATIVO]
    dur = _duracion_param(modelo, segundos)
    if dur is not None:
        cuerpo["parameters"]["duration"] = dur
    if modelo.startswith("wan2.6") and prompt_extend:
        # Sin esto, la reescritura del prompt puede devolver un clip con
        # cortes de camara. Una linea de dialogo es UN plano continuo.
        cuerpo["parameters"]["shot_type"] = "single"
    if modelo in MUDO_EXPLICITO:
        cuerpo["parameters"]["audio"] = False  # la voz la pone VOICE; y cuesta la mitad
    if semilla is not None:
        cuerpo["parameters"]["seed"] = int(semilla)

    ultimo = ""
    for intento in range(1, intentos + 1):
        try:
            r = requests.post(CREAR, headers=_cabeceras(async_=True),
                              json=cuerpo, timeout=timeout_s)
        except requests.RequestException as exc:
            ultimo = f"{type(exc).__name__}: {str(exc)[:160]}"
            r = None
        if r is not None:
            try:
                data = r.json()
            except ValueError:
                data = {}
            tid = (data.get("output") or {}).get("task_id")
            if r.status_code == 200 and tid:
                return tid
            ultimo = (f"HTTP {r.status_code} {data.get('code', '')}: "
                      f"{data.get('message') or r.text[:200]}")
            # 4xx que no sea 429 es culpa nuestra: no tiene sentido reintentar.
            if r.status_code not in (408, 429) and r.status_code < 500:
                raise WanError(ultimo)
        if intento < intentos:
            espera = 5 * (2 ** (intento - 1))
            print(f"    reintento {intento}/{intentos - 1} en {espera}s ({ultimo})",
                  flush=True)
            time.sleep(espera)
    raise WanError(ultimo or "no se pudo crear la tarea")


def esperar(task_id: str, intervalo_s: int = 15, timeout_s: int = 900,
            silencioso: bool = False) -> str:
    """Sondea la tarea hasta SUCCEEDED y devuelve la URL del video."""
    limite = time.monotonic() + timeout_s
    estado = "PENDING"
    while time.monotonic() < limite:
        time.sleep(intervalo_s)
        try:
            r = requests.get(TAREAS + task_id, headers=_cabeceras(), timeout=60)
            data = r.json()
        except (requests.RequestException, ValueError) as exc:
            # Un fallo de red suelto no invalida la tarea: sigue viva 24 h.
            if not silencioso:
                print(f"    (sondeo: {type(exc).__name__}, reintento)", flush=True)
            continue
        out = data.get("output") or {}
        estado = out.get("task_status", "UNKNOWN")
        if estado == "SUCCEEDED":
            url = out.get("video_url") or (out.get("results") or {}).get("video_url")
            if not url:
                raise WanError(f"tarea {task_id} SUCCEEDED pero sin video_url: "
                               f"{str(out)[:200]}")
            return url
        if estado in ("FAILED", "CANCELED"):
            raise WanError(f"tarea {task_id} {estado}: "
                           f"{out.get('code', '')} {out.get('message', '')}".strip())
        if estado == "UNKNOWN":
            raise WanError(f"tarea {task_id} desconocida para la API "
                           "(caduca a las 24 h)")
    raise WanError(f"tarea {task_id} sigue en {estado} tras {timeout_s}s")


def descargar(url: str, dest: Path, timeout_s: int = 300) -> Path:
    """Descarga el mp4 a un .part y solo entonces lo renombra.

    Igual que en VOICE: si se corta la descarga, no queda un archivo a medias
    con el nombre bueno que luego parece valido y revienta en RENDERING.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    parcial = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=timeout_s) as r:
        r.raise_for_status()
        with open(parcial, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    tam = parcial.stat().st_size
    if tam < MIN_MP4_BYTES:
        parcial.unlink(missing_ok=True)
        raise WanError(f"el video descargado pesa solo {tam} bytes")
    parcial.replace(dest)
    return dest


def generar(
    modelo: str,
    prompt: str,
    imagen: Path,
    dest: Path,
    resolucion: str = "1080P",
    segundos: float = 5,
    negativo: str | None = None,
    prompt_extend: bool = True,
    semilla: int | None = None,
    intervalo_s: int = 15,
    timeout_tarea_s: int = 900,
) -> dict:
    """Crea la tarea, espera el resultado y descarga el mp4. Todo en uno."""
    task_id = crear_tarea(
        modelo=modelo, prompt=prompt, imagen=imagen, resolucion=resolucion,
        segundos=segundos, negativo=negativo, prompt_extend=prompt_extend,
        semilla=semilla,
    )
    url = esperar(task_id, intervalo_s=intervalo_s, timeout_s=timeout_tarea_s)
    descargar(url, dest)
    return {"task_id": task_id, "url": url,
            "segundos": duracion_real(modelo, segundos), "archivo": dest}
