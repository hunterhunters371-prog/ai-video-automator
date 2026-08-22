"""Capa LLM: un solo punto de acceso, proveedor elegido por .env.

Sin SDK: HTTP vía `requests`. Proveedores:
- openai / anthropic: pago por uso (requieren tarjeta).
- github: GitHub Models — gratis sin tarjeta (GITHUB_MODELS_TOKEN).
- hf: Hugging Face Inference — gratis sin tarjeta (HF_TOKEN, el mismo de imágenes).
- pollinations: Pollinations.ai — gratis sin tarjeta (POLLINATIONS_KEY).
Interfaz única (ARQUITECTURA.md §6): `llm.complete(prompt) -> str`.
"""
from __future__ import annotations

import json
import re

import requests

from . import config

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_MODEL = "gpt-4o-mini"
ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"

# Proveedores OpenAI-compatibles y gratis (sin tarjeta).
# Si un endpoint cambia de catálogo (404 de modelo), ajustar `model` aquí.
COMPAT_PROVIDERS = {
    "github": {
        "url": "https://models.github.ai/inference/chat/completions",
        "key": lambda: config.GITHUB_MODELS_TOKEN,
        "model": "openai/gpt-4o-mini",  # catálogo: github.com/marketplace/models
        "help": "gratis sin tarjeta: github.com/settings/tokens",
    },
    "hf": {
        "url": "https://router.huggingface.co/v1/chat/completions",
        "key": lambda: config.HF_TOKEN,
        "model": "Qwen/Qwen2.5-72B-Instruct",
        "help": "gratis sin tarjeta: huggingface.co/settings/tokens",
    },
    "pollinations": {
        "url": "https://gen.pollinations.ai/v1/chat/completions",  # [no verificado] ruta exacta
        "key": lambda: config.POLLINATIONS_KEY,
        "model": "openai",
        "help": "gratis sin tarjeta: enter.pollinations.ai",
    },
}


class LLMError(Exception):
    """Fallo del proveedor LLM (clave ausente, HTTP, JSON inválido)."""


def complete(prompt: str, system: str = "", json_mode: bool = False,
             temperature: float = 0.7) -> str:
    provider = config.LLM_PROVIDER
    if provider == "openai":
        return _openai(prompt, system, json_mode, temperature)
    if provider == "anthropic":
        return _anthropic(prompt, system, json_mode, temperature)
    if provider in COMPAT_PROVIDERS:
        return _openai_compatible(provider, prompt, system, json_mode, temperature)
    raise LLMError(
        f"LLM_PROVIDER desconocido: {provider!r} "
        f"(usa openai | anthropic | github | hf | pollinations)"
    )


def complete_json(prompt: str, system: str = "", temperature: float = 0.7):
    """complete + parseo robusto: cercos ``` y texto alrededor no rompen."""
    raw = complete(prompt, system=system, json_mode=True, temperature=temperature)
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise LLMError(f"El LLM no devolvió JSON: {text[:200]}")
    obj, _ = json.JSONDecoder().raw_decode(text[min(starts):])
    return obj


def _openai_compatible(provider: str, prompt: str, system: str,
                       json_mode: bool, temperature: float) -> str:
    spec = COMPAT_PROVIDERS[provider]
    key = spec["key"]()
    if not key:
        raise LLMError(
            f"Falta la clave de {provider} en .env — {spec['help']} "
            f"(ver docs/SETUP.md §2)"
        )
    body = {
        "model": spec["model"],
        "messages": ([{"role": "system", "content": system}] if system else [])
        + [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(
        spec["url"],
        headers={"Authorization": f"Bearer {key}"},
        json=body,
        timeout=120,
    )
    if r.status_code != 200:
        raise LLMError(f"{provider} HTTP {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def _openai(prompt: str, system: str, json_mode: bool, temperature: float) -> str:
    if not config.OPENAI_API_KEY:
        raise LLMError("Falta OPENAI_API_KEY en .env (ver docs/SETUP.md §2)")
    body = {
        "model": OPENAI_MODEL,
        "messages": ([{"role": "system", "content": system}] if system else [])
        + [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(
        OPENAI_URL,
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        json=body,
        timeout=120,
    )
    if r.status_code != 200:
        raise LLMError(f"OpenAI HTTP {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def _anthropic(prompt: str, system: str, json_mode: bool, temperature: float) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise LLMError("Falta ANTHROPIC_API_KEY en .env (ver docs/SETUP.md §2)")
    sys_prompt = system
    if json_mode:
        sys_prompt = (sys_prompt
                      + "\nResponde SOLO con JSON válido: sin texto extra ni cercos de código.").strip()
    body = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 4096,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if sys_prompt:
        body["system"] = sys_prompt
    r = requests.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=body,
        timeout=120,
    )
    if r.status_code != 200:
        raise LLMError(f"Anthropic HTTP {r.status_code}: {r.text[:300]}")
    return "".join(block.get("text", "") for block in r.json()["content"])
