"""HTTP client tests: timeouts, headers, retries and error messages."""

from __future__ import annotations

import io
import socket
import ssl
from email.message import Message
from urllib.error import HTTPError, URLError

import pytest

from uoft_course_finder import httpclient
from uoft_course_finder.httpclient import USER_AGENT, FetchError, fetch


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, charset: str = "utf-8") -> None:
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = f"text/html; charset={charset}"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def install_urlopen(monkeypatch, outcomes):
    """Patch urlopen to pop one outcome per call; record every call."""
    calls = []

    def fake_urlopen(request, timeout=None, context=None):
        calls.append({"request": request, "timeout": timeout, "context": context})
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(httpclient, "urlopen", fake_urlopen)
    return calls


def test_fetch_sends_user_agent_and_timeout(monkeypatch):
    calls = install_urlopen(monkeypatch, [FakeResponse(b"<html>ok</html>")])
    body = fetch("https://example.test/search", timeout=7.5)
    assert body == "<html>ok</html>"
    (call,) = calls
    assert call["timeout"] == 7.5
    assert call["context"] is None
    assert call["request"].get_header("User-agent") == USER_AGENT
    assert "uoft-course-finder/" in USER_AGENT


def test_fetch_decodes_declared_charset(monkeypatch):
    install_urlopen(monkeypatch, [FakeResponse("café".encode("latin-1"), "iso-8859-1")])
    assert fetch("https://example.test/") == "café"


def test_allow_insecure_ssl_uses_unverified_context(monkeypatch):
    calls = install_urlopen(monkeypatch, [FakeResponse(b"ok")])
    fetch("https://example.test/", allow_insecure_ssl=True)
    context = calls[0]["context"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_NONE


def test_transient_error_is_retried_once(monkeypatch):
    calls = install_urlopen(
        monkeypatch, [URLError("connection reset"), FakeResponse(b"second try")]
    )
    sleeps = []
    assert fetch("https://example.test/", sleep=sleeps.append) == "second try"
    assert len(calls) == 2
    assert sleeps == [1.0]


@pytest.mark.parametrize(
    "make_error",
    [
        lambda: socket.timeout("timed out"),
        lambda: TimeoutError("timed out"),
        lambda: ConnectionResetError("reset"),
        lambda: HTTPError("https://example.test/", 503, "Service Unavailable", Message(), None),
        lambda: HTTPError("https://example.test/", 429, "Too Many Requests", Message(), None),
    ],
    ids=["socket-timeout", "TimeoutError", "ConnectionResetError", "http-503", "http-429"],
)
def test_transient_errors_fail_after_retry_budget(monkeypatch, make_error):
    error = make_error()
    calls = install_urlopen(monkeypatch, [error, error])
    with pytest.raises(FetchError) as excinfo:
        fetch("https://example.test/", sleep=lambda _s: None)
    assert len(calls) == 2
    assert excinfo.value.__cause__ is error
    assert "https://example.test/" in str(excinfo.value)


def test_non_transient_http_error_is_not_retried(monkeypatch):
    error = HTTPError("https://example.test/x", 404, "Not Found", Message(), None)
    calls = install_urlopen(monkeypatch, [error])
    with pytest.raises(FetchError, match="HTTP 404 Not Found"):
        fetch("https://example.test/x", sleep=lambda _s: None)
    assert len(calls) == 1


def test_retries_can_be_disabled(monkeypatch):
    calls = install_urlopen(monkeypatch, [URLError("boom")])
    with pytest.raises(FetchError, match="could not connect"):
        fetch("https://example.test/", retries=0)
    assert len(calls) == 1


def test_timeout_message(monkeypatch):
    install_urlopen(monkeypatch, [socket.timeout("x")])
    with pytest.raises(FetchError, match="timed out fetching"):
        fetch("https://example.test/", retries=0)


def test_certificate_error_hints_at_flag(monkeypatch):
    cert_error = ssl.SSLCertVerificationError("certificate verify failed")
    install_urlopen(monkeypatch, [URLError(cert_error)])
    with pytest.raises(FetchError, match="--allow-insecure-ssl"):
        fetch("https://example.test/", retries=0)


def test_unexpected_exception_is_wrapped_without_retry(monkeypatch):
    calls = install_urlopen(monkeypatch, [ValueError("bad value")])
    with pytest.raises(FetchError, match="ValueError while fetching"):
        fetch("https://example.test/")
    assert len(calls) == 1
