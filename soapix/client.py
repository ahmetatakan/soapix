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
