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


class TestElementRef:
    """Bug 1: xs:element ref="..." — referenced elements must appear as fields."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "element_ref.wsdl"))
        assert "GetPerson" in doc.operations

    def test_ref_field_appears_in_input(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "element_ref.wsdl"))
        op = doc.get_operation("GetPerson")
        fields = resolve_input_fields(op, doc)
        assert any(f.name == "sharedId" for f in fields)

    def test_ref_fields_appear_in_output(self, parser):
        from soapix.docs.resolver import resolve_output_fields
        doc = parser.load(str(FIXTURES / "element_ref.wsdl"))
        op = doc.get_operation("GetPerson")
        fields = resolve_output_fields(op, doc)
        field_names = [f.name for f in fields]
        assert "sharedId" in field_names
        assert "sharedName" in field_names
        assert "email" in field_names


class TestTypeExtension:
    """Bug 2: xs:extension base="..." — inherited fields must be included."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "type_extension.wsdl"))
        assert "GetUser" in doc.operations

    def test_own_fields_present(self, parser):
        from soapix.docs.resolver import resolve_output_fields
        doc = parser.load(str(FIXTURES / "type_extension.wsdl"))
        op = doc.get_operation("GetUser")
        fields = resolve_output_fields(op, doc)
        field_names = [f.name for f in fields]
        assert "name" in field_names
        assert "email" in field_names

    def test_inherited_fields_present(self, parser):
        from soapix.docs.resolver import resolve_output_fields
        doc = parser.load(str(FIXTURES / "type_extension.wsdl"))
        op = doc.get_operation("GetUser")
        fields = resolve_output_fields(op, doc)
        field_names = [f.name for f in fields]
        assert "id" in field_names
        assert "createdAt" in field_names

    def test_inherited_fields_come_first(self, parser):
        from soapix.docs.resolver import resolve_output_fields
        doc = parser.load(str(FIXTURES / "type_extension.wsdl"))
        op = doc.get_operation("GetUser")
        fields = resolve_output_fields(op, doc)
        names = [f.name for f in fields]
        assert names.index("id") < names.index("name")


