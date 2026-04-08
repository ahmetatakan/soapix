"""Tests for exception hierarchy and formatting."""

from __future__ import annotations

import pytest

from soapix.exceptions import (
    HttpError,
    SerializationError,
    SoapCallError,
    SoapFaultError,
    SoapixError,
    TimeoutError,
    WsdlImportError,
    WsdlNotFoundError,
    WsdlParseError,
)


class TestExceptionHierarchy:
    def test_wsdl_not_found_is_parse_error(self):
        assert issubclass(WsdlNotFoundError, WsdlParseError)

    def test_wsdl_import_is_parse_error(self):
        assert issubclass(WsdlImportError, WsdlParseError)

    def test_wsdl_parse_is_soapix(self):
        assert issubclass(WsdlParseError, SoapixError)

    def test_soap_call_is_soapix(self):
        assert issubclass(SoapCallError, SoapixError)

    def test_soap_fault_is_call_error(self):
        assert issubclass(SoapFaultError, SoapCallError)

    def test_http_error_is_call_error(self):
        assert issubclass(HttpError, SoapCallError)

    def test_timeout_is_call_error(self):
        assert issubclass(TimeoutError, SoapCallError)

    def test_serialization_is_soapix(self):
        assert issubclass(SerializationError, SoapixError)


class TestSoapCallErrorFormatting:
    def test_includes_service(self):
        err = SoapCallError("Test error", service="UserService")
        assert "UserService" in str(err)

    def test_includes_method(self):
        err = SoapCallError("Test error", method="GetUser")
        assert "GetUser" in str(err)

    def test_includes_endpoint(self):
        err = SoapCallError("Test error", endpoint="http://example.com")
        assert "http://example.com" in str(err)

    def test_includes_hint(self):
        err = SoapCallError("Test error", hint="userId is a required field")
        assert "userId is a required field" in str(err)

    def test_all_fields(self):
        err = SoapCallError(
            "Call failed",
            service="UserService",
            method="GetUser",
            endpoint="http://example.com",
            hint="userId must be an int",
        )
        msg = str(err)
        assert "UserService" in msg
        assert "GetUser" in msg
        assert "http://example.com" in msg
        assert "userId must be an int" in msg


class TestSoapFaultError:
    def test_fault_attributes(self):
        err = SoapFaultError(
            fault_code="Server",
            fault_string="Internal error",
        )
        assert err.fault_code == "Server"
        assert err.fault_string == "Internal error"

    def test_fault_with_detail(self):
        err = SoapFaultError(
            fault_code="Server",
            fault_string="Error",
            detail="<detail>NullRef</detail>",
        )
        assert err.detail == "<detail>NullRef</detail>"

    def test_is_catchable_as_soap_call_error(self):
        err = SoapFaultError(fault_code="Server", fault_string="Error")
        assert isinstance(err, SoapCallError)
