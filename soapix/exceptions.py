"""Soapix exception hierarchy — meaningful, actionable error messages."""

from __future__ import annotations


class SoapixError(Exception):
    """Base exception for all soapix errors."""


# --- WSDL Parse Errors ---

class WsdlParseError(SoapixError):
    """Raised when a WSDL document cannot be read or parsed."""


class WsdlNotFoundError(WsdlParseError):
    """Raised when the WSDL URL or file path cannot be reached."""


class WsdlImportError(WsdlParseError):
    """Raised when a referenced xs:import or xs:include cannot be resolved."""


# --- SOAP Call Errors ---

class SoapCallError(SoapixError):
    """Raised when a SOAP operation call fails."""

    def __init__(
        self,
        message: str,
        service: str | None = None,
        method: str | None = None,
        endpoint: str | None = None,
        hint: str | None = None,
        sent: dict | None = None,
    ) -> None:
        self.service = service
        self.method = method
        self.endpoint = endpoint
        self.hint = hint
        self.sent = sent
        super().__init__(self._format(message))

    def _format(self, message: str) -> str:
        lines = [message, ""]
        if self.service:
            lines.append(f"  Service  : {self.service}")
        if self.method:
            lines.append(f"  Method   : {self.method}")
        if self.endpoint:
            lines.append(f"  Endpoint : {self.endpoint}")
        if self.sent:
            lines.append(f"  Sent     : {self.sent}")
        if self.hint:
            lines.append("")
            lines.append(f"  Hint  : {self.hint}")
        return "\n".join(lines)


class SoapFaultError(SoapCallError):
    """Raised when the server returns a soap:Fault response."""

    def __init__(
        self,
        fault_code: str,
        fault_string: str,
        detail: str | None = None,
        **kwargs: object,
    ) -> None:
        self.fault_code = fault_code
        self.fault_string = fault_string
        self.detail = detail
        message = f"Server returned a SOAP fault: {fault_code} — {fault_string}"
        if detail:
            message += f"\n  Detail: {detail}"
        super().__init__(message, **kwargs)


class HttpError(SoapCallError):
    """Raised on HTTP-level failures (4xx, 5xx, connection error)."""


class TimeoutError(SoapCallError):
    """Raised when the HTTP request times out."""


# --- Serialization Errors ---

class SerializationError(SoapixError):
    """Raised when Python values cannot be serialized to SOAP XML."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        expected_type: str | None = None,
        got: object = None,
    ) -> None:
        self.field = field
        self.expected_type = expected_type
        self.got = got
        super().__init__(self._format(message))

    def _format(self, message: str) -> str:
        lines = [message]
        if self.field:
            lines.append(f"  Field    : {self.field}")
        if self.expected_type:
            lines.append(f"  Expected : {self.expected_type}")
        if self.got is not None:
            lines.append(f"  Got      : {self.got!r} ({type(self.got).__name__})")
        return "\n".join(lines)