class TestNamedGroups:
    """Bug 3: xs:group ref="..." — named model group fields must be included."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "named_groups.wsdl"))
        assert "GetEmployee" in doc.operations

    def test_group_fields_present(self, parser):
        from soapix.docs.resolver import resolve_output_fields
        doc = parser.load(str(FIXTURES / "named_groups.wsdl"))
        op = doc.get_operation("GetEmployee")
        fields = resolve_output_fields(op, doc)
        field_names = [f.name for f in fields]
        assert "firstName" in field_names
        assert "lastName" in field_names

    def test_non_group_fields_present(self, parser):
        from soapix.docs.resolver import resolve_output_fields
        doc = parser.load(str(FIXTURES / "named_groups.wsdl"))
        op = doc.get_operation("GetEmployee")
        fields = resolve_output_fields(op, doc)
        field_names = [f.name for f in fields]
        assert "employeeId" in field_names
        assert "department" in field_names


class TestNoServiceElement:
    """Bug 5: WSDL without wsdl:service — operations must still be discoverable."""

    def test_operations_found_without_service(self, parser):
        doc = parser.load(str(FIXTURES / "no_service.wsdl"))
        assert "Ping" in doc.operations

    def test_service_list_is_empty(self, parser):
        doc = parser.load(str(FIXTURES / "no_service.wsdl"))
        assert doc.services == []

    def test_endpoint_is_empty_string(self, parser):
        doc = parser.load(str(FIXTURES / "no_service.wsdl"))
        assert doc.endpoint == ""

    def test_operation_has_input_params(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "no_service.wsdl"))
        op = doc.get_operation("Ping")
        fields = resolve_input_fields(op, doc)
        assert any(f.name == "message" for f in fields)


class TestGibEFatura:
    """GIB eFatura style: elements reference named complexTypes (no inline types)."""

    def test_loads_without_error(self, parser):
        doc = parser.load(str(FIXTURES / "gib_efatura.wsdl"))
        assert doc is not None

    def test_service_name(self, parser):
        doc = parser.load(str(FIXTURES / "gib_efatura.wsdl"))
        assert doc.service_name == "EFatura"

    def test_operations_discovered(self, parser):
        doc = parser.load(str(FIXTURES / "gib_efatura.wsdl"))
        assert "sendDocument" in doc.operations
        assert "getAddressInfo" in doc.operations

    def test_send_document_input_params_resolved(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "gib_efatura.wsdl"))
        op = doc.get_operation("sendDocument")
        fields = resolve_input_fields(op, doc)
        field_names = [f.name for f in fields]
        assert "fileName" in field_names
        assert "binaryData" in field_names
        assert "hash" in field_names

    def test_send_document_output_params_resolved(self, parser):
        from soapix.docs.resolver import resolve_output_fields
        doc = parser.load(str(FIXTURES / "gib_efatura.wsdl"))
        op = doc.get_operation("sendDocument")
        fields = resolve_output_fields(op, doc)
        field_names = [f.name for f in fields]
        assert "msg" in field_names
        assert "httpStatus" in field_names

    def test_get_address_info_params_resolved(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "gib_efatura.wsdl"))
        op = doc.get_operation("getAddressInfo")
        fields = resolve_input_fields(op, doc)
        assert any(f.name == "identifier" for f in fields)

    def test_endpoint_present(self, parser):
        doc = parser.load(str(FIXTURES / "gib_efatura.wsdl"))
        assert "efatura.example.com" in doc.endpoint


class TestXsAttribute:
    """xs:attribute fields must be included alongside xs:element fields."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "xs_attribute.wsdl"))
        assert "Login" in doc.operations

    def test_credentials_field_present(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "xs_attribute.wsdl"))
        op = doc.get_operation("Login")
        fields = resolve_input_fields(op, doc)
        assert any(f.name == "credentials" for f in fields)

    def test_attribute_fields_in_type(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "xs_attribute.wsdl"))
        fields = get_type_fields("Credentials", doc)
        field_names = [f.name for f in fields]
        assert "realm" in field_names    # xs:element
        assert "token" in field_names    # xs:attribute required
        assert "locale" in field_names   # xs:attribute optional

    def test_required_attribute(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "xs_attribute.wsdl"))
        fields = get_type_fields("Credentials", doc)
        token = next(f for f in fields if f.name == "token")
        assert token.required is True

    def test_optional_attribute(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "xs_attribute.wsdl"))
        fields = get_type_fields("Credentials", doc)
        locale = next(f for f in fields if f.name == "locale")
        assert locale.required is False


class TestAttributeGroup:
    """xs:attributeGroup ref must expand to its attribute fields."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "attribute_group.wsdl"))
        assert "Do" in doc.operations

    def test_attribute_group_fields_in_type(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "attribute_group.wsdl"))
        fields = get_type_fields("RequestType", doc)
        field_names = [f.name for f in fields]
        assert "body" in field_names      # xs:element
        assert "lang" in field_names      # from attributeGroup
        assert "version" in field_names   # from attributeGroup

    def test_required_from_attribute_group(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "attribute_group.wsdl"))
        fields = get_type_fields("RequestType", doc)
        version = next(f for f in fields if f.name == "version")
        assert version.required is True


class TestRestrictionBase:
    """xs:restriction must still expose base type fields."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "restriction_base.wsdl"))
        assert "Get" in doc.operations

    def test_restriction_fields_present(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "restriction_base.wsdl"))
        fields = get_type_fields("LimitedEntity", doc)
        field_names = [f.name for f in fields]
        assert "id" in field_names
        assert "name" in field_names


class TestFaultMessage:
    """wsdl:fault messages must be parsed and stored in fault_params."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "fault_message.wsdl"))
        assert "GetUser" in doc.operations

    def test_fault_name_present(self, parser):
        doc = parser.load(str(FIXTURES / "fault_message.wsdl"))
        op = doc.get_operation("GetUser")
        assert "ServiceError" in op.fault_params

    def test_fault_params_resolved(self, parser):
        doc = parser.load(str(FIXTURES / "fault_message.wsdl"))
        op = doc.get_operation("GetUser")
        fault = op.fault_params["ServiceError"]
        assert len(fault) > 0
