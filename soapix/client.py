"""SoapClient and AsyncSoapClient — main user-facing API."""

from __future__ import annotations

from typing import Any


class _ServiceProxy:
    """Proxy that allows client.service.MethodName(...) call style."""

    def __init__(self, client: SoapClient) -> None:
        self._client = client

    def __getattr__(self, method_name: str) -> Any:
        def caller(**kwargs: Any) -> Any:
            return self._client._call(method_name, **kwargs)
        caller.__name__ = method_name
        return caller


class _AsyncServiceProxy:
    """Async proxy that allows await client.service.MethodName(...) call style."""

    def __init__(self, client: AsyncSoapClient) -> None:
        self._client = client

    def __getattr__(self, method_name: str) -> Any:
        async def caller(**kwargs: Any) -> Any:
            return await self._client._call(method_name, **kwargs)
        caller.__name__ = method_name
        return caller


class SoapClient:
    """
    Synchronous SOAP client.

    Args:
        wsdl:       URL or file path to the WSDL document
        debug:      Print raw XML request/response to terminal
        strict:     Raise on missing required params (default: tolerant)
        timeout:    HTTP request timeout in seconds (default: 30)
        retries:    Number of retry attempts on transient failures (default: 0)
        cache:      Cache backend instance or None to disable (default: module cache)

    Usage:
        client = SoapClient('http://service.example.com/?wsdl')
        result = client.service.GetUser(userId=123)
        client.docs()
    """

    def __init__(
        self,
        wsdl: str,
        *,
        debug: bool = False,
        strict: bool = False,
        timeout: float = 30.0,
        retries: int = 0,
        cache: Any = "default",
        verify: bool | str = True,
        auth: tuple[str, str] | None = None,
    ) -> None:
        self.wsdl = wsdl
        self.debug = debug
        self.strict = strict
        self.timeout = timeout
        self.retries = retries
        self.verify = verify
        self.auth = auth
        self._cache = self._resolve_cache(cache)
        self._wsdl_doc: Any = None
        self.service = _ServiceProxy(self)
        self._load()

    @staticmethod
    def _resolve_cache(cache: Any) -> Any:
        if cache == "default":
            from soapix.cache import get_default_cache
            return get_default_cache()
        return cache  # None → disabled, or custom cache instance

    def _load(self) -> None:
        from soapix.wsdl.parser import WsdlParser
        from soapix.cache import make_cache_key

        key = make_cache_key(self.wsdl, self.strict)

        if self._cache is not None:
            cached = self._cache.get(key)
            if cached is not None:
                self._wsdl_doc = cached
                return

        parser = WsdlParser(strict=self.strict, verify=self.verify, auth=self.auth)
        self._wsdl_doc = parser.load(self.wsdl)

        if self._cache is not None:
            self._cache.set(key, self._wsdl_doc)

    def _call(self, method_name: str, **kwargs: Any) -> Any:
        from soapix.transport import Transport
        from soapix.xml.builder import SoapBuilder
        from soapix.xml.parser import SoapResponseParser

        operation = self._wsdl_doc.get_operation(method_name)
        builder = SoapBuilder(self._wsdl_doc, debug=self.debug, strict=self.strict)
        envelope = builder.build(operation, kwargs)

        transport = Transport(
            timeout=self.timeout,
            debug=self.debug,
            retries=self.retries,
            verify=self.verify,
            auth=self.auth,
        )
        response_xml = transport.send(
            endpoint=operation.endpoint,
            soap_action=operation.soap_action,
            envelope=envelope,
            soap_version=operation.soap_version.value,
        )

        parser = SoapResponseParser(self._wsdl_doc, strict=self.strict)
        return parser.parse(response_xml, operation)

    def docs(
        self,
        output: str = "terminal",
        path: str | None = None,
    ) -> str | None:
        """
        Generate documentation for this service.

        Args:
            output: 'terminal' (default), 'markdown', or 'html'
            path:   File path for markdown/html export

        Returns:
            str if output is 'markdown'/'html' and path is None, else None.
        """
        from soapix.docs.generator import DocsGenerator
        return DocsGenerator(self._wsdl_doc).render(output=output, path=path)

    def generate(self, path: str | None = None) -> str | None:
        """
        Generate a typed Python client class for this service.

        Args:
            path: Write generated code to this file path.
                  If None, returns the code as a string.

        Returns:
            str if path is None, else None (file is written).

        Example:
            # Print to terminal
            print(client.generate())

            # Write to file
            client.generate(path="my_service_client.py")
        """
        from soapix.codegen.generator import ClientGenerator
        code = ClientGenerator(self._wsdl_doc).generate(self.wsdl)
        if path is not None:
            from pathlib import Path
            Path(path).write_text(code, encoding="utf-8")
            return None
        return code

    def serve(
        self,
        host: str = "localhost",
        port: int = 8765,
        open_browser: bool = True,
    ) -> None:
        """
        Start an interactive browser-based playground for this service.

        Opens a local HTTP server with a UI where you can browse operations,
        fill in parameters, and execute SOAP calls — similar to Swagger UI.

        Args:
            host:         Interface to bind (default: 'localhost')
            port:         TCP port (default: 8765)
            open_browser: Open the browser automatically (default: True)

        Press Ctrl+C to stop the server.
        """
        from soapix.playground.server import serve
        serve(self, host=host, port=port, open_browser=open_browser)

    def check(self) -> None:
        """
        Diagnose potential WSDL parsing issues and print a report.

        Checks:
        - Operations discovered
        - Input/output fields resolvable per operation
        - Endpoint present
        - elementFormDefault qualification
        - Type resolution chain integrity

        Raises nothing — prints warnings directly so the user can act before
        making any real service call.
        """
        from soapix.docs.resolver import resolve_input_fields, resolve_output_fields
        from rich.console import Console
        from rich.table import Table
        from rich import box

        doc = self._wsdl_doc
        c = Console()

        c.print(f"\n[bold cyan]soapix check — {doc.service_name}[/bold cyan]")
        c.print(f"[dim]Endpoint: {doc.endpoint or '(empty)'}[/dim]")
        c.print(f"[dim]SOAP {doc.soap_version.value} | "
                f"qualified NS: {len(doc.qualified_namespaces)}[/dim]\n")

        issues: list[str] = []

        # 1. Operations
        if not doc.operations:
            issues.append("No operations found — WSDL may not have parsed correctly")
            c.print("[bold red]✗ No operations found[/bold red]")
        else:
            c.print(f"[green]✓ {len(doc.operations)} operation(s) found[/green]")

        # 2. Endpoint
        if not doc.endpoint:
            issues.append("Endpoint is empty — wsdl:service may be missing")
            c.print("[yellow]⚠ Endpoint is empty[/yellow]")
        else:
            c.print(f"[green]✓ Endpoint: {doc.endpoint}[/green]")

        # 3. Per-operation field resolution
        if doc.operations:
            tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold")
            tbl.add_column("Operation")
            tbl.add_column("Input fields")
            tbl.add_column("Output fields")
            tbl.add_column("Status")

            for op_name, op in sorted(doc.operations.items()):
                in_fields = resolve_input_fields(op, doc)
                out_fields = resolve_output_fields(op, doc)

                has_raw_input = bool(op.input_params)
                in_resolved = len(in_fields)
                out_resolved = len(out_fields)

                if has_raw_input and in_resolved == 0:
                    status = "[red]✗ input unresolved[/red]"
                    issues.append(f"{op_name}: input params declared but no fields resolved")
                else:
                    status = "[green]✓[/green]"

                tbl.add_row(
                    op_name,
                    str(in_resolved) if in_resolved else ("[yellow]0[/yellow]" if has_raw_input else "0"),
                    str(out_resolved),
                    status,
                )

            c.print(tbl)

        # 4. Summary
        if issues:
            c.print(f"[bold red]{len(issues)} issue(s) detected:[/bold red]")
            for issue in issues:
                c.print(f"  [red]• {issue}[/red]")
        else:
            c.print("[bold green]All checks passed.[/bold green]")


