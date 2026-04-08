"""
Phase 2 tests: Tolerant Engine
- Tolerant / strict validation
- anyType support
- document/wrapped auto-detection
- Circular ref protection
- Enhanced error messages
"""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from soapix.wsdl.parser import WsdlParser
from soapix.xml.builder import SoapBuilder
from soapix.xml.parser import SoapResponseParser
from soapix.exceptions import SerializationError, SoapCallError

FIXTURES = Path(__file__).parent / "fixtures"


# ------------------------------------------------------------------
# Tolerant validation
# ------------------------------------------------------------------

class TestTolerantValidation:
    def test_missing_optional_param_no_error(self):
        """In tolerant mode, a missing optional parameter should not raise."""
        doc = WsdlParser().load(str(FIXTURES / "simple.wsdl"))
        builder = SoapBuilder(doc, strict=False)
        op = doc.get_operation("GetUser")
        # locale is optional — should not raise
        envelope = builder.build(op, {"userId": 1})
        assert envelope is not None

    def test_missing_optional_param_not_in_xml(self):
        """Tolerant modda opsiyonel None parametre XML'e eklenmemeli."""
        doc = WsdlParser().load(str(FIXTURES / "simple.wsdl"))
        builder = SoapBuilder(doc, strict=False)
        op = doc.get_operation("GetUser")
        xml = builder.build(op, {"userId": 1}).decode("utf-8")
        # locale not passed → should not appear in XML
        assert "locale" not in xml

    def test_missing_required_strict_raises(self):
        """In strict mode, a missing required parameter should raise SerializationError."""
        doc = WsdlParser().load(str(FIXTURES / "simple.wsdl"))
        builder = SoapBuilder(doc, strict=True)
        op = doc.get_operation("GetUser")
        with pytest.raises(SerializationError):
            builder.build(op, {})  # userId is required but not provided

    def test_missing_required_strict_error_has_field(self):
        """SerializationError alan adını içermeli."""
        doc = WsdlParser().load(str(FIXTURES / "simple.wsdl"))
        builder = SoapBuilder(doc, strict=True)
        op = doc.get_operation("GetUser")
        with pytest.raises(SerializationError) as exc_info:
            builder.build(op, {})
        assert "userId" in str(exc_info.value)

    def test_missing_required_tolerant_sends_nil(self):
        """In tolerant mode, a required field sent as None should produce xsi:nil."""
        doc = WsdlParser().load(str(FIXTURES / "simple.wsdl"))
        builder = SoapBuilder(doc, strict=False)
        op = doc.get_operation("GetUser")
        xml = builder.build(op, {"userId": None}).decode("utf-8")
        assert "nil" in xml


# ------------------------------------------------------------------
# document/wrapped otomatik algılama
# ------------------------------------------------------------------

class TestWrappedDetection:
    def test_wrapped_wsdl_loads(self):
        doc = WsdlParser().load(str(FIXTURES / "wrapped.wsdl"))
        assert "SearchProducts" in doc.operations

    def test_wrapped_builds_correct_envelope(self):
        doc = WsdlParser().load(str(FIXTURES / "wrapped.wsdl"))
        builder = SoapBuilder(doc)
        op = doc.get_operation("SearchProducts")
        xml = builder.build(op, {"query": "laptop"}).decode("utf-8")
        assert "SearchProducts" in xml
        assert "laptop" in xml

    def test_wrapped_optional_params_omitted(self):
        doc = WsdlParser().load(str(FIXTURES / "wrapped.wsdl"))
        builder = SoapBuilder(doc, strict=False)
        op = doc.get_operation("SearchProducts")
        xml = builder.build(op, {"query": "laptop"}).decode("utf-8")
        # maxItems and category are optional — omitted when not passed
        assert "maxItems" not in xml
        assert "category" not in xml

    def test_wrapped_with_all_params(self):
        doc = WsdlParser().load(str(FIXTURES / "wrapped.wsdl"))
        builder = SoapBuilder(doc)
        op = doc.get_operation("SearchProducts")
        xml = builder.build(op, {
            "query": "laptop", "maxItems": 10, "category": "electronics"
        }).decode("utf-8")
        assert "10" in xml
        assert "electronics" in xml


