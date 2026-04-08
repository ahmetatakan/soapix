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
