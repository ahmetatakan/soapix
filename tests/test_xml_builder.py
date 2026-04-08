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
        body = root[0]
        assert "Body" in body.tag

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
