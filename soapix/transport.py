"""
HTTP Transport layer — wraps httpx for sync and async SOAP requests.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from soapix.exceptions import HttpError, TimeoutError


def _is_ssl_error(exc: Exception) -> bool:
    """Return True if the exception chain contains an SSL-related error."""
    import ssl as _ssl
    cause = exc
    while cause is not None:
        if isinstance(cause, _ssl.SSLError):
            return True
        msg = str(cause).lower()
        if "ssl" in msg or "certificate" in msg or "handshake" in msg:
            return True
        cause = getattr(cause, "__cause__", None) or getattr(cause, "__context__", None)
    return False


_DEFAULT_HEADERS = {
    "Content-Type": "text/xml; charset=utf-8",
    "Accept": "text/xml, multipart/related",
}


def _build_headers(soap_action: str, soap_version: str = "1.1") -> dict[str, str]:
    headers = dict(_DEFAULT_HEADERS)
    if soap_version == "1.2":
        headers["Content-Type"] = (
            f'application/soap+xml; charset=utf-8; action="{soap_action}"'
        )
    else:
        headers["SOAPAction"] = f'"{soap_action}"'
    return headers


def _log_request(endpoint: str, soap_action: str, envelope: bytes) -> None:
    from rich.console import Console
    from rich.syntax import Syntax

    console = Console()
    console.print(f"\n[bold cyan]── REQUEST ──────────────────────────────[/bold cyan]")
    console.print(f"[cyan]POST {endpoint}[/cyan]")
    console.print(f"[cyan]SOAPAction: {soap_action}[/cyan]\n")
    console.print(Syntax(envelope.decode("utf-8", errors="replace"), "xml", theme="monokai"))


def _log_response(status_code: int, elapsed_ms: float, body: bytes) -> None:
    from rich.console import Console
    from rich.syntax import Syntax

    console = Console()
    color = "green" if status_code < 400 else "red"
    label = "OK" if status_code < 400 else "ERROR"
    console.print(
        f"\n[bold {color}]── RESPONSE ({status_code} {label}, {elapsed_ms:.0f}ms) ──────────[/bold {color}]"
    )
    console.print(Syntax(body.decode("utf-8", errors="replace"), "xml", theme="monokai"))


class Transport:
    """Synchronous HTTP transport using httpx."""

    def __init__(
        self,
        timeout: float = 30.0,
        debug: bool = False,
        retries: int = 0,
        verify: bool | str = True,
        auth: tuple[str, str] | None = None,
    ) -> None:
        self.timeout = timeout
        self.debug = debug
        self.retries = retries
        self.verify = verify
        self.auth = auth

    def send(
        self,
        endpoint: str,
        soap_action: str,
        envelope: bytes,
        soap_version: str = "1.1",
    ) -> bytes:
        headers = _build_headers(soap_action, soap_version)

        if self.debug:
            _log_request(endpoint, soap_action, envelope)

        attempts = self.retries + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                start = time.monotonic()
                with httpx.Client(timeout=self.timeout, verify=self.verify, auth=self.auth) as client:
                    response = client.post(endpoint, content=envelope, headers=headers)
                elapsed = (time.monotonic() - start) * 1000

                if self.debug:
                    _log_response(response.status_code, elapsed, response.content)

                if 400 <= response.status_code < 500:
                    # 4xx — client error, do not retry
                    raise HttpError(
                        f"HTTP {response.status_code} error",
                        hint=f"Endpoint: {endpoint}",
                    )
                if response.status_code >= 500:
                    # 5xx — server error, retry
                    last_error = HttpError(
                        f"HTTP {response.status_code} error",
                        hint=f"Endpoint: {endpoint} — server error, retrying.",
                    )
                    continue

                return response.content

            except httpx.TimeoutException:
                last_error = TimeoutError(
                    f"Request timed out ({self.timeout}s)",
                    hint=f"Endpoint: {endpoint} — consider increasing the timeout.",
                )
            except httpx.ConnectError as e:
                if _is_ssl_error(e):
                    from urllib.parse import urlparse
                    host = urlparse(endpoint).netloc or endpoint
                    raise HttpError(
                        f"SSL verification failed for {endpoint}",
                        hint=(
                            f"The server's certificate could not be verified.\n\n"
                            f"  Options:\n"
                            f'    verify="/path/to/ca-bundle.pem"   # custom CA bundle\n'
                            f"    verify=False                       # disable (development only)\n\n"
                            f"  To extract the server certificate:\n"
                            f"    openssl s_client -connect {host}:443 -showcerts 2>/dev/null \\\n"
                            f"      | sed -n '/BEGIN CERTIFICATE/,/END CERTIFICATE/p' > ca.pem\n"
                            f"  Then: verify='ca.pem'"
                        ),
                    )
                else:
                    last_error = HttpError(
                        f"Connection error: {e}",
                        hint=f"Is the endpoint reachable? {endpoint}",
                    )
            except httpx.RequestError as e:
                last_error = HttpError(
                    f"Connection error: {e}",
                    hint=f"Is the endpoint reachable? {endpoint}",
                )

        raise last_error or HttpError("Unknown transport error")


class AsyncTransport:
    """Asynchronous HTTP transport using httpx."""

    def __init__(
        self,
        timeout: float = 30.0,
        debug: bool = False,
        retries: int = 0,
        verify: bool | str = True,
        auth: tuple[str, str] | None = None,
    ) -> None:
        self.timeout = timeout
        self.debug = debug
        self.retries = retries
        self.verify = verify
        self.auth = auth

    async def send(
        self,
        endpoint: str,
        soap_action: str,
        envelope: bytes,
        soap_version: str = "1.1",
    ) -> bytes:
        headers = _build_headers(soap_action, soap_version)

        if self.debug:
            _log_request(endpoint, soap_action, envelope)

        attempts = self.retries + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                start = time.monotonic()
                async with httpx.AsyncClient(timeout=self.timeout, verify=self.verify, auth=self.auth) as client:
                    response = await client.post(
                        endpoint, content=envelope, headers=headers
                    )
                elapsed = (time.monotonic() - start) * 1000

                if self.debug:
                    _log_response(response.status_code, elapsed, response.content)

                if 400 <= response.status_code < 500:
                    # 4xx — client error, do not retry
                    raise HttpError(
                        f"HTTP {response.status_code} error",
                        hint=f"Endpoint: {endpoint}",
                    )
                if response.status_code >= 500:
                    # 5xx — server error, retry
                    last_error = HttpError(
                        f"HTTP {response.status_code} error",
                        hint=f"Endpoint: {endpoint} — server error, retrying.",
                    )
                    continue

                return response.content

            except httpx.TimeoutException:
                last_error = TimeoutError(
                    f"Request timed out ({self.timeout}s)",
                    hint=f"Endpoint: {endpoint} — consider increasing the timeout.",
                )
            except httpx.ConnectError as e:
                if _is_ssl_error(e):
                    from urllib.parse import urlparse
                    host = urlparse(endpoint).netloc or endpoint
                    raise HttpError(
                        f"SSL verification failed for {endpoint}",
                        hint=(
                            f"The server's certificate could not be verified.\n\n"
                            f"  Options:\n"
                            f'    verify="/path/to/ca-bundle.pem"   # custom CA bundle\n'
                            f"    verify=False                       # disable (development only)\n\n"
                            f"  To extract the server certificate:\n"
                            f"    openssl s_client -connect {host}:443 -showcerts 2>/dev/null \\\n"
                            f"      | sed -n '/BEGIN CERTIFICATE/,/END CERTIFICATE/p' > ca.pem\n"
                            f"  Then: verify='ca.pem'"
                        ),
                    )
                else:
                    last_error = HttpError(
                        f"Connection error: {e}",
                        hint=f"Is the endpoint reachable? {endpoint}",
                    )
            except httpx.RequestError as e:
                last_error = HttpError(
                    f"Connection error: {e}",
                    hint=f"Is the endpoint reachable? {endpoint}",
                )

        raise last_error or HttpError("Unknown transport error")
