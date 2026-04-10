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


@pytest.fixture
def soap12_doc():
    return WsdlParser().load(str(FIXTURES / "soap12.wsdl"))


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


class TestTypeCasting:
    """Tests for _cast_value type coercion rules."""

    def _parse_body(self, xml_body: bytes, doc, op_name: str):
        doc_ = WsdlParser().load(str(FIXTURES / "simple.wsdl"))
        parser = SoapResponseParser(doc_)
        op = doc_.get_operation(op_name)
        return parser.parse(xml_body, op)

    def test_casts_boolean_false(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId><name>x</name><email>x</email>
              <active>false</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert result["active"] is False

    def test_boolean_case_insensitive(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId><name>x</name><email>x</email>
              <active>TRUE</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert result["active"] is True

    def test_negative_integer(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>-5</userId><name>x</name><email>x</email><active>true</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert result["userId"] == -5

    def test_float_value(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId><name>3.14</name><email>x</email><active>true</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert result["name"] == 3.14

    def test_leading_zeros_preserved_as_string(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>007</userId><name>Bond</name><email>x</email><active>true</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert result["userId"] == "007"

    def test_empty_element_returns_empty_string(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId><name></name><email>x</email><active>true</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert result["name"] == ""

    def test_xsi_nil_returns_none(self, simple_doc):
        xml = b"""<soap:Envelope
            xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId>
              <name xsi:nil="true"/>
              <email>x</email><active>true</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert result["name"] is None


class TestNestedAndRepeated:
    """Tests for nested complex types and repeated elements."""

    def test_nested_dict(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId>
              <name>Test</name>
              <email>t@t.com</email>
              <active>true</active>
              <address>
                <street>Main St</street>
                <city>Istanbul</city>
              </address>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert isinstance(result["address"], dict)
        assert result["address"]["city"] == "Istanbul"

    def test_repeated_elements_become_list(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId><name>x</name><email>x</email><active>true</active>
              <tag>admin</tag>
              <tag>user</tag>
              <tag>editor</tag>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert isinstance(result["tag"], list)
        assert len(result["tag"]) == 3
        assert result["tag"][0] == "admin"

    def test_two_repeated_elements_become_list(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId><name>x</name><email>x</email><active>true</active>
              <role>admin</role>
              <role>viewer</role>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert isinstance(result["role"], list)
        assert result["role"] == ["admin", "viewer"]

    def test_deeply_nested_structure(self, simple_doc):
        # Single-child wrapper elements are auto-unwrapped by the parser:
        # <company><info><name>Acme</name>...</info></company>
        # → result["company"] == {"name": "Acme", "country": "TR"}  (info wrapper stripped)
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId><name>x</name><email>x</email><active>true</active>
              <company>
                <info>
                  <name>Acme</name>
                  <country>TR</country>
                </info>
              </company>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        # Single-key wrapper (info) is auto-unwrapped → company is the inner dict
        assert result["company"]["country"] == "TR"

    def test_empty_body_returns_empty_dict(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body/>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert result == {}

    def test_multiple_body_children_returns_list(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <item><id>1</id></item>
            <item><id>2</id></item>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert isinstance(result, list)
        assert len(result) == 2


class TestXmlComments:
    """Parser must not crash on XML comments or processing instructions."""

    def test_comment_in_envelope_ignored(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <!-- this is a comment -->
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId><name>Test</name><email>t@t.com</email><active>true</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert result["name"] == "Test"

    def test_comment_in_body_ignored(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <!-- another comment -->
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId><name>Test</name><email>t@t.com</email><active>true</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert result["name"] == "Test"

    def test_comment_in_response_element_ignored(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <!-- field comment -->
              <userId>99</userId><name>Test</name><email>t@t.com</email><active>false</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert result["userId"] == 99


class TestNamespaceHandling:
    """Namespace-qualified elements should be keyed by localname only."""

    def test_namespace_qualified_elements_use_localname(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <tns:GetUserResponse xmlns:tns="http://example.com/userservice">
              <tns:userId>42</tns:userId>
              <tns:name>Test</tns:name>
              <tns:email>t@t.com</tns:email>
              <tns:active>true</tns:active>
            </tns:GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert result["userId"] == 42
        assert result["name"] == "Test"

    def test_soap12_envelope_parsed(self, soap12_doc):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <env:Envelope xmlns:env="http://www.w3.org/2003/05/soap-envelope">
          <env:Body>
            <GetOrderResponse xmlns="http://example.com/orders">
              <orderId>ORD-001</orderId>
              <total>99.95</total>
              <status>shipped</status>
            </GetOrderResponse>
          </env:Body>
        </env:Envelope>"""
        parser = SoapResponseParser(soap12_doc)
        op = soap12_doc.get_operation("GetOrder")
        result = parser.parse(xml, op)
        assert result["orderId"] == "ORD-001"
        assert result["status"] == "shipped"


class TestFaultHandling:
    """Detailed fault parsing tests."""

    def test_fault_missing_body_raises(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        with pytest.raises(SoapCallError, match="soap:Body not found"):
            parser.parse(xml, op)

    def test_soap12_fault(self, soap12_doc):
        xml = b"""<env:Envelope xmlns:env="http://www.w3.org/2003/05/soap-envelope">
          <env:Body>
            <env:Fault>
              <env:Code><env:Value>env:Sender</env:Value></env:Code>
              <env:Reason><env:Text>Bad request</env:Text></env:Reason>
            </env:Fault>
          </env:Body>
        </env:Envelope>"""
        parser = SoapResponseParser(soap12_doc)
        op = soap12_doc.get_operation("GetOrder")
        with pytest.raises(SoapFaultError) as exc_info:
            parser.parse(xml, op)
        assert "Sender" in exc_info.value.fault_code
        assert "Bad request" in exc_info.value.fault_string

    def test_fault_with_complex_detail(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <soap:Fault>
              <faultcode>Client</faultcode>
              <faultstring>Validation failed</faultstring>
              <detail>
                <ValidationError>
                  <field>userId</field>
                  <message>must be positive</message>
                </ValidationError>
              </detail>
            </soap:Fault>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        with pytest.raises(SoapFaultError) as exc_info:
            parser.parse(xml, op)
        assert exc_info.value.fault_code == "Client"
        assert exc_info.value.detail is not None

    def test_fault_detail_fallback_message(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <soap:Fault>
              <faultcode>Server</faultcode>
              <faultstring></faultstring>
              <detail>
                <ServiceFault>
                  <msg>Custom error from service</msg>
                </ServiceFault>
              </detail>
            </soap:Fault>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        with pytest.raises(SoapFaultError) as exc_info:
            parser.parse(xml, op)
        assert "Custom error from service" in exc_info.value.fault_string

    def test_fault_without_detail(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <soap:Fault>
              <faultcode>Server.ApplicationException</faultcode>
              <faultstring>Unexpected error</faultstring>
            </soap:Fault>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        with pytest.raises(SoapFaultError) as exc_info:
            parser.parse(xml, op)
        assert exc_info.value.detail is None


class TestElementAttributes:
    """Elements with XML attributes should be captured correctly."""

    def test_element_with_attribute(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId>
              <name lang="tr">Ahmet</name>
              <email>x</email><active>true</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        # name has attribute lang — returned as dict with _value
        assert isinstance(result["name"], dict)
        assert result["name"]["lang"] == "tr"
        assert result["name"]["_value"] == "Ahmet"

    def test_element_with_only_attribute_no_text(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId>
              <name type="display"/>
              <email>x</email><active>true</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        assert isinstance(result["name"], dict)
        assert result["name"]["type"] == "display"

    def test_xsi_nil_false_with_other_attribute(self, simple_doc):
        # xsi:nil="false" — element is NOT nil; nil attribute must be stripped from result
        xml = b"""<soap:Envelope
            xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId>
              <name xsi:nil="false" lang="en">Ahmet</name>
              <email>x</email><active>true</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        # Element is not nil — should parse normally; nil attr must NOT appear in result
        assert isinstance(result["name"], dict)
        assert "nil" not in result["name"]
        assert result["name"]["lang"] == "en"
        assert result["name"]["_value"] == "Ahmet"


class TestMixedContent:
    """Elements with both text and child nodes (mixed content)."""

    def test_mixed_content_text_captured_as_text_key(self, simple_doc):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetUserResponse xmlns="http://example.com/userservice">
              <userId>1</userId>
              <name>Hello <b>world</b></name>
              <email>x</email><active>true</active>
            </GetUserResponse>
          </soap:Body>
        </soap:Envelope>"""
        parser = SoapResponseParser(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = parser.parse(xml, op)
        # Mixed content: leading text → _text key
        assert isinstance(result["name"], dict)
        assert result["name"]["_text"] == "Hello"
