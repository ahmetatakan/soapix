"""Tests for WSDL parser — no real network calls, fixtures only."""

from __future__ import annotations

from pathlib import Path

import pytest

from soapix.wsdl.parser import WsdlParser
from soapix.wsdl.types import BindingStyle, SoapVersion
from soapix.exceptions import WsdlNotFoundError, SoapCallError

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def parser() -> WsdlParser:
    return WsdlParser(strict=False)


class TestSimpleWsdl:
    def test_loads_without_error(self, parser):
        doc = parser.load(str(FIXTURES / "simple.wsdl"))
        assert doc is not None

    def test_target_namespace(self, parser):
        doc = parser.load(str(FIXTURES / "simple.wsdl"))
        assert doc.target_namespace == "http://example.com/userservice"

    def test_service_name(self, parser):
        doc = parser.load(str(FIXTURES / "simple.wsdl"))
        assert doc.service_name == "UserService"

    def test_endpoint(self, parser):
        doc = parser.load(str(FIXTURES / "simple.wsdl"))
        assert doc.endpoint == "http://example.com/userservice"

    def test_operations_discovered(self, parser):
        doc = parser.load(str(FIXTURES / "simple.wsdl"))
        assert "GetUser" in doc.operations
        assert "CreateUser" in doc.operations

    def test_operation_soap_action(self, parser):
        doc = parser.load(str(FIXTURES / "simple.wsdl"))
        op = doc.operations["GetUser"]
        assert op.soap_action == "http://example.com/userservice/GetUser"

    def test_operation_style_document(self, parser):
        doc = parser.load(str(FIXTURES / "simple.wsdl"))
        op = doc.operations["GetUser"]
        assert op.style == BindingStyle.DOCUMENT

    def test_operation_soap_version_11(self, parser):
        doc = parser.load(str(FIXTURES / "simple.wsdl"))
        assert doc.soap_version == SoapVersion.SOAP_11

    def test_operation_documentation(self, parser):
        doc = parser.load(str(FIXTURES / "simple.wsdl"))
        op = doc.operations["GetUser"]
        assert "ID" in op.documentation

    def test_get_operation_success(self, parser):
        doc = parser.load(str(FIXTURES / "simple.wsdl"))
        op = doc.get_operation("GetUser")
        assert op.name == "GetUser"

    def test_get_operation_not_found(self, parser):
        doc = parser.load(str(FIXTURES / "simple.wsdl"))
        with pytest.raises(SoapCallError, match="is not defined"):
            doc.get_operation("NonExistentMethod")

    def test_get_operation_error_lists_available(self, parser):
        doc = parser.load(str(FIXTURES / "simple.wsdl"))
        with pytest.raises(SoapCallError) as exc_info:
            doc.get_operation("NonExistentMethod")
        assert "GetUser" in str(exc_info.value)


class TestNamespaceQuirks:
    def test_loads_trailing_slash_namespace(self, parser):
        doc = parser.load(str(FIXTURES / "namespace_quirks.wsdl"))
        assert doc is not None

    def test_ping_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "namespace_quirks.wsdl"))
        assert "Ping" in doc.operations

    def test_endpoint_with_trailing_slash(self, parser):
        doc = parser.load(str(FIXTURES / "namespace_quirks.wsdl"))
        assert doc.endpoint == "http://quirky.example.com/service/"


class TestSoap12:
    def test_detects_soap_12(self, parser):
        doc = parser.load(str(FIXTURES / "soap12.wsdl"))
        assert doc.soap_version == SoapVersion.SOAP_12

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "soap12.wsdl"))
        assert "GetOrder" in doc.operations


class TestErrorHandling:
    def test_file_not_found(self, parser):
        with pytest.raises(WsdlNotFoundError):
            parser.load("/nonexistent/path/service.wsdl")

    def test_invalid_xml(self, parser, tmp_path):
        bad_file = tmp_path / "bad.wsdl"
        bad_file.write_text("this is not xml at all <<<")
        with pytest.raises(WsdlNotFoundError, match="is not valid XML"):
            parser.load(str(bad_file))
