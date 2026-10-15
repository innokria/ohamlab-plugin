"""Browser-rendered public webpage fetch and readable-text extraction.

This module fetches pages; it does not perform authenticated browsing or attempt
to bypass access controls. URL validation is a useful baseline, not a complete
SSRF security boundary for hostile input.
"""
from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import trafilatura
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from storage.bucket import store

MAX_CHARS = max(1000, int(os.getenv("OHAM_MAX_FETCH_CHARS", "30000")))
TIMEOUT_SECONDS = max(5, int(os.getenv("OHAM_FETCH_TIMEOUT_SECONDS", "25")))


def validate_public_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Only absolute HTTP/HTTPS URLs are supported.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are not allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Local destinations are not allowed.")
    try:
        answers = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
        addresses = {ipaddress.ip_address(answer[4][0].split("%")[0]) for answer in answers}
        if not addresses or any(not address.is_global for address in addresses):
            raise ValueError("Private or non-public IP destinations are not allowed.")
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve hostname: {host}") from exc
    return parsed.geturl()


async def _render_page(url: str) -> tuple[str, str]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (compatible; OhamLabPlugin/0.1)"
            )
            await page.goto(validate_public_url(url), wait_until="domcontentloaded", timeout=TIMEOUT_SECONDS * 1000)
            final_url = validate_public_url(page.url)
            try:
                await page.wait_for_load_state("networkidle", timeout=min(5000, TIMEOUT_SECONDS * 1000))
            except Exception:
                pass
            return await page.content(), final_url
        finally:
            await browser.close()


def fetch_page(url: str, save: bool = True, source_query: str = "") -> dict:
    requested_url = validate_public_url(url)
    started = time.monotonic()
    html, final_url = asyncio.run(_render_page(requested_url))
    text = trafilatura.extract(
        html, url=final_url, output_format="txt", include_comments=False, include_tables=True
    ) or ""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else final_url
    description_tag = soup.find("meta", attrs={"name": "description"})
    description = (description_tag.get("content") or "")[:2000] if description_tag else ""
    canonical_tag = soup.find("link", rel="canonical")
    if not text.strip():
        for node in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
            node.decompose()
        text = soup.get_text("\n", strip=True)
    text = text[:MAX_CHARS]
    if not text.strip():
        raise RuntimeError("No readable text was extracted from this page.")

    document = {
        "url": requested_url,
        "final_url": final_url,
        "title": title[:500],
        "description": description,
        "canonical_url": canonical_tag.get("href") if canonical_tag else None,
        "language": soup.html.get("lang") if soup.html else None,
        "text": text,
        "snippet": text[:600],
        "source_query": source_query or None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "fetch_duration_ms": int((time.monotonic() - started) * 1000),
        "content_length": len(text),
        "extractor": "playwright+trafilatura",
    }
    if save:
        document = store.save_document(document)
    store.log_task("web_fetch", {"url": requested_url, "save": save, "source_query": source_query}, {
        "document_id": document.get("document_id"),
        "title": document["title"],
        "content_length": len(text),
        "final_url": final_url,
    })
    return document
