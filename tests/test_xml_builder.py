"""Tests for SOAP XML builder."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from soapix.wsdl.parser import WsdlParser
from soapix.wsdl.types import SoapVersion
from soapix.xml.builder import SoapBuilder

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def simple_doc():
    return WsdlParser().load(str(FIXTURES / "simple.wsdl"))


@pytest.fixture
def soap12_doc():
    return WsdlParser().load(str(FIXTURES / "soap12.wsdl"))


@pytest.fixture
def gib_doc():
    return WsdlParser().load(str(FIXTURES / "gib_efatura.wsdl"))


class TestSoapBuilder:
    def test_builds_valid_xml(self, simple_doc):
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("GetUser")
        envelope_bytes = builder.build(op, {"userId": 123})
        root = etree.fromstring(envelope_bytes)
        assert root is not None

    def test_envelope_tag(self, simple_doc):
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("GetUser")
        envelope_bytes = builder.build(op, {"userId": 123})
        root = etree.fromstring(envelope_bytes)
        assert "Envelope" in root.tag

    def test_body_tag_present(self, simple_doc):
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("GetUser")
        envelope_bytes = builder.build(op, {"userId": 123})
        root = etree.fromstring(envelope_bytes)
        tags = [etree.QName(child.tag).localname for child in root]
        assert "Header" in tags
        assert "Body" in tags

    def test_parameter_included(self, simple_doc):
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("GetUser")
        envelope_bytes = builder.build(op, {"userId": 42})
        xml_str = envelope_bytes.decode("utf-8")
        assert "42" in xml_str

    def test_none_value_gets_xsi_nil(self, simple_doc):
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("GetUser")
        envelope_bytes = builder.build(op, {"userId": None})
        xml_str = envelope_bytes.decode("utf-8")
        assert "nil" in xml_str

    def test_boolean_true_serialization(self, simple_doc):
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("CreateUser")
        envelope_bytes = builder.build(op, {"name": "Ahmet", "email": "a@b.com"})
        xml_str = envelope_bytes.decode("utf-8")
        assert "Ahmet" in xml_str
        assert "a@b.com" in xml_str

    def test_soap12_envelope_namespace(self, soap12_doc):
        builder = SoapBuilder(soap12_doc)
        op = soap12_doc.get_operation("GetOrder")
        envelope_bytes = builder.build(op, {"orderId": "ORD-001"})
        xml_str = envelope_bytes.decode("utf-8")
        # SOAP 1.2 envelope namespace
        assert "soap-envelope" in xml_str or "soap/envelope" in xml_str or "2003/05/soap-envelope" in xml_str

    def test_returns_bytes(self, simple_doc):
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("GetUser")
        result = builder.build(op, {"userId": 1})
        assert isinstance(result, bytes)


class TestElementFormQualified:
    """elementFormDefault="qualified" — child elements must carry namespace prefix."""

    @pytest.fixture
    def qualified_doc(self):
        return WsdlParser().load(str(FIXTURES / "qualified_form.wsdl"))

    def test_namespace_detected(self, qualified_doc):
        assert "http://tempuri.org/" in qualified_doc.qualified_namespaces

    def test_child_elements_are_namespace_qualified(self, qualified_doc):
        builder = SoapBuilder(qualified_doc, debug=True)
        op = qualified_doc.get_operation("GetData")
        xml = builder.build(op, {"pKullaniciAdi": "user", "pSifre": "pass", "pTarih": "2026-01-01"}).decode()
        # All child elements must carry the tns namespace
        assert 'tns:pKullaniciAdi' in xml or '{http://tempuri.org/}pKullaniciAdi' in xml
        assert 'tns:pSifre' in xml or '{http://tempuri.org/}pSifre' in xml

    def test_values_are_present(self, qualified_doc):
        builder = SoapBuilder(qualified_doc, debug=True)
        op = qualified_doc.get_operation("GetData")
        xml = builder.build(op, {"pKullaniciAdi": "user123", "pSifre": "secret"}).decode()
        assert "user123" in xml
        assert "secret" in xml

    def test_unqualified_schema_not_affected(self, simple_doc):
        """simple.wsdl has no elementFormDefault — child elements stay unqualified."""
        builder = SoapBuilder(simple_doc, debug=True)
        op = simple_doc.get_operation("GetUser")
        xml = builder.build(op, {"userId": 1}).decode()
        assert "<userId>" in xml  # no namespace prefix


class TestGibEFaturaBuilder:
    """Builder must use element name (documentRequest), not part name (document)."""

    def test_body_element_is_document_request(self, gib_doc):
        builder = SoapBuilder(gib_doc, debug=True)
        op = gib_doc.get_operation("sendDocument")
        xml = builder.build(op, {"fileName": "test.xml"}).decode()
        assert "documentRequest" in xml
        assert "<document" not in xml

    def test_body_element_is_namespace_qualified(self, gib_doc):
        builder = SoapBuilder(gib_doc, debug=True)
        op = gib_doc.get_operation("sendDocument")
        xml = builder.build(op, {"fileName": "test.xml"}).decode()
        assert "gib.gov.tr/vedop3/eFatura" in xml

    def test_field_values_serialized(self, gib_doc):
        builder = SoapBuilder(gib_doc, debug=True)
        op = gib_doc.get_operation("sendDocument")
        xml = builder.build(op, {"fileName": "GETUSRL#", "hash": "abc123"}).decode()
        assert "GETUSRL#" in xml
        assert "abc123" in xml

    def test_tns_prefix_declared(self, gib_doc):
        builder = SoapBuilder(gib_doc)
        op = gib_doc.get_operation("sendDocument")
        xml = builder.build(op, {"fileName": "x"}).decode()
        assert 'xmlns:tns' in xml


class TestScalarSerialization:
    """Various scalar types must serialize correctly."""

    def test_bytes_serialized_as_base64(self, simple_doc):
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("CreateUser")
        xml = builder.build(op, {"name": b"\x00\x01\x02", "email": "x"}).decode()
        # b"\x00\x01\x02" base64 → "AAEC"
        assert "AAEC" in xml

    def test_datetime_serialized_as_isoformat(self, simple_doc):
        from datetime import datetime
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("CreateUser")
        dt = datetime(2026, 4, 10, 12, 30, 0)
        xml = builder.build(op, {"name": dt, "email": "x"}).decode()
        assert "2026-04-10" in xml

    def test_date_serialized_as_isoformat(self, simple_doc):
        from datetime import date
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("CreateUser")
        d = date(2026, 4, 10)
        xml = builder.build(op, {"name": d, "email": "x"}).decode()
        assert "2026-04-10" in xml

    def test_bool_true_serialized(self, simple_doc):
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("CreateUser")
        xml = builder.build(op, {"name": True, "email": "x"}).decode()
        assert ">true<" in xml

    def test_bool_false_serialized(self, simple_doc):
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("CreateUser")
        xml = builder.build(op, {"name": False, "email": "x"}).decode()
        assert ">false<" in xml

    def test_integer_serialized(self, simple_doc):
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("GetUser")
        xml = builder.build(op, {"userId": 9999}).decode()
        assert "9999" in xml

    def test_float_serialized(self, simple_doc):
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("CreateUser")
        xml = builder.build(op, {"name": 3.14, "email": "x"}).decode()
        assert "3.14" in xml


class TestRepeatingElements:
    """List values on non-xs:list types must produce repeated elements."""

    @pytest.fixture
    def max_occurs_doc(self):
        return WsdlParser().load(str(FIXTURES / "max_occurs.wsdl"))

    def test_list_produces_repeated_elements(self, max_occurs_doc):
        builder = SoapBuilder(max_occurs_doc)
        op = max_occurs_doc.get_operation("CreateOrder")
        xml = builder.build(op, {
            "item": [
                {"sku": "A1", "quantity": 2},
                {"sku": "B3", "quantity": 1},
            ]
        }).decode()
        assert xml.count("<item") == 2

    def test_repeated_element_values(self, max_occurs_doc):
        builder = SoapBuilder(max_occurs_doc)
        op = max_occurs_doc.get_operation("CreateOrder")
        xml = builder.build(op, {
            "item": [{"sku": "X9", "quantity": 5}]
        }).decode()
        assert "X9" in xml
        assert "5" in xml


class TestStrictMode:
    """SerializationError raised for missing required params in strict mode."""

    def test_missing_required_raises_in_strict_mode(self, simple_doc):
        from soapix.exceptions import SerializationError
        builder = SoapBuilder(simple_doc, strict=True)
        op = simple_doc.get_operation("GetUser")
        with pytest.raises(SerializationError):
            builder.build(op, {})  # userId required but missing

    def test_missing_optional_no_error_in_strict_mode(self, simple_doc):
        builder = SoapBuilder(simple_doc, strict=True)
        op = simple_doc.get_operation("GetUser")
        # userId is required, locale is optional → no error if locale omitted
        xml = builder.build(op, {"userId": 1})
        assert xml is not None


class TestXsAttributeBuilder:
    """xs:attribute fields must be serialized as XML attributes, not child elements."""

    @pytest.fixture
    def attr_doc(self):
        return WsdlParser().load(str(FIXTURES / "xs_attribute.wsdl"))

    def test_xs_attribute_token_serialized_as_xml_attribute(self, attr_doc):
        builder = SoapBuilder(attr_doc)
        op = attr_doc.get_operation("Login")
        xml = builder.build(op, {
            "credentials": {"realm": "example.com", "token": "abc123"}
        }).decode()
        # token is xs:attribute → must appear as XML attribute, not child element
        assert 'token="abc123"' in xml

    def test_xs_element_realm_serialized_as_child(self, attr_doc):
        builder = SoapBuilder(attr_doc)
        op = attr_doc.get_operation("Login")
        xml = builder.build(op, {
            "credentials": {"realm": "myrealm", "token": "tok"}
        }).decode()
        assert "<realm>" in xml or ">myrealm<" in xml

    def test_xs_attribute_default_used_when_value_is_none(self, attr_doc):
        # locale has use="optional" default="en"
        # Passing None explicitly → fallback to default value
        builder = SoapBuilder(attr_doc)
        op = attr_doc.get_operation("Login")
        xml = builder.build(op, {
            "credentials": {"token": "tok", "locale": None}
        }).decode()
        # default="en" must be written as XML attribute when value is explicitly None
        assert 'locale="en"' in xml


class TestRpcLiteralBuilder:
    """RPC/literal style — operation wrapper present, no xsi:type annotations."""

    @pytest.fixture
    def rpc_lit_doc(self):
        return WsdlParser().load(str(FIXTURES / "rpc_literal.wsdl"))

    def test_builds_valid_xml(self, rpc_lit_doc):
        builder = SoapBuilder(rpc_lit_doc)
        op = rpc_lit_doc.get_operation("Multiply")
        xml = builder.build(op, {"x": 3, "y": 7})
        from lxml import etree
        assert etree.fromstring(xml) is not None

    def test_operation_element_in_body(self, rpc_lit_doc):
        builder = SoapBuilder(rpc_lit_doc)
        op = rpc_lit_doc.get_operation("Multiply")
        xml = builder.build(op, {"x": 3, "y": 7}).decode()
        assert "Multiply" in xml

    def test_no_xsi_type_annotation(self, rpc_lit_doc):
        builder = SoapBuilder(rpc_lit_doc)
        op = rpc_lit_doc.get_operation("Multiply")
        xml = builder.build(op, {"x": 3, "y": 7}).decode()
        # RPC/literal must NOT add xsi:type
        assert "xsi:type" not in xml

    def test_param_values_present(self, rpc_lit_doc):
        builder = SoapBuilder(rpc_lit_doc)
        op = rpc_lit_doc.get_operation("Multiply")
        xml = builder.build(op, {"x": 6, "y": 9}).decode()
        assert "6" in xml and "9" in xml


class TestAnyTypeBuilder:
    """Unstructured dict on anyType field — serialize as free-form child elements."""

    @pytest.fixture
    def any_doc(self):
        return WsdlParser().load(str(FIXTURES / "any_type.wsdl"))

    def test_anytype_dict_serialized(self, simple_doc):
        # Passing a dict for a primitive-type field (no child fields known) →
        # builder falls through to free-form key/value serialization
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("CreateUser")
        xml = builder.build(op, {
            "name": {"first": "Ahmet", "last": "Yilmaz"},
            "email": "x"
        }).decode()
        assert "first" in xml
        assert "Ahmet" in xml

    def test_base64_content_type_dict(self, simple_doc):
        # {"value": bytes, "contentType": "..."} → xmlmime:contentType attribute
        builder = SoapBuilder(simple_doc)
        op = simple_doc.get_operation("CreateUser")
        xml = builder.build(op, {
            "name": {"value": b"\x00\xFF", "contentType": "application/octet-stream"},
            "email": "x"
        }).decode()
        assert "contentType" in xml
        assert "application/octet-stream" in xml
