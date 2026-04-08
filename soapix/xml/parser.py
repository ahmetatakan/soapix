"""
SOAP Response Parser — converts SOAP XML response into Python dict.
"""

from __future__ import annotations

from typing import Any

from lxml import etree

from soapix.exceptions import SoapFaultError
from soapix.wsdl.namespace import (
    NS_SOAP_ENV_11,
    NS_SOAP_ENV_12,
    localname,
    namespace_of,
    namespaces_match,
)
from soapix.wsdl.types import OperationInfo, WsdlDocument


class SoapResponseParser:
    """
    Parses a SOAP response XML bytes into a Python dict.

    Features:
    - Detects and raises SoapFaultError on soap:Fault
    - Tolerant namespace handling (unknown namespaces are silently ignored)
    - Automatic unwrapping of single-element responses
    - anyType / unknown type fields returned as raw dict
    """

    def __init__(self, wsdl_doc: WsdlDocument, strict: bool = False) -> None:
        self._doc = wsdl_doc
        self._strict = strict

    # Parser instance with huge_tree enabled for large base64 payloads
    _huge_parser = etree.XMLParser(huge_tree=True)

    def parse(self, response_xml: bytes, operation: OperationInfo) -> Any:
        """Parse the raw response bytes and return a Python dict."""
        try:
            root = etree.fromstring(response_xml, self._huge_parser)
        except etree.XMLSyntaxError as e:
            from soapix.exceptions import SoapCallError
            raise SoapCallError(
                f"Service returned invalid XML: {e}",
                method=operation.name,
                endpoint=operation.endpoint,
            )

        body = self._find_body(root)
        if body is None:
            from soapix.exceptions import SoapCallError
            raise SoapCallError(
                "soap:Body not found in response",
                method=operation.name,
                endpoint=operation.endpoint,
            )

        # Check for soap:Fault
        fault = self._find_fault(body)
        if fault is not None:
            self._raise_fault(fault, operation)

        # Unwrap response body
        return self._unwrap(body, operation)

    # ------------------------------------------------------------------
    # Body / Fault finding
    # ------------------------------------------------------------------

    def _find_body(self, root: etree._Element) -> etree._Element | None:
        """Find soap:Body, tolerant of SOAP 1.1 vs 1.2 namespace differences."""
        for child in root:
            local = localname(child.tag)
            ns = namespace_of(child.tag)
            if local == "Body" and (
                namespaces_match(ns, NS_SOAP_ENV_11)
                or namespaces_match(ns, NS_SOAP_ENV_12)
            ):
                return child
        return None

    def _find_fault(self, body: etree._Element) -> etree._Element | None:
        for child in body:
            if localname(child.tag) == "Fault":
                return child
        return None

    def _raise_fault(
        self, fault_el: etree._Element, operation: OperationInfo
    ) -> None:
        """Extract fault details and raise SoapFaultError."""
        fault_code = ""
        fault_string = ""
        detail_el: etree._Element | None = None

        for child in fault_el:
            local = localname(child.tag)
            if local in ("faultcode", "Code"):
                val = child.find(".//{*}Value")
                fault_code = (val.text or "").strip() if val is not None else (child.text or "").strip()
            elif local in ("faultstring", "Reason"):
                val = child.find(".//{*}Text")
                fault_string = (val.text or "").strip() if val is not None else (child.text or "").strip()
            elif local == "detail":
                detail_el = child

        # If faultstring is missing, try to extract a message from structured
        # fault detail (e.g. <EFaturaFault><msg>...</msg></EFaturaFault>)
        if not fault_string and detail_el is not None:
            for msg_el in detail_el.iter():
                if localname(msg_el.tag) in ("msg", "message", "faultMessage", "text"):
                    text = (msg_el.text or "").strip()
                    if text:
                        fault_string = text
                        break

        detail_str = etree.tostring(detail_el, encoding="unicode") if detail_el is not None else None

        raise SoapFaultError(
            fault_code=fault_code or "Unknown",
            fault_string=fault_string or "Unknown fault",
            detail=detail_str,
            method=operation.name,
            endpoint=operation.endpoint,
        )

    # ------------------------------------------------------------------
    # Response unwrapping
    # ------------------------------------------------------------------

    def _unwrap(self, body: etree._Element, operation: OperationInfo) -> Any:
        """
        Extract the meaningful payload from soap:Body.

        Handles:
        - document/wrapped: <MethodResponse><field>...</field></MethodResponse>
        - document/literal bare: multiple top-level elements
        - Single-child auto-unwrap
        """
        children = list(body)
        if not children:
            return {}

        # If there's exactly one child, unwrap it
        if len(children) == 1:
            return self._element_to_dict(children[0])

        # Multiple children — return as list
        return [self._element_to_dict(child) for child in children]

    # ------------------------------------------------------------------
    # XML → dict conversion
    # ------------------------------------------------------------------

    def _element_to_dict(self, element: etree._Element) -> Any:
        """
        Recursively convert an lxml element to a Python dict/scalar.

        Rules:
        - Leaf element with text → return text (cast to appropriate type)
        - Element with children → return dict {localname: value}
        - Multiple siblings with same name → return list
        - xsi:nil="true" → return None
        """
        # Check for xsi:nil
        nil = element.get(f"{{{NS_SOAP_ENV_11}}}nil") or element.get("{http://www.w3.org/2001/XMLSchema-instance}nil", "")
        if nil.lower() == "true":
            return None

        children = list(element)

        # Leaf node
        if not children:
            text = (element.text or "").strip()
            return self._cast_value(text)

        # Node with children → dict
        result: dict[str, Any] = {}
        for child in children:
            key = localname(child.tag)
            value = self._element_to_dict(child)

            if key in result:
                # Convert to list on duplicate keys
                existing = result[key]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    result[key] = [existing, value]
            else:
                result[key] = value

        # Auto-unwrap single-key wrapper dicts
        if len(result) == 1:
            only_value = next(iter(result.values()))
            # Only unwrap if it's a dict (not a primitive)
            if isinstance(only_value, dict):
                return only_value

        return result

    def _cast_value(self, text: str) -> Any:
        """Attempt simple type casting for common XSD types."""
        if not text:
            return text

        # Boolean
        if text.lower() == "true":
            return True
        if text.lower() == "false":
            return False

        # Integer
        try:
            return int(text)
        except ValueError:
            pass

        # Float
        try:
            return float(text)
        except ValueError:
            pass

        return text
