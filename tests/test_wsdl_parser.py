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


class TestXsChoice:
    """xs:choice — fields from a choice group must all be discoverable."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "xs_choice.wsdl"))
        assert "Search" in doc.operations

    def test_choice_type_registered(self, parser):
        doc = parser.load(str(FIXTURES / "xs_choice.wsdl"))
        assert any("SearchCriteria" in k for k in doc.types)

    def test_choice_fields_present(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "xs_choice.wsdl"))
        fields = get_type_fields("SearchCriteria", doc)
        field_names = [f.name for f in fields]
        assert "userId" in field_names
        assert "email" in field_names

    def test_optional_field_in_choice(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "xs_choice.wsdl"))
        fields = get_type_fields("SearchCriteria", doc)
        locale = next((f for f in fields if f.name == "locale"), None)
        assert locale is not None
        assert locale.required is False

    def test_input_includes_criteria_param(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "xs_choice.wsdl"))
        op = doc.get_operation("Search")
        fields = resolve_input_fields(op, doc)
        assert any(f.name == "criteria" for f in fields)


class TestXsAll:
    """xs:all — all fields must be discoverable regardless of ordering."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "xs_all.wsdl"))
        assert "UpdateProfile" in doc.operations

    def test_all_type_registered(self, parser):
        doc = parser.load(str(FIXTURES / "xs_all.wsdl"))
        assert any("Profile" in k for k in doc.types)

    def test_all_fields_present(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "xs_all.wsdl"))
        fields = get_type_fields("Profile", doc)
        field_names = [f.name for f in fields]
        assert "firstName" in field_names
        assert "lastName" in field_names

    def test_optional_field_in_all(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "xs_all.wsdl"))
        fields = get_type_fields("Profile", doc)
        bio = next((f for f in fields if f.name == "bio"), None)
        assert bio is not None
        assert bio.required is False


class TestMaxOccurs:
    """maxOccurs="unbounded" elements must be detected as list-typed."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "max_occurs.wsdl"))
        assert "CreateOrder" in doc.operations

    def test_unbounded_field_is_list(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "max_occurs.wsdl"))
        op = doc.get_operation("CreateOrder")
        fields = resolve_input_fields(op, doc)
        item = next(f for f in fields if f.name == "item")
        assert item.is_list is True

    def test_unbounded_field_max_occurs_none(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "max_occurs.wsdl"))
        op = doc.get_operation("CreateOrder")
        fields = resolve_input_fields(op, doc)
        item = next(f for f in fields if f.name == "item")
        assert item.max_occurs is None  # None = unbounded

    def test_optional_unbounded_field(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "max_occurs.wsdl"))
        op = doc.get_operation("CreateOrder")
        fields = resolve_input_fields(op, doc)
        tag = next(f for f in fields if f.name == "tag")
        assert tag.is_list is True
        assert tag.required is False


class TestRpcStyle:
    """RPC-style binding — style and use must be correctly detected."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "rpc_encoded.wsdl"))
        assert "Add" in doc.operations

    def test_style_is_rpc(self, parser):
        doc = parser.load(str(FIXTURES / "rpc_encoded.wsdl"))
        op = doc.get_operation("Add")
        assert op.style == BindingStyle.RPC

    def test_use_is_encoded(self, parser):
        from soapix.wsdl.types import ParameterUse
        doc = parser.load(str(FIXTURES / "rpc_encoded.wsdl"))
        op = doc.get_operation("Add")
        assert op.use == ParameterUse.ENCODED

    def test_input_params_from_message_parts(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "rpc_encoded.wsdl"))
        op = doc.get_operation("Add")
        fields = resolve_input_fields(op, doc)
        field_names = [f.name for f in fields]
        assert "a" in field_names
        assert "b" in field_names


class TestXsList:
    """xs:list simple type — detected as list kind with correct item_type."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "xs_list.wsdl"))
        assert "SetTags" in doc.operations

    def test_list_type_registered(self, parser):
        doc = parser.load(str(FIXTURES / "xs_list.wsdl"))
        assert any("IntList" in k for k in doc.types)

    def test_list_type_kind(self, parser):
        doc = parser.load(str(FIXTURES / "xs_list.wsdl"))
        key = next(k for k in doc.types if "IntList" in k)
        assert doc.types[key].kind == "list"

    def test_list_type_item_type(self, parser):
        doc = parser.load(str(FIXTURES / "xs_list.wsdl"))
        key = next(k for k in doc.types if "IntList" in k)
        assert doc.types[key].item_type == "int"

    def test_ids_field_uses_list_type(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "xs_list.wsdl"))
        op = doc.get_operation("SetTags")
        fields = resolve_input_fields(op, doc)
        ids = next(f for f in fields if f.name == "ids")
        assert ids.type_name.endswith("IntList") or ids.type_name == "IntList"


class TestNamedSimpleType:
    """Named simpleType with xs:restriction must be registered as kind='simple'."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "named_simple_type.wsdl"))
        assert "GetStatus" in doc.operations

    def test_simple_type_registered(self, parser):
        doc = parser.load(str(FIXTURES / "named_simple_type.wsdl"))
        assert any("StatusCode" in k for k in doc.types)

    def test_simple_type_kind(self, parser):
        doc = parser.load(str(FIXTURES / "named_simple_type.wsdl"))
        key = next(k for k in doc.types if "StatusCode" in k)
        assert doc.types[key].kind == "simple"

    def test_simple_type_base_type(self, parser):
        doc = parser.load(str(FIXTURES / "named_simple_type.wsdl"))
        key = next(k for k in doc.types if "StatusCode" in k)
        assert doc.types[key].base_type == "string"

    def test_second_simple_type_registered(self, parser):
        doc = parser.load(str(FIXTURES / "named_simple_type.wsdl"))
        assert any("ShortId" in k for k in doc.types)

    def test_simple_type_field_in_input(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "named_simple_type.wsdl"))
        op = doc.get_operation("GetStatus")
        fields = resolve_input_fields(op, doc)
        assert any(f.name == "filter" for f in fields)


