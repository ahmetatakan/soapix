"""Tests for tolerant namespace normalization."""

from __future__ import annotations

import pytest

from soapix.wsdl.namespace import (
    localname,
    namespace_of,
    namespaces_match,
    normalize_namespace,
    clark,
)


class TestNormalizeNamespace:
    def test_strips_trailing_slash(self):
        assert normalize_namespace("http://example.com/v1/") == "http://example.com/v1"

    def test_multiple_trailing_slashes(self):
        assert normalize_namespace("http://example.com/v1///") == "http://example.com/v1"

    def test_lowercases(self):
        assert normalize_namespace("HTTP://Example.COM/V1") == "http://example.com/v1"

    def test_removes_fragment(self):
        assert normalize_namespace("http://example.com/v1#types") == "http://example.com/v1"

    def test_strips_whitespace(self):
        assert normalize_namespace("  http://example.com/v1  ") == "http://example.com/v1"

    def test_empty_string(self):
        assert normalize_namespace("") == ""

    def test_no_change_needed(self):
        assert normalize_namespace("http://example.com/v1") == "http://example.com/v1"


class TestNamespacesMatch:
    def test_identical(self):
        assert namespaces_match("http://example.com/v1", "http://example.com/v1")

    def test_trailing_slash(self):
        assert namespaces_match("http://example.com/v1/", "http://example.com/v1")

    def test_case_insensitive(self):
        assert namespaces_match("HTTP://Example.COM/v1", "http://example.com/v1")

    def test_fragment_ignored(self):
        assert namespaces_match("http://example.com/v1#foo", "http://example.com/v1")

    def test_different_namespaces(self):
        assert not namespaces_match("http://example.com/v1", "http://example.com/v2")


class TestClarkNotation:
    def test_localname_with_ns(self):
        assert localname("{http://example.com}Foo") == "Foo"

    def test_localname_without_ns(self):
        assert localname("Foo") == "Foo"

    def test_namespace_of_with_ns(self):
        assert namespace_of("{http://example.com}Foo") == "http://example.com"

    def test_namespace_of_without_ns(self):
        assert namespace_of("Foo") == ""

    def test_clark_builds_tag(self):
        assert clark("http://example.com", "Foo") == "{http://example.com}Foo"

    def test_clark_empty_ns(self):
        assert clark("", "Foo") == "Foo"
