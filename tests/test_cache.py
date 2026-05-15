"""
Phase 4 tests: Cache, retry configuration, client API.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from soapix.cache import MemoryCache, FileCache, make_cache_key, get_default_cache
from soapix.client import SoapClient
from soapix.wsdl.parser import WsdlParser

FIXTURES = Path(__file__).parent / "fixtures"


# ------------------------------------------------------------------
# MemoryCache
# ------------------------------------------------------------------

class TestMemoryCache:
    def test_set_and_get(self):
        cache = MemoryCache()
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_miss_returns_none(self):
        cache = MemoryCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        cache = MemoryCache(ttl=0.05)
        cache.set("key", "value")
        time.sleep(0.1)
        assert cache.get("key") is None

    def test_no_ttl_does_not_expire(self):
        cache = MemoryCache(ttl=None)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_maxsize_evicts_oldest(self):
        cache = MemoryCache(maxsize=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # should evict "a"
        assert len(cache) == 2
        assert cache.get("c") == 3

    def test_clear(self):
        cache = MemoryCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert len(cache) == 0

    def test_overwrite_existing_key(self):
        cache = MemoryCache()
        cache.set("key", "old")
        cache.set("key", "new")
        assert cache.get("key") == "new"

    def test_stores_wsdl_doc(self):
        doc = WsdlParser().load(str(FIXTURES / "simple.wsdl"))
        cache = MemoryCache()
        cache.set("wsdl_key", doc)
        retrieved = cache.get("wsdl_key")
        assert retrieved is doc  # same object reference


# ------------------------------------------------------------------
# FileCache
# ------------------------------------------------------------------

class TestFileCache:
    def test_set_and_get(self, tmp_path):
        cache = FileCache(cache_dir=tmp_path)
        cache.set("key", {"data": 42})
        result = cache.get("key")
        assert result == {"data": 42}

    def test_miss_returns_none(self, tmp_path):
        cache = FileCache(cache_dir=tmp_path)
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self, tmp_path):
        cache = FileCache(cache_dir=tmp_path, ttl=0.05)
        cache.set("key", "value")
        time.sleep(0.1)
        assert cache.get("key") is None

    def test_clear(self, tmp_path):
        cache = FileCache(cache_dir=tmp_path)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert len(cache) == 0

    def test_creates_cache_dir(self, tmp_path):
        cache_dir = tmp_path / "nested" / "cache"
        FileCache(cache_dir=cache_dir)
        assert cache_dir.exists()

    def test_stores_wsdl_doc(self, tmp_path):
        doc = WsdlParser().load(str(FIXTURES / "simple.wsdl"))
        cache = FileCache(cache_dir=tmp_path)
        cache.set("wsdl", doc)
        retrieved = cache.get("wsdl")
        assert retrieved is not None
        assert retrieved.service_name == doc.service_name
        assert set(retrieved.operations) == set(doc.operations)


# ------------------------------------------------------------------
# Cache key
# ------------------------------------------------------------------

class TestCacheKey:
    def test_same_location_same_key(self):
        k1 = make_cache_key("http://example.com/wsdl", False)
        k2 = make_cache_key("http://example.com/wsdl", False)
        assert k1 == k2

    def test_different_strict_different_key(self):
        k1 = make_cache_key("http://example.com/wsdl", False)
        k2 = make_cache_key("http://example.com/wsdl", True)
        assert k1 != k2

    def test_different_location_different_key(self):
        k1 = make_cache_key("http://a.com/wsdl", False)
        k2 = make_cache_key("http://b.com/wsdl", False)
        assert k1 != k2


# ------------------------------------------------------------------
# SoapClient cache integration
# ------------------------------------------------------------------

class TestSoapClientCache:
    def test_client_uses_cache_on_second_load(self):
        """Second client with same WSDL should hit cache, not parse again."""
        cache = MemoryCache()
        wsdl = str(FIXTURES / "simple.wsdl")

        client1 = SoapClient(wsdl, cache=cache)
        assert len(cache) == 1

        # Patch WsdlParser.load to detect if it's called again
        with patch("soapix.wsdl.parser.WsdlParser.load") as mock_load:
            client2 = SoapClient(wsdl, cache=cache)
            mock_load.assert_not_called()

        assert client2._wsdl_doc is client1._wsdl_doc

    def test_client_cache_disabled(self):
        """cache=None should always parse fresh."""
        wsdl = str(FIXTURES / "simple.wsdl")
        with patch("soapix.wsdl.parser.WsdlParser.load", wraps=WsdlParser().load) as mock:
            SoapClient(wsdl, cache=None)
            SoapClient(wsdl, cache=None)
            assert mock.call_count == 2

    def test_client_default_cache_is_memory(self):
        default = get_default_cache()
        assert isinstance(default, MemoryCache)

    def test_client_with_file_cache(self, tmp_path):
        cache = FileCache(cache_dir=tmp_path)
        wsdl = str(FIXTURES / "simple.wsdl")
        client = SoapClient(wsdl, cache=cache)
        assert len(cache) == 1
        assert client._wsdl_doc is not None


# ------------------------------------------------------------------
# SoapClient retry + timeout API
# ------------------------------------------------------------------

class TestSoapClientConfig:
    def test_default_timeout(self):
        client = SoapClient(str(FIXTURES / "simple.wsdl"), cache=None)
        assert client.timeout == 30.0

    def test_custom_timeout(self):
        client = SoapClient(str(FIXTURES / "simple.wsdl"), timeout=60.0, cache=None)
        assert client.timeout == 60.0

    def test_default_retries(self):
        client = SoapClient(str(FIXTURES / "simple.wsdl"), cache=None)
        assert client.retries == 0

    def test_custom_retries(self):
        client = SoapClient(str(FIXTURES / "simple.wsdl"), retries=3, cache=None)
        assert client.retries == 3

    def test_strict_false_default(self):
        client = SoapClient(str(FIXTURES / "simple.wsdl"), cache=None)
        assert client.strict is False

    def test_strict_true(self):
        client = SoapClient(str(FIXTURES / "simple.wsdl"), strict=True, cache=None)
        assert client.strict is True

    def test_debug_false_default(self):
        client = SoapClient(str(FIXTURES / "simple.wsdl"), cache=None)
        assert client.debug is False

    def test_parse_xml_field_helper(self):
        client = SoapClient(str(FIXTURES / "simple.wsdl"), cache=None)
        result = client.parse_xml_field("<ApplicationResponse><ID>abc</ID></ApplicationResponse>")
        assert result == {"ID": "abc"}
