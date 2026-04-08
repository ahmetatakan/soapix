"""Tests for SOAP response parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from soapix.wsdl.parser import WsdlParser
from soapix.xml.parser import SoapResponseParser
from soapix.exceptions import SoapFaultError, SoapCallError

FIXTURES = Path(__file__).parent / "fixtures"

SIMPLE_RESPONSE = b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetUserResponse xmlns="http://example.com/userservice">
      <userId>123</userId>
      <name>Ahmet Yilmaz</name>
      <email>ahmet@example.com</email>
      <active>true</active>
    </GetUserResponse>
  </soap:Body>
</soap:Envelope>"""

FAULT_RESPONSE = b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <soap:Fault>
      <faultcode>Server</faultcode>
      <faultstring>Internal server error</faultstring>
      <detail>NullReferenceException in GetUser</detail>
    </soap:Fault>
  </soap:Body>
</soap:Envelope>"""

INVALID_XML = b"not xml at all <<<"


@pytest.fixture
def simple_doc():
    return WsdlParser().load(str(FIXTURES / "simple.wsdl"))


class TestSoapResponseParser:
    def test_parses_simple_response(self, simple_doc):
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(SIMPLE_RESPONSE, op)
        assert result is not None

    def test_extracts_string_field(self, simple_doc):
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(SIMPLE_RESPONSE, op)
        assert result.get("name") == "Ahmet Yilmaz"

    def test_extracts_email_field(self, simple_doc):
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(SIMPLE_RESPONSE, op)
        assert result.get("email") == "ahmet@example.com"

    def test_casts_int(self, simple_doc):
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(SIMPLE_RESPONSE, op)
        assert result.get("userId") == 123

    def test_casts_boolean_true(self, simple_doc):
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(SIMPLE_RESPONSE, op)
        assert result.get("active") is True

    def test_raises_soap_fault(self, simple_doc):
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        with pytest.raises(SoapFaultError):
            parser.parse(FAULT_RESPONSE, op)

    def test_fault_contains_code(self, simple_doc):
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        with pytest.raises(SoapFaultError) as exc_info:
            parser.parse(FAULT_RESPONSE, op)
        assert exc_info.value.fault_code == "Server"

    def test_fault_contains_string(self, simple_doc):
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        with pytest.raises(SoapFaultError) as exc_info:
            parser.parse(FAULT_RESPONSE, op)
        assert "internal server error" in exc_info.value.fault_string.lower()

    def test_invalid_xml_raises(self, simple_doc):
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        with pytest.raises(SoapCallError, match="invalid XML"):
            parser.parse(INVALID_XML, op)
