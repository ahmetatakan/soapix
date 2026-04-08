"""
SOAP XML Builder — converts Python values into a SOAP Envelope bytes.
"""

from __future__ import annotations

from typing import Any

from lxml import etree

from soapix.exceptions import SerializationError
import base64

from soapix.wsdl.namespace import NS_SOAP_ENV_11, NS_SOAP_ENV_12, NS_XSI, NS_XMLMIME
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

        op_ns = operation.input_namespace or self._doc.target_namespace
        nsmap: dict[str, str] = {
            "soapenv": soap_env_ns,
            "xsi": NS_XSI,
        }
        if op_ns:
            nsmap["tns"] = op_ns

        envelope = etree.Element(f"{{{soap_env_ns}}}Envelope", nsmap=nsmap)
        etree.SubElement(envelope, f"{{{soap_env_ns}}}Header")
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

        # Single-part messages always use the part's element as the body wrapper.
        # This covers both classic wrapped (element name == operation name) and
        # element-reference patterns where the element name differs from the
        # operation name (e.g. sendDocument → documentRequest).
        if not input_params or len(input_params) == 1:
            wrapper_name = (
                operation.input_wrapper
                or (input_params[0].type_name if input_params else operation.name)
            )
            wrapper = etree.SubElement(body, f"{{{tns}}}{wrapper_name}")
            fields = self._resolve_type_fields(wrapper_name, tns)
            self._serialize_params(wrapper, fields, params, tns)
        else:
            # Bare document/literal: multiple parts, each is a top-level body element
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

    def _qualify(self, name: str, tns: str) -> str:
        """Return Clark-notation name if tns uses elementFormDefault=qualified."""
        if tns and tns in self._doc.qualified_namespaces:
            return f"{{{tns}}}{name}"
        return name

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

            # Optional None → empty element <field/> (standard SOAP behavior)
            # Required None → xsi:nil (handled inside _serialize_value)
            if value is None and not param.required:
                etree.SubElement(parent, self._qualify(param.name, tns))
                continue

            self._serialize_value(parent, self._qualify(param.name, tns), value, param.type_name, tns)

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
            # Special dict syntax for xmlmime base64Binary with contentType attribute:
            #   {"value": b"...", "contentType": "application/xml"}
            if "value" in value and "contentType" in value:
                raw = value["value"]
                content_type = value["contentType"]
                el.set(f"{{{NS_XMLMIME}}}contentType", content_type)
                el.text = base64.b64encode(raw).decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
                return

            # anyType / complex type passed as dict — serialize recursively
            child_fields = self._resolve_type_fields(type_name, tns)
            if child_fields:
                self._serialize_params(el, child_fields, value, tns)
            else:
                for k, v in value.items():
                    self._serialize_value(el, k, v, "anyType", tns)
            return

        # bytes → base64Binary
        if isinstance(value, (bytes, bytearray)):
            el.text = base64.b64encode(value).decode()
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

    def _resolve_type_fields(
        self,
        type_name: str,
        tns: str,
        _visited: frozenset[str] | None = None,
    ) -> list[Any]:
        """
        Look up the fields of a complex type by name.
        Follows base_type references (element → named complexType, and
        xs:extension inheritance) to return the full field list.
        """
        if ":" in type_name:
            type_name = type_name.split(":", 1)[1]

        _visited = _visited or frozenset()
        if type_name in _visited:
            return []

        key = f"{{{tns}}}{type_name}" if tns else type_name
        type_info = self._doc.types.get(key)
        if type_info is None:
            for t in self._doc.types.values():
                if t.name == type_name:
                    type_info = t
                    break
        if type_info is None:
            return []

        own_fields = type_info.fields
        if type_info.base_type:
            base_fields = self._resolve_type_fields(
                type_info.base_type, tns, _visited | {type_name}
            )
            return base_fields + own_fields
        return own_fields
