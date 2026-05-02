"""Shared Playwright browser, started once per worker.

Spawning Chromium per request is the obvious wrong answer (~500ms cold,
the spec wants <2s warm). One browser per worker process, started in
``lifespan`` and closed at shutdown, gets PDF render <300ms warm.

If Playwright's browser binary isn't installed (``playwright install
chromium`` not run), we degrade gracefully: ``browser`` stays ``None``,
``/healthz`` reports ``playwright: false``, and the PDF route returns a
503 problem+json. HTML rendering is unaffected.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from playwright.async_api import Browser, async_playwright

log = logging.getLogger(__name__)


class _BrowserState:
    pw: Any = None
    browser: Browser | None = None


_state = _BrowserState()


async def get_browser() -> Browser | None:
    """FastAPI dependency. Returns ``None`` when no browser is available."""
    return _state.browser


@asynccontextmanager
async def browser_lifespan() -> AsyncIterator[None]:
    try:
        _state.pw = await async_playwright().start()
        _state.browser = await _state.pw.chromium.launch(headless=True)
    except Exception as exc:
        log.warning("Playwright browser unavailable; PDF rendering disabled (%s)", exc)
        _state.browser = None
        if _state.pw is not None:
            await _state.pw.stop()
            _state.pw = None
    try:
        yield
    finally:
        if _state.browser is not None:
            await _state.browser.close()
            _state.browser = None
        if _state.pw is not None:
            await _state.pw.stop()
            _state.pw = None
