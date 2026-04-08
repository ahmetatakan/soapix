"""Type stubs for soapix.client — enables IDE autocomplete."""

from typing import Any

class _ServiceProxy:
    def __getattr__(self, method_name: str) -> Any: ...

class _AsyncServiceProxy:
    def __getattr__(self, method_name: str) -> Any: ...

class SoapClient:
    wsdl: str
    debug: bool
    strict: bool
    timeout: float
    retries: int
    verify: bool | str
    service: _ServiceProxy

    def __init__(
        self,
        wsdl: str,
        *,
        debug: bool = ...,
        strict: bool = ...,
        timeout: float = ...,
        retries: int = ...,
        cache: Any = ...,
        verify: bool | str = ...,
        auth: tuple[str, str] | None = ...,
    ) -> None: ...

    def docs(
        self,
        output: str = ...,
        path: str | None = ...,
    ) -> str | None: ...

class AsyncSoapClient:
    wsdl: str
    debug: bool
    strict: bool
    timeout: float
    retries: int
    verify: bool | str
    service: _AsyncServiceProxy

    def __init__(
        self,
        wsdl: str,
        *,
        debug: bool = ...,
        strict: bool = ...,
        timeout: float = ...,
        retries: int = ...,
        cache: Any = ...,
        verify: bool | str = ...,
        auth: tuple[str, str] | None = ...,
    ) -> None: ...

    async def __aenter__(self) -> AsyncSoapClient: ...
    async def __aexit__(self, *args: Any) -> None: ...

    def docs(
        self,
        output: str = ...,
        path: str | None = ...,
    ) -> str | None: ...
