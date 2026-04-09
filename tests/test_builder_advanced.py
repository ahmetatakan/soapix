"""
Tests for advanced builder features:
- RPC/encoded style with xsi:type annotations
- xs:list space-separated serialization
"""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from soapix.wsdl.parser import WsdlParser
from soapix.xml.builder import SoapBuilder

FIXTURES = Path(__file__).parent / "fixtures"

NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"


# ---------------------------------------------------------------------------
# RPC / encoded
# ---------------------------------------------------------------------------

class TestRpcEncodedBuilder:
    @pytest.fixture
    def rpc_doc(self):
        return WsdlParser().load(str(FIXTURES / "rpc_encoded.wsdl"))

    def test_rpc_style_detected(self, rpc_doc):
        from soapix.wsdl.types import BindingStyle
        op = rpc_doc.get_operation("Add")
        assert op.style == BindingStyle.RPC

    def test_encoded_use_detected(self, rpc_doc):
        from soapix.wsdl.types import ParameterUse
        op = rpc_doc.get_operation("Add")
        assert op.use == ParameterUse.ENCODED

    def test_rpc_encoded_builds_valid_xml(self, rpc_doc):
        builder = SoapBuilder(rpc_doc)
        op = rpc_doc.get_operation("Add")
        xml = builder.build(op, {"a": 3, "b": 7})
        root = etree.fromstring(xml)
        assert root is not None

    def test_rpc_encoded_has_xsi_type(self, rpc_doc):
        builder = SoapBuilder(rpc_doc)
        op = rpc_doc.get_operation("Add")
        xml = builder.build(op, {"a": 3, "b": 7}).decode()
        # xsi:type annotations must be present in RPC/encoded
        assert "xsi:type" in xml or f"{{{NS_XSI}}}type" in xml or "type=" in xml

    def test_rpc_encoded_values_present(self, rpc_doc):
        builder = SoapBuilder(rpc_doc)
        op = rpc_doc.get_operation("Add")
        xml = builder.build(op, {"a": 42, "b": 8}).decode()
        assert "42" in xml
        assert "8" in xml

    def test_rpc_encoded_operation_element_in_body(self, rpc_doc):
        builder = SoapBuilder(rpc_doc)
        op = rpc_doc.get_operation("Add")
        xml = builder.build(op, {"a": 1, "b": 2}).decode()
        # The operation element must appear in the Body
        assert "Add" in xml

    def test_rpc_encoded_nil_for_none_param(self, rpc_doc):
        builder = SoapBuilder(rpc_doc)
        op = rpc_doc.get_operation("Add")
        xml = builder.build(op, {"a": None, "b": 5}).decode()
        assert "nil" in xml


# ---------------------------------------------------------------------------
# xs:list — space-separated serialization
# ---------------------------------------------------------------------------

class TestXsListBuilder:
    @pytest.fixture
    def list_doc(self):
        return WsdlParser().load(str(FIXTURES / "xs_list.wsdl"))

    def test_xs_list_type_parsed(self, list_doc):
        # IntList type should be present with kind="list"
        matched = [t for t in list_doc.types.values() if t.name == "IntList"]
        assert matched, "IntList type not found in parsed types"
        assert matched[0].kind == "list"

    def test_xs_list_serialized_space_separated(self, list_doc):
        builder = SoapBuilder(list_doc)
        op = list_doc.get_operation("SetTags")
        xml = builder.build(op, {"ids": [1, 2, 3]}).decode()
        assert "1 2 3" in xml

    def test_xs_list_single_value(self, list_doc):
        builder = SoapBuilder(list_doc)
        op = list_doc.get_operation("SetTags")
        xml = builder.build(op, {"ids": [99]}).decode()
        assert "99" in xml
        # Must NOT have duplicate <ids> elements
        assert xml.count("<ids") == 1

    def test_xs_list_empty_list(self, list_doc):
        builder = SoapBuilder(list_doc)
        op = list_doc.get_operation("SetTags")
        xml = builder.build(op, {"ids": []}).decode()
        # Empty list → element with empty text content
        assert "<ids" in xml
