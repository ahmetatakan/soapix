"""
SOAP XML Builder — converts Python values into a SOAP Envelope bytes.
"""

from __future__ import annotations

from typing import Any

from lxml import etree

from soapix.exceptions import SerializationError
from soapix.wsdl.namespace import NS_SOAP_ENV_11, NS_SOAP_ENV_12, NS_XSI
from soapix.wsdl.types import BindingStyle, OperationInfo, SoapVersion, WsdlDocument


# XSD primitive types that map directly to Python scalars
_XSD_PRIMITIVES = frozenset(
    [
        "string", "normalizedString", "token",
        "int", "integer", "long", "short", "byte",
        "unsignedInt", "unsignedLong", "unsignedShort", "unsignedByte",
        "float", "double", "decimal",
        "boolean",
        "dateTime", "date", "time", "duration",
        "base64Binary", "hexBinary",
        "anyURI", "QName",
        "anyType", "anySimpleType",
    ]
)


class SoapBuilder:
    """
    Builds a SOAP Envelope from an OperationInfo and user-provided kwargs.

    Supports:
    - SOAP 1.1 and 1.2 envelopes
    - document/literal and document/wrapped styles
    - Nested complex types from WsdlDocument.types
    - Tolerant mode (strict=False): missing required params → xsi:nil, no error
    - Strict mode (strict=True): missing required params → SerializationError
    """

    def __init__(
        self,
        wsdl_doc: WsdlDocument,
        debug: bool = False,
        strict: bool = False,
    ) -> None:
        self._doc = wsdl_doc
        self._debug = debug
        self._strict = strict

    def build(self, operation: OperationInfo, params: dict[str, Any]) -> bytes:
        """Build and return SOAP Envelope as UTF-8 encoded bytes."""
        soap_env_ns = (
            NS_SOAP_ENV_12
            if operation.soap_version == SoapVersion.SOAP_12
            else NS_SOAP_ENV_11
        )

        nsmap: dict[str, str] = {
            "soapenv": soap_env_ns,
            "xsi": NS_XSI,
        }
        if operation.input_namespace:
            nsmap["tns"] = operation.input_namespace

        envelope = etree.Element(f"{{{soap_env_ns}}}Envelope", nsmap=nsmap)
        body = etree.SubElement(envelope, f"{{{soap_env_ns}}}Body")

        self._build_body(body, operation, params, soap_env_ns)

        return etree.tostring(
            envelope,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=self._debug,
        )

    # ------------------------------------------------------------------
    # Body builders
    # ------------------------------------------------------------------

    def _build_body(
        self,
        body: etree._Element,
        operation: OperationInfo,
        params: dict[str, Any],
        soap_env_ns: str,
    ) -> None:
        tns = operation.input_namespace or self._doc.target_namespace

        if operation.style == BindingStyle.DOCUMENT:
            self._build_document_literal(body, operation, params, tns)
        else:
            self._build_rpc(body, operation, params, tns, soap_env_ns)

    def _build_document_literal(
        self,
        body: etree._Element,
        operation: OperationInfo,
        params: dict[str, Any],
        tns: str,
    ) -> None:
        """Build document/literal body — auto-detects document/wrapped."""
        input_params = operation.input_params

        # document/wrapped detection:
        # Single message part whose element name matches the operation name.
        is_wrapped = (
            len(input_params) == 1
            and input_params[0].type_name == operation.name
        ) or operation.input_wrapper is not None

        wrapper_name = operation.input_wrapper or operation.name

        if is_wrapped or not input_params:
            wrapper = etree.SubElement(body, f"{{{tns}}}{wrapper_name}")
            # Resolve actual type fields from WsdlDocument, not the raw message part
            fields = self._resolve_type_fields(wrapper_name, tns)
            self._serialize_params(wrapper, fields, params, tns)
        else:
            # Bare document/literal: each part is a top-level element
            for param in input_params:
                self._serialize_value(
                    body, param.name, params.get(param.name), param.type_name, tns
                )

    def _build_rpc(
        self,
        body: etree._Element,
        operation: OperationInfo,
        params: dict[str, Any],
        tns: str,
        soap_env_ns: str,
    ) -> None:
        """Build RPC/literal body."""
        op_el = etree.SubElement(body, f"{{{tns}}}{operation.name}")
        self._serialize_params(op_el, operation.input_params, params, tns)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _serialize_params(
        self,
        parent: etree._Element,
        param_defs: list[Any],
        values: dict[str, Any],
        tns: str,
    ) -> None:
        for param in param_defs:
            value = values.get(param.name, param.default)

            if value is None and param.required and self._strict:
                raise SerializationError(
                    f"Zorunlu parametre eksik: '{param.name}'",
                    field=param.name,
                    expected_type=param.type_name,
                    got=None,
                )

            # Skip None optional params in tolerant mode (don't add nil element)
            if value is None and not param.required and not self._strict:
                continue

            self._serialize_value(parent, param.name, value, param.type_name, tns)

    def _serialize_value(
        self,
        parent: etree._Element,
        name: str,
        value: Any,
        type_name: str,
        tns: str,
    ) -> None:
        """Recursively serialize a value into an XML element."""
        if value is None:
            el = etree.SubElement(parent, name)
            el.set(f"{{{NS_XSI}}}nil", "true")
            return

        if isinstance(value, list):
            for item in value:
                self._serialize_value(parent, name, item, type_name, tns)
            return

        el = etree.SubElement(parent, name)

        if isinstance(value, dict):
            # anyType / complex type passed as dict — serialize recursively
            child_fields = self._resolve_type_fields(type_name, tns)
            if child_fields:
                self._serialize_params(el, child_fields, value, tns)
            else:
                for k, v in value.items():
                    self._serialize_value(el, k, v, "anyType", tns)
            return

        if isinstance(value, bool):
            el.text = "true" if value else "false"
        elif hasattr(value, "isoformat"):
            el.text = value.isoformat()
        else:
            el.text = str(value)

    # ------------------------------------------------------------------
    # Type resolution
    # ------------------------------------------------------------------

    def _resolve_type_fields(self, type_name: str, tns: str) -> list[Any]:
        """
        Look up the fields of a complex type by name.
        Tries qualified key {tns}name first, then searches by bare name.
        Returns empty list for unknown / primitive types (anyType fallback).
        """
        key = f"{{{tns}}}{type_name}" if tns else type_name
        type_info = self._doc.types.get(key)
        if type_info is None:
            for t in self._doc.types.values():
                if t.name == type_name:
                    type_info = t
                    break
        return type_info.fields if type_info else []