class TestAnyAttribute:
    """xs:anyAttribute in a complex type must register a _anyAttribute sentinel field."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "any_attribute.wsdl"))
        assert "Process" in doc.operations

    def test_any_attribute_field_registered(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "any_attribute.wsdl"))
        fields = get_type_fields("ExtensibleRequest", doc)
        assert any(f.name == "_anyAttribute" for f in fields)

    def test_any_attribute_is_optional(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "any_attribute.wsdl"))
        fields = get_type_fields("ExtensibleRequest", doc)
        attr_field = next(f for f in fields if f.name == "_anyAttribute")
        assert attr_field.required is False

    def test_regular_field_also_present(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "any_attribute.wsdl"))
        fields = get_type_fields("ExtensibleRequest", doc)
        assert any(f.name == "payload" for f in fields)


class TestNillable:
    """nillable="true" elements must be treated as not-required."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "nillable.wsdl"))
        assert "CreateRecord" in doc.operations

    def test_nillable_element_not_required(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "nillable.wsdl"))
        op = doc.get_operation("CreateRecord")
        fields = resolve_input_fields(op, doc)
        notes = next(f for f in fields if f.name == "notes")
        assert notes.required is False

    def test_non_nillable_required(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "nillable.wsdl"))
        op = doc.get_operation("CreateRecord")
        fields = resolve_input_fields(op, doc)
        title = next(f for f in fields if f.name == "title")
        assert title.required is True

    def test_min_occurs_zero_still_optional(self, parser):
        from soapix.docs.resolver import resolve_input_fields
        doc = parser.load(str(FIXTURES / "nillable.wsdl"))
        op = doc.get_operation("CreateRecord")
        fields = resolve_input_fields(op, doc)
        tags = next(f for f in fields if f.name == "tags")
        assert tags.required is False


class TestNoTypes:
    """WSDL without a <types> section must load without error."""

    def test_loads_without_error(self, parser):
        doc = parser.load(str(FIXTURES / "no_types.wsdl"))
        assert doc is not None

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "no_types.wsdl"))
        assert "Ping" in doc.operations

    def test_types_dict_empty(self, parser):
        doc = parser.load(str(FIXTURES / "no_types.wsdl"))
        assert doc.types == {}


class TestInlineAnonymousComplexType:
    """Element with inline anonymous complexType → type_name uses element name."""

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "inline_anonymous.wsdl"))
        assert "Ship" in doc.operations

    def test_ship_order_type_registered(self, parser):
        doc = parser.load(str(FIXTURES / "inline_anonymous.wsdl"))
        assert any("ShipOrder" in k for k in doc.types)

    def test_inline_address_field_type_name(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "inline_anonymous.wsdl"))
        fields = get_type_fields("ShipOrder", doc)
        address = next((f for f in fields if f.name == "address"), None)
        assert address is not None
        # Inline anonymous complexType → type_name equals element name
        assert address.type_name == "address"

    def test_no_type_no_inline_falls_back_to_any_type(self, parser):
        from soapix.docs.resolver import get_type_fields
        doc = parser.load(str(FIXTURES / "inline_anonymous.wsdl"))
        fields = get_type_fields("ShipOrder", doc)
        metadata = next((f for f in fields if f.name == "metadata"), None)
        assert metadata is not None
        assert metadata.type_name == "anyType"


class TestRestrictionBase:
    """_get_restriction_base extracts base type from xs:restriction."""

    def test_restriction_base_with_namespace_prefix(self, parser):
        # xsd:string → strips prefix → "string"
        doc = parser.load(str(FIXTURES / "named_simple_type.wsdl"))
        key = next(k for k in doc.types if "StatusCode" in k)
        assert doc.types[key].base_type == "string"

    def test_restriction_base_int(self, parser):
        doc = parser.load(str(FIXTURES / "named_simple_type.wsdl"))
        key = next(k for k in doc.types if "ShortId" in k)
        assert doc.types[key].base_type == "int"

    def test_restriction_base_none_when_no_restriction(self, parser):
        # xs:list type has no restriction → _get_restriction_base returns None
        doc = parser.load(str(FIXTURES / "xs_list.wsdl"))
        key = next(k for k in doc.types if "IntList" in k)
        # IntList is xs:list, not xs:restriction — base_type should be None
        assert doc.types[key].base_type is None


