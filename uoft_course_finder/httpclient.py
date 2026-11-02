"""Minimal HTTP client built on :mod:`urllib` with timeout and one retry."""

from __future__ import annotations

import http.client
import socket
import ssl
import time
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ._version import __version__

USER_AGENT = f"uoft-course-finder/{__version__} (+https://github.com/xyan029/uoft_course_finder)"
DEFAULT_TIMEOUT = 30.0
RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


class FetchError(Exception):
    """A page could not be retrieved after the allowed attempts."""


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, HTTPError):
        return exc.code in RETRY_STATUSES
    if isinstance(exc, URLError):
        # Covers DNS failures, connection refused/reset and TLS handshakes.
        return True
    return isinstance(
        exc,
        (socket.timeout, TimeoutError, http.client.HTTPException, ConnectionError),
    )


def fetch(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    allow_insecure_ssl: bool = False,
    retries: int = 1,
    sleep: Callable[[float], None] = time.sleep,
    backoff: float = 1.0,
) -> str:
    """Return the decoded body of ``url``.

    Transient failures (timeouts, connection errors, 5xx and 429 responses)
    are retried ``retries`` times with a short pause. Anything else, and any
    failure after the last attempt, is raised as :class:`FetchError` with the
    original exception attached as ``__cause__``.
    """
    context: Optional[ssl.SSLContext] = None
    if allow_insecure_ssl:
        context = ssl._create_unverified_context()  # opt-in flag, see --allow-insecure-ssl

    attempt = 0
    while True:
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=timeout, context=context) as response:
                raw = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
        except Exception as exc:  # re-raised as FetchError below
            if attempt < retries and _is_transient(exc):
                attempt += 1
                sleep(backoff * attempt)
                continue
            raise FetchError(_describe(exc, url)) from exc


def _describe(exc: BaseException, url: str) -> str:
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code} {exc.reason} for {url}"
    if isinstance(exc, URLError):
        reason = exc.reason
        if isinstance(reason, ssl.SSLCertVerificationError):
            return (
                f"TLS certificate verification failed for {url} "
                "(re-run with --allow-insecure-ssl if you trust the network)"
            )
        return f"could not connect to {url}: {reason}"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return f"timed out fetching {url}"
    return f"{type(exc).__name__} while fetching {url}: {exc}"