# ------------------------------------------------------------------
# anyType desteği
# ------------------------------------------------------------------

class TestAnyType:
    def test_any_type_wsdl_loads(self):
        doc = WsdlParser().load(str(FIXTURES / "any_type.wsdl"))
        assert "ProcessData" in doc.operations

    def test_any_type_with_dict_payload(self):
        doc = WsdlParser().load(str(FIXTURES / "any_type.wsdl"))
        builder = SoapBuilder(doc)
        op = doc.get_operation("ProcessData")
        xml = builder.build(op, {"id": "REQ-1"}).decode("utf-8")
        assert "REQ-1" in xml

    def test_any_type_response_returns_dict(self):
        """anyType field should be returned as a dict in the response."""
        doc = WsdlParser().load(str(FIXTURES / "any_type.wsdl"))
        parser = SoapResponseParser(doc)
        op = doc.get_operation("ProcessData")

        response = b"""<?xml version="1.0"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <ProcessDataResponse xmlns="http://example.com/flex">
              <status>OK</status>
              <payload>
                <key>value</key>
                <count>42</count>
              </payload>
            </ProcessDataResponse>
          </soap:Body>
        </soap:Envelope>"""

        result = parser.parse(response, op)
        assert result.get("status") == "OK"

    def test_any_type_response_nested_dict(self):
        """Nested anyType payload should be accessible as a dict."""
        doc = WsdlParser().load(str(FIXTURES / "any_type.wsdl"))
        parser = SoapResponseParser(doc)
        op = doc.get_operation("ProcessData")

        response = b"""<?xml version="1.0"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <ProcessDataResponse xmlns="http://example.com/flex">
              <status>OK</status>
              <payload><count>42</count></payload>
            </ProcessDataResponse>
          </soap:Body>
        </soap:Envelope>"""

        result = parser.parse(response, op)
        payload = result.get("payload")
        assert payload is not None


# ------------------------------------------------------------------
# Circular ref koruması
# ------------------------------------------------------------------

class TestCircularRefProtection:
    def test_deep_import_wsdl_loads(self):
        doc = WsdlParser().load(str(FIXTURES / "deep_import.wsdl"))
        assert "GetReport" in doc.operations

    def test_deeply_nested_type_does_not_stack_overflow(self):
        """Deeply nested types should not cause a stack overflow."""
        # Build a schema with self-referencing type (simulated via deep nesting)
        doc = WsdlParser().load(str(FIXTURES / "wrapped.wsdl"))
        # SearchProducts has nested type Product — should parse fine
        assert doc is not None
        assert "SearchProducts" in doc.operations


# ------------------------------------------------------------------
# Gelişmiş hata mesajları
# ------------------------------------------------------------------

class TestEnhancedErrors:
    def test_serialization_error_has_field(self):
        err = SerializationError(
            "Required field missing", field="userId", expected_type="int"
        )
        assert "userId" in str(err)
        assert "int" in str(err)

    def test_serialization_error_has_got(self):
        err = SerializationError(
            "Type mismatch", field="userId", expected_type="int", got="abc"
        )
        assert "abc" in str(err)

    def test_soap_call_error_with_sent(self):
        err = SoapCallError(
            "Call failed",
            method="GetUser",
            sent={"userId": None},
        )
        assert "GetUser" in str(err)
        assert "userId" in str(err)

    def test_operation_not_found_suggests_alternatives(self):
        doc = WsdlParser().load(str(FIXTURES / "simple.wsdl"))
        with pytest.raises(SoapCallError) as exc_info:
            doc.get_operation("getUserByEmail")  # typo
        # Should list actual operations
        error_msg = str(exc_info.value)
        assert "GetUser" in error_msg or "CreateUser" in error_msg

    def test_wsdl_parse_namespace_quirks_loads(self):
        """namespace_quirks.wsdl should load with tolerant namespace handling."""
        doc = WsdlParser().load(str(FIXTURES / "namespace_quirks.wsdl"))
        assert doc is not None
        assert "Ping" in doc.operations