class TestAsyncLoad:
    """load_async must parse the same result as load for local files."""

    def test_load_async_file(self):
        import asyncio
        async def _run():
            parser = WsdlParser()
            doc = await parser.load_async(str(FIXTURES / "simple.wsdl"))
            return doc
        doc = asyncio.run(_run())
        assert "GetUser" in doc.operations

    def test_load_async_target_namespace(self):
        import asyncio
        async def _run():
            parser = WsdlParser()
            return await parser.load_async(str(FIXTURES / "simple.wsdl"))
        doc = asyncio.run(_run())
        assert doc.target_namespace == "http://example.com/userservice"

    def test_load_async_invalid_xml(self, tmp_path):
        import asyncio
        from soapix.exceptions import WsdlNotFoundError
        bad = tmp_path / "bad.wsdl"
        bad.write_text("not xml <<<")
        async def _run():
            return await WsdlParser().load_async(str(bad))
        with pytest.raises(WsdlNotFoundError):
            asyncio.run(_run())


class TestSafeInt:
    """_safe_int helper must handle invalid and empty values gracefully."""

    def test_valid_integer(self):
        from soapix.wsdl.parser import _safe_int
        assert _safe_int("5", 1) == 5

    def test_empty_string_returns_default(self):
        from soapix.wsdl.parser import _safe_int
        assert _safe_int("", 1) == 1

    def test_none_returns_default(self):
        from soapix.wsdl.parser import _safe_int
        assert _safe_int(None, 99) == 99

    def test_non_integer_string_returns_default(self):
        from soapix.wsdl.parser import _safe_int
        assert _safe_int("unbounded", 1) == 1

    def test_whitespace_only_returns_default(self):
        from soapix.wsdl.parser import _safe_int
        assert _safe_int("   ", 0) == 0

    def test_negative_integer(self):
        from soapix.wsdl.parser import _safe_int
        assert _safe_int("-1", 0) == -1


class TestHttpAddress:
    """Port with non-SOAP address element — fallback address lookup must work."""

    def test_loads_without_error(self, parser):
        doc = parser.load(str(FIXTURES / "http_address.wsdl"))
        assert doc is not None

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "http_address.wsdl"))
        assert "GetVersion" in doc.operations

    def test_endpoint_resolved_from_http_address(self, parser):
        doc = parser.load(str(FIXTURES / "http_address.wsdl"))
        assert "legacy.example.com" in doc.endpoint


class TestDuplicatePort:
    """Two ports with same binding — operations registered only once (first wins)."""

    def test_loads_without_error(self, parser):
        doc = parser.load(str(FIXTURES / "duplicate_port.wsdl"))
        assert doc is not None

    def test_operation_registered_once(self, parser):
        doc = parser.load(str(FIXTURES / "duplicate_port.wsdl"))
        assert "Ping" in doc.operations
        # dict has no duplicates by definition — verify it's exactly once
        ping_count = sum(1 for k in doc.operations if k == "Ping")
        assert ping_count == 1

    def test_first_endpoint_wins(self, parser):
        doc = parser.load(str(FIXTURES / "duplicate_port.wsdl"))
        op = doc.get_operation("Ping")
        assert "primary.example.com" in op.endpoint

    def test_two_services_registered(self, parser):
        doc = parser.load(str(FIXTURES / "duplicate_port.wsdl"))
        # Both ports create service entries
        assert len(doc.services) == 2


class TestRestrictionNoPrefix:
    """xs:restriction base without namespace prefix and xs:union (no restriction)."""

    def test_loads_without_error(self, parser):
        doc = parser.load(str(FIXTURES / "restriction_no_prefix.wsdl"))
        assert doc is not None

    def test_restriction_base_no_prefix(self, parser):
        doc = parser.load(str(FIXTURES / "restriction_no_prefix.wsdl"))
        key = next(k for k in doc.types if "CountryCode" in k)
        # base="string" (no prefix) → base_type should be "string"
        assert doc.types[key].base_type == "string"

    def test_union_type_base_is_none(self, parser):
        doc = parser.load(str(FIXTURES / "restriction_no_prefix.wsdl"))
        key = next(k for k in doc.types if "AnyCode" in k)
        # xs:union has no xs:restriction → _get_restriction_base returns None
        assert doc.types[key].base_type is None

    def test_operation_found(self, parser):
        doc = parser.load(str(FIXTURES / "restriction_no_prefix.wsdl"))
        assert "GetCode" in doc.operations


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
