"""Búsqueda web sin clave (DuckDuckGo HTML) para la etapa RESEARCH.

Devuelve [{title, url, snippet}]. Sin dependencias nuevas: solo `requests`.
"""
from __future__ import annotations

import re
from html import unescape
from urllib.parse import parse_qs, urlparse

import requests

_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) ai-video-automator/1.0"}


def search(query: str, max_results: int = 5) -> list[dict]:
    r = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers=_UA,
        timeout=30,
    )
    r.raise_for_status()
    results: list[dict] = []
    blocks = re.findall(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
        r'.*?class="result__snippet"[^>]*>(.*?)</a>',
        r.text,
        flags=re.S,
    )
    for href, title_html, snippet_html in blocks:
        url = _clean_url(href)
        title = _strip_tags(title_html)
        if url and title:
            results.append({
                "title": title,
                "url": url,
                "snippet": _strip_tags(snippet_html),
            })
        if len(results) >= max_results:
            break
    return results


def _clean_url(href: str) -> str:
    """Los enlaces salen como redirect //duckduckgo.com/l/?uddg=<url>."""
    if "uddg=" in href:
        full = href if href.startswith("http") else f"https:{href}"
        return parse_qs(urlparse(full).query).get("uddg", [""])[0]
    return href


def _strip_tags(html: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", html)).strip()
