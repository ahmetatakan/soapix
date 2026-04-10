"""Tests for wsdl/resolver.py — load_xml, _make_ssl_context, ImportResolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from soapix.wsdl.resolver import (
    ImportResolver,
    _is_url,
    _make_ssl_context,
    _resolve_location,
    load_xml,
)
from soapix.exceptions import WsdlNotFoundError, WsdlImportError

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# _make_ssl_context
# ---------------------------------------------------------------------------

class TestMakeSslContext:
    def test_verify_true_returns_none(self):
        ctx = _make_ssl_context(True)
        assert ctx is None

    def test_verify_false_disables_verification(self):
        import ssl
        ctx = _make_ssl_context(False)
        assert ctx is not None
        assert ctx.verify_mode == ssl.CERT_NONE
        assert ctx.check_hostname is False

    def test_verify_string_uses_cafile(self, tmp_path):
        import ssl
        # ssl.create_default_context(cafile=...) requires a valid PEM file
        # Use the system CA bundle if available, otherwise skip
        import sys
        cafile = None
        if sys.platform == "darwin":
            import subprocess
            result = subprocess.run(
                ["security", "find-certificate", "-a", "-p", "/System/Library/Keychains/SystemRootCertificates.keychain"],
                capture_output=True, timeout=5
            )
            if result.returncode == 0 and result.stdout:
                pem_file = tmp_path / "ca.pem"
                pem_file.write_bytes(result.stdout)
                cafile = str(pem_file)
        if cafile is None:
            pytest.skip("No system CA bundle available for this test")
        ctx = _make_ssl_context(cafile)
        assert ctx is not None
        assert isinstance(ctx, ssl.SSLContext)


# ---------------------------------------------------------------------------
# _is_url
# ---------------------------------------------------------------------------

class TestIsUrl:
    def test_http_is_url(self):
        assert _is_url("http://example.com/service.wsdl") is True

    def test_https_is_url(self):
        assert _is_url("https://example.com/service.wsdl") is True

    def test_ftp_is_url(self):
        assert _is_url("ftp://example.com/file.xsd") is True

    def test_file_path_not_url(self):
        assert _is_url("/path/to/file.wsdl") is False

    def test_relative_path_not_url(self):
        assert _is_url("service.wsdl") is False

    def test_windows_path_not_url(self):
        assert _is_url("C:\\service.wsdl") is False


# ---------------------------------------------------------------------------
# _resolve_location
# ---------------------------------------------------------------------------

class TestResolveLocation:
    def test_absolute_url_unchanged(self):
        result = _resolve_location("http://base.example.com/", "http://other.example.com/types.xsd")
        assert result == "http://other.example.com/types.xsd"

    def test_relative_against_url_base(self):
        result = _resolve_location("http://example.com/wsdl/service.wsdl", "types.xsd")
        assert result == "http://example.com/wsdl/types.xsd"

    def test_relative_against_url_base_subdir(self):
        result = _resolve_location("http://example.com/service.wsdl", "schemas/types.xsd")
        assert result == "http://example.com/schemas/types.xsd"

    def test_relative_against_file_path(self):
        result = _resolve_location("/path/to/service.wsdl", "types.xsd")
        assert result == "/path/to/types.xsd"

    def test_relative_against_file_path_subdir(self):
        result = _resolve_location("/path/to/service.wsdl", "schemas/types.xsd")
        assert result == "/path/to/schemas/types.xsd"


# ---------------------------------------------------------------------------
# load_xml — local file paths
# ---------------------------------------------------------------------------

class TestLoadXml:
    def test_loads_local_wsdl(self):
        root = load_xml(str(FIXTURES / "simple.wsdl"))
        assert root is not None

    def test_returns_element(self):
        from lxml import etree
        root = load_xml(str(FIXTURES / "simple.wsdl"))
        assert isinstance(root, etree._Element)

    def test_file_not_found_raises(self):
        with pytest.raises(WsdlNotFoundError, match="not found"):
            load_xml("/nonexistent/path/service.wsdl")

    def test_invalid_xml_raises(self, tmp_path):
        bad = tmp_path / "bad.wsdl"
        bad.write_text("this is not XML <<<")
        with pytest.raises(WsdlNotFoundError, match="not valid XML"):
            load_xml(str(bad))

    def test_os_error_raises(self, tmp_path):
        # A directory instead of a file triggers OSError on read
        d = tmp_path / "mydir"
        d.mkdir()
        with pytest.raises(WsdlNotFoundError):
            load_xml(str(d))

    def test_url_fetch_success(self):
        from unittest.mock import patch, MagicMock
        from lxml import etree
        simple_xml = (FIXTURES / "simple.wsdl").read_bytes()
        mock_resp = MagicMock()
        mock_resp.read.return_value = simple_xml
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_resp

        with patch("urllib.request.build_opener", return_value=mock_opener):
            root = load_xml("http://example.com/service.wsdl")
        assert root is not None
        assert isinstance(root, etree._Element)

    def test_url_ssl_error_raises(self):
        import ssl
        from unittest.mock import patch, MagicMock
        mock_opener = MagicMock()
        mock_opener.open.side_effect = ssl.SSLError("certificate verify failed")

        with patch("urllib.request.build_opener", return_value=mock_opener):
            with pytest.raises(WsdlNotFoundError, match="SSL"):
                load_xml("https://example.com/service.wsdl")

    def test_url_os_error_raises(self):
        from unittest.mock import patch, MagicMock
        mock_opener = MagicMock()
        mock_opener.open.side_effect = OSError("connection refused")

        with patch("urllib.request.build_opener", return_value=mock_opener):
            with pytest.raises(WsdlNotFoundError, match="Failed to load"):
                load_xml("http://example.com/service.wsdl")

    def test_url_with_auth(self):
        from unittest.mock import patch, MagicMock
        simple_xml = (FIXTURES / "simple.wsdl").read_bytes()
        mock_resp = MagicMock()
        mock_resp.read.return_value = simple_xml
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_resp

        with patch("urllib.request.build_opener", return_value=mock_opener) as mock_build:
            load_xml("http://example.com/service.wsdl", auth=("user", "pass"))
        # build_opener was called with handlers including auth handler
        assert mock_build.called


# ---------------------------------------------------------------------------
# ImportResolver — xs:import chain
# ---------------------------------------------------------------------------

class TestImportResolver:
    def test_no_imports_leaves_schemas_empty(self):
        resolver = ImportResolver()
        from soapix.wsdl.parser import WsdlParser
        from lxml import etree
        # simple.wsdl has no xs:import
        root = load_xml(str(FIXTURES / "simple.wsdl"))
        resolver.resolve_all(root, str(FIXTURES / "simple.wsdl"))
        assert resolver.schemas == {}

    def test_xs_import_loads_external_schema(self):
        resolver = ImportResolver()
        root = load_xml(str(FIXTURES / "import_wsdl.wsdl"))
        resolver.resolve_all(root, str(FIXTURES / "import_wsdl.wsdl"))
        # import_types.xsd defines namespace http://example.com/commontypes
        assert any("commontypes" in k for k in resolver.schemas)

    def test_imported_types_available(self):
        from soapix.wsdl.parser import WsdlParser
        doc = WsdlParser().load(str(FIXTURES / "import_wsdl.wsdl"))
        # Address and PhoneNumber from import_types.xsd
        assert any("Address" in k for k in doc.types)

    def test_xs_import_without_namespace_uses_target_namespace(self):
        # xs:import with schemaLocation but no namespace attribute →
        # schema's own targetNamespace is used as the key
        from lxml import etree
        xsd_path = str(FIXTURES / "import_no_namespace.xsd")
        wsdl = f"""<?xml version="1.0"?>
        <definitions xmlns="http://schemas.xmlsoap.org/wsdl/"
                     xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                     targetNamespace="http://example.com/test">
          <types>
            <xsd:schema>
              <xsd:import schemaLocation="{xsd_path}"/>
            </xsd:schema>
          </types>
        </definitions>""".encode()
        root = etree.fromstring(wsdl)
        resolver = ImportResolver()
        resolver.resolve_all(root, "/fake/path/service.wsdl")
        # targetNamespace from the XSD is used as key
        assert any("nons" in k for k in resolver.schemas)

    def test_duplicate_import_not_loaded_twice(self):
        resolver = ImportResolver()
        root = load_xml(str(FIXTURES / "import_wsdl.wsdl"))
        resolver.resolve_all(root, str(FIXTURES / "import_wsdl.wsdl"))
        # Running again should not re-add (loaded set prevents it)
        schema_count_before = len(resolver.schemas)
        resolver.resolve_all(root, str(FIXTURES / "import_wsdl.wsdl"))
        assert len(resolver.schemas) == schema_count_before

    def test_missing_schema_location_skipped(self):
        # xs:import without schemaLocation — should not raise, just skip
        from lxml import etree
        wsdl = b"""<?xml version="1.0"?>
        <definitions xmlns="http://schemas.xmlsoap.org/wsdl/"
                     xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                     targetNamespace="http://example.com/test">
          <types>
            <xsd:schema>
              <xsd:import namespace="http://example.com/other"/>
            </xsd:schema>
          </types>
        </definitions>"""
        root = etree.fromstring(wsdl)
        resolver = ImportResolver()
        resolver.resolve_all(root, "/fake/path/service.wsdl")
        assert resolver.schemas == {}

    def test_failed_import_raises_wsdl_import_error(self):
        from lxml import etree
        wsdl = b"""<?xml version="1.0"?>
        <definitions xmlns="http://schemas.xmlsoap.org/wsdl/"
                     xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                     targetNamespace="http://example.com/test">
          <types>
            <xsd:schema>
              <xsd:import namespace="http://example.com/other"
                          schemaLocation="nonexistent_types.xsd"/>
            </xsd:schema>
          </types>
        </definitions>"""
        root = etree.fromstring(wsdl)
        resolver = ImportResolver()
        with pytest.raises(WsdlImportError, match="Failed to resolve"):
            resolver.resolve_all(root, "/fake/path/service.wsdl")