class AsyncSoapClient:
    """
    Asynchronous SOAP client.

    Args:
        wsdl:    URL or file path to the WSDL document
        debug:   Print raw XML request/response to terminal
        strict:  Raise on missing required params (default: tolerant)
        timeout: HTTP request timeout in seconds (default: 30)
        retries: Number of retry attempts on transient failures (default: 0)
        cache:   Cache backend instance or None to disable (default: module cache)

    Usage:
        async with AsyncSoapClient('http://service/?wsdl') as client:
            result = await client.service.GetUser(userId=123)
    """

    def __init__(
        self,
        wsdl: str,
        *,
        debug: bool = False,
        strict: bool = False,
        timeout: float = 30.0,
        retries: int = 0,
        cache: Any = "default",
        verify: bool | str = True,
        auth: tuple[str, str] | None = None,
    ) -> None:
        self.wsdl = wsdl
        self.debug = debug
        self.strict = strict
        self.timeout = timeout
        self.retries = retries
        self.verify = verify
        self.auth = auth
        self._cache = SoapClient._resolve_cache(cache)
        self._wsdl_doc: Any = None
        self.service = _AsyncServiceProxy(self)

    async def __aenter__(self) -> AsyncSoapClient:
        await self._load()
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass

    async def _load(self) -> None:
        from soapix.wsdl.parser import WsdlParser
        from soapix.cache import make_cache_key

        key = make_cache_key(self.wsdl, self.strict)

        if self._cache is not None:
            cached = self._cache.get(key)
            if cached is not None:
                self._wsdl_doc = cached
                return

        parser = WsdlParser(strict=self.strict, verify=self.verify, auth=self.auth)
        self._wsdl_doc = await parser.load_async(self.wsdl)

        if self._cache is not None:
            self._cache.set(key, self._wsdl_doc)

    async def _call(self, method_name: str, **kwargs: Any) -> Any:
        from soapix.transport import AsyncTransport
        from soapix.xml.builder import SoapBuilder
        from soapix.xml.parser import SoapResponseParser

        operation = self._wsdl_doc.get_operation(method_name)
        builder = SoapBuilder(self._wsdl_doc, debug=self.debug, strict=self.strict)
        envelope = builder.build(operation, kwargs)

        transport = AsyncTransport(
            timeout=self.timeout,
            debug=self.debug,
            retries=self.retries,
            verify=self.verify,
            auth=self.auth,
        )
        response_xml = await transport.send(
            endpoint=operation.endpoint,
            soap_action=operation.soap_action,
            envelope=envelope,
            soap_version=operation.soap_version.value,
        )

        parser = SoapResponseParser(self._wsdl_doc, strict=self.strict)
        return parser.parse(response_xml, operation)

    def docs(
        self,
        output: str = "terminal",
        path: str | None = None,
    ) -> str | None:
        from soapix.docs.generator import DocsGenerator
        return DocsGenerator(self._wsdl_doc).render(output=output, path=path)

    def generate(self, path: str | None = None) -> str | None:
        """Same as SoapClient.generate() — generate a typed Python client class."""
        from soapix.codegen.generator import ClientGenerator
        code = ClientGenerator(self._wsdl_doc).generate(self.wsdl)
        if path is not None:
            from pathlib import Path
            Path(path).write_text(code, encoding="utf-8")
            return None
        return code

    def serve(
        self,
        host: str = "localhost",
        port: int = 8765,
        open_browser: bool = True,
    ) -> None:
        """Same interactive playground as SoapClient.serve()."""
        proxy = object.__new__(SoapClient)
        proxy._wsdl_doc = self._wsdl_doc
        proxy.debug = self.debug
        proxy.strict = self.strict
        proxy.timeout = self.timeout
        proxy.retries = self.retries
        proxy.verify = self.verify
        proxy.auth = self.auth
        from soapix.playground.server import serve
        serve(proxy, host=host, port=port, open_browser=open_browser)

    def check(self) -> None:
        """Same diagnostics as SoapClient.check()."""
        # Reuse SoapClient's implementation via a temporary wrapper
        proxy = object.__new__(SoapClient)
        proxy._wsdl_doc = self._wsdl_doc
        proxy.check()
