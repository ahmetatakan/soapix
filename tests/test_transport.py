"""
Tests for Transport retry logic, error semantics, and SSL handling.
"""

from __future__ import annotations

import ssl
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from soapix.exceptions import HttpError, TimeoutError
from soapix.transport import AsyncTransport, Transport

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int, content: bytes = b"<ok/>") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    return resp


# ---------------------------------------------------------------------------
# Transport (sync) — retry semantics
# ---------------------------------------------------------------------------

class TestTransportRetry:
    """5xx errors should retry up to `retries` times; 4xx should not retry."""

    def test_success_returns_content(self):
        t = Transport()
        resp = _make_response(200, b"<result/>")
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.return_value = resp
            result = t.send("http://example.com", "Action", b"<req/>")
        assert result == b"<result/>"

    def test_4xx_raises_immediately_no_retry(self):
        t = Transport(retries=3)
        resp = _make_response(400)
        with patch("httpx.Client") as MockClient:
            mock_post = MockClient.return_value.__enter__.return_value.post
            mock_post.return_value = resp
            with pytest.raises(HttpError, match="400"):
                t.send("http://example.com", "Action", b"<req/>")
        # Must have been called exactly once — no retries
        assert mock_post.call_count == 1

    def test_5xx_retries_up_to_count(self):
        t = Transport(retries=2)
        resp = _make_response(503)
        with patch("httpx.Client") as MockClient:
            mock_post = MockClient.return_value.__enter__.return_value.post
            mock_post.return_value = resp
            with pytest.raises(HttpError, match="503"):
                t.send("http://example.com", "Action", b"<req/>")
        # 1 initial attempt + 2 retries = 3 total
        assert mock_post.call_count == 3

    def test_5xx_no_retries_configured(self):
        t = Transport(retries=0)
        resp = _make_response(500)
        with patch("httpx.Client") as MockClient:
            mock_post = MockClient.return_value.__enter__.return_value.post
            mock_post.return_value = resp
            with pytest.raises(HttpError, match="500"):
                t.send("http://example.com", "Action", b"<req/>")
        assert mock_post.call_count == 1

    def test_5xx_success_on_retry(self):
        """If 5xx on first try but 200 on second, should return the 200."""
        t = Transport(retries=1)
        with patch("httpx.Client") as MockClient:
            mock_post = MockClient.return_value.__enter__.return_value.post
            mock_post.side_effect = [
                _make_response(500),
                _make_response(200, b"<ok/>"),
            ]
            result = t.send("http://example.com", "Action", b"<req/>")
        assert result == b"<ok/>"
        assert mock_post.call_count == 2

    def test_timeout_raises_timeout_error(self):
        t = Transport(timeout=5.0, retries=0)
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.side_effect = (
                httpx.TimeoutException("timed out")
            )
            with pytest.raises(TimeoutError, match="5.0"):
                t.send("http://example.com", "Action", b"<req/>")

    def test_connect_error_raises_http_error(self):
        t = Transport(retries=0)
        with patch("httpx.Client") as MockClient:
            exc = httpx.ConnectError("connection refused")
            MockClient.return_value.__enter__.return_value.post.side_effect = exc
            with pytest.raises(HttpError):
                t.send("http://example.com", "Action", b"<req/>")

    def test_ssl_connect_error_raises_immediately_no_retry(self):
        """SSL ConnectError must raise immediately — no retries."""
        t = Transport(retries=3)
        ssl_exc = ssl.SSLError("certificate verify failed")

        with patch("httpx.Client") as MockClient:
            connect_err = httpx.ConnectError("SSL error")
            connect_err.__cause__ = ssl_exc
            mock_post = MockClient.return_value.__enter__.return_value.post
            mock_post.side_effect = connect_err
            with pytest.raises(HttpError, match="SSL"):
                t.send("https://example.com", "Action", b"<req/>")
        # SSL errors must not retry
        assert mock_post.call_count == 1

    def test_ssl_error_hint_contains_verify_option(self):
        """SSL error message should mention the verify option."""
        t = Transport(retries=0)
        ssl_exc = ssl.SSLError("certificate verify failed")
        connect_err = httpx.ConnectError("SSL error")
        connect_err.__cause__ = ssl_exc

        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.side_effect = connect_err
            with pytest.raises(HttpError) as exc_info:
                t.send("https://example.com", "Action", b"<req/>")

        hint = exc_info.value.hint or ""
        assert "verify" in hint.lower() or "verify" in str(exc_info.value).lower()

    def test_404_is_4xx_no_retry(self):
        t = Transport(retries=5)
        resp = _make_response(404)
        with patch("httpx.Client") as MockClient:
            mock_post = MockClient.return_value.__enter__.return_value.post
            mock_post.return_value = resp
            with pytest.raises(HttpError, match="404"):
                t.send("http://example.com", "Action", b"<req/>")
        assert mock_post.call_count == 1


# ---------------------------------------------------------------------------
# AsyncTransport — retry semantics
# ---------------------------------------------------------------------------

class TestAsyncTransportRetry:
    """Async transport should have the same retry semantics as sync."""

    @pytest.mark.asyncio
    async def test_4xx_raises_immediately_no_retry(self):
        t = AsyncTransport(retries=3)
        resp = _make_response(400)
        with patch("httpx.AsyncClient") as MockClient:
            mock_post = AsyncMock(return_value=resp)
            MockClient.return_value.__aenter__.return_value.post = mock_post
            with pytest.raises(HttpError, match="400"):
                await t.send("http://example.com", "Action", b"<req/>")
        assert mock_post.call_count == 1

    @pytest.mark.asyncio
    async def test_5xx_retries_up_to_count(self):
        t = AsyncTransport(retries=2)
        resp = _make_response(503)
        with patch("httpx.AsyncClient") as MockClient:
            mock_post = AsyncMock(return_value=resp)
            MockClient.return_value.__aenter__.return_value.post = mock_post
            with pytest.raises(HttpError, match="503"):
                await t.send("http://example.com", "Action", b"<req/>")
        assert mock_post.call_count == 3

    @pytest.mark.asyncio
    async def test_ssl_raises_immediately_no_retry(self):
        t = AsyncTransport(retries=3)
        ssl_exc = ssl.SSLError("certificate verify failed")
        connect_err = httpx.ConnectError("SSL error")
        connect_err.__cause__ = ssl_exc

        with patch("httpx.AsyncClient") as MockClient:
            mock_post = AsyncMock(side_effect=connect_err)
            MockClient.return_value.__aenter__.return_value.post = mock_post
            with pytest.raises(HttpError, match="SSL"):
                await t.send("https://example.com", "Action", b"<req/>")
        assert mock_post.call_count == 1

    @pytest.mark.asyncio
    async def test_success_returns_content(self):
        t = AsyncTransport()
        resp = _make_response(200, b"<data/>")
        with patch("httpx.AsyncClient") as MockClient:
            mock_post = AsyncMock(return_value=resp)
            MockClient.return_value.__aenter__.return_value.post = mock_post
            result = await t.send("http://example.com", "Action", b"<req/>")
        assert result == b"<data/>"

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self):
        t = AsyncTransport(timeout=10.0, retries=0)
        with patch("httpx.AsyncClient") as MockClient:
            mock_post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
            MockClient.return_value.__aenter__.return_value.post = mock_post
            with pytest.raises(TimeoutError):
                await t.send("http://example.com", "Action", b"<req/>")
