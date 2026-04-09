"""Local HTTP server that powers the soapix interactive playground."""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from soapix.client import SoapClient


class _Handler(BaseHTTPRequestHandler):
    """Request handler — subclassed at runtime to bind a SoapClient instance."""

    client: SoapClient  # injected via type(...) before serving

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._serve_html()
        elif path == "/api/operations":
            self._serve_operations()
        elif path == "/api/meta":
            self._serve_meta()
        else:
            self._json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/call/"):
            op_name = path[len("/api/call/"):]
            self._call_operation(op_name)
        else:
            self._json({"error": "not found"}, status=404)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _serve_html(self) -> None:
        from soapix.playground.ui import HTML
        body = HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_meta(self) -> None:
        doc = self.client._wsdl_doc
        self._json({
            "service_name": doc.service_name,
            "endpoint": doc.endpoint,
            "soap_version": doc.soap_version.value,
        })

    def _serve_operations(self) -> None:
        from soapix.docs.resolver import resolve_input_fields

        doc = self.client._wsdl_doc
        result = []
        for name, op in sorted(doc.operations.items()):
            fields = resolve_input_fields(op, doc)
            result.append({
                "name": name,
                "fields": [
                    {
                        "name": f.name,
                        "type": f.type_name,
                        "required": f.required,
                    }
                    for f in fields
                ],
            })
        self._json(result)

    def _call_operation(self, op_name: str) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            kwargs: dict[str, Any] = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            self._json({"ok": False, "error": "Invalid JSON body"})
            return

        try:
            result = self.client._call(op_name, **kwargs)
            self._json({"ok": True, "result": result})
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass  # suppress default stderr logging


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def serve(
    client: SoapClient,
    host: str = "localhost",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    """
    Start the interactive playground for *client* and block until Ctrl-C.

    Args:
        client:       A loaded SoapClient instance.
        host:         Interface to bind (default: localhost).
        port:         TCP port (default: 8765).
        open_browser: Automatically open the browser (default: True).
    """
    # Bind the client to the handler class via a dynamic subclass
    handler_cls = type("Handler", (_Handler,), {"client": client})

    server = ThreadingHTTPServer((host, port), handler_cls)
    url = f"http://{host}:{port}"

    from rich.console import Console
    c = Console()
    doc = client._wsdl_doc
    c.print(f"\n[bold magenta]soapix playground[/bold magenta] — [cyan]{doc.service_name}[/cyan]")
    c.print(f"  [dim]Listening at [link={url}]{url}[/link][/dim]")
    c.print(f"  [dim]{len(doc.operations)} operation(s) available[/dim]")
    c.print("  [dim]Press [bold]Ctrl+C[/bold] to stop[/dim]\n")

    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        c.print("\n[dim]Playground stopped.[/dim]")
