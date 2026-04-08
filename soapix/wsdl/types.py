"""
WSDL type system — pydantic models representing parsed WSDL/XSD structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SoapVersion(str, Enum):
    SOAP_11 = "1.1"
    SOAP_12 = "1.2"


class BindingStyle(str, Enum):
    DOCUMENT = "document"
    RPC = "rpc"


class ParameterUse(str, Enum):
    LITERAL = "literal"
    ENCODED = "encoded"


@dataclass
class TypeInfo:
    """Represents an XSD type definition."""
    name: str
    namespace: str
    kind: str = "complex"          # simple | complex | any | list
    base_type: str | None = None
    fields: list[ParameterInfo] = field(default_factory=list)
    is_array: bool = False
    item_type: str | None = None   # for list/array types

    @property
    def qualified_name(self) -> str:
        return f"{{{self.namespace}}}{self.name}" if self.namespace else self.name


@dataclass
class ParameterInfo:
    """Represents a single input/output parameter of an operation."""
    name: str
    type_name: str
    namespace: str = ""
    required: bool = True
    min_occurs: int = 1
    max_occurs: int | None = 1     # None = unbounded
    default: Any = None
    documentation: str = ""

    @property
    def is_optional(self) -> bool:
        return self.min_occurs == 0

    @property
    def is_list(self) -> bool:
        return self.max_occurs is None or self.max_occurs > 1


@dataclass
class OperationInfo:
    """Represents a WSDL operation (method)."""
    name: str
    endpoint: str
    soap_action: str
    soap_version: SoapVersion = SoapVersion.SOAP_11
    style: BindingStyle = BindingStyle.DOCUMENT
    use: ParameterUse = ParameterUse.LITERAL
    input_params: list[ParameterInfo] = field(default_factory=list)
    output_params: list[ParameterInfo] = field(default_factory=list)
    documentation: str = ""
    # For document/wrapped: the wrapper element name
    input_wrapper: str | None = None
    output_wrapper: str | None = None
    input_namespace: str = ""
    output_namespace: str = ""


@dataclass
class ServiceInfo:
    """Represents a WSDL service."""
    name: str
    endpoint: str
    documentation: str = ""


@dataclass
class WsdlDocument:
    """
    Fully parsed WSDL document — the central object passed between layers.
    """
    target_namespace: str
    services: list[ServiceInfo] = field(default_factory=list)
    operations: dict[str, OperationInfo] = field(default_factory=dict)
    types: dict[str, TypeInfo] = field(default_factory=dict)
    soap_version: SoapVersion = SoapVersion.SOAP_11
    # Namespaces where elementFormDefault="qualified" — child elements must be NS-prefixed
    qualified_namespaces: set[str] = field(default_factory=set)

    def get_operation(self, name: str) -> OperationInfo:
        from soapix.exceptions import SoapCallError
        if name not in self.operations:
            available = ", ".join(sorted(self.operations.keys()))
            raise SoapCallError(
                f"Operation '{name}' is not defined in this service.",
                hint=f"Available operations: {available}",
            )
        return self.operations[name]

    @property
    def service_name(self) -> str:
        return self.services[0].name if self.services else "UnknownService"

    @property
    def endpoint(self) -> str:
        return self.services[0].endpoint if self.services else ""
