"""
WSDL/XSD import resolver — handles xs:import and xs:include chains.
"""

from __future__ import annotations

import ssl
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from lxml import etree

from soapix.exceptions import WsdlImportError, WsdlNotFoundError
from soapix.wsdl.namespace import NS_XSD, normalize_namespace


def _make_ssl_context(verify: bool | str) -> ssl.SSLContext | None:
    if verify is False:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    if isinstance(verify, str):
        return ssl.create_default_context(cafile=verify)
    return None  # default system context


def load_xml(
    location: str,
    verify: bool | str = True,
    auth: tuple[str, str] | None = None,
) -> etree._Element:
    """
    Load and parse XML from a URL or file path.
    Returns the root element.

    Args:
        verify: True (default) — normal SSL verification
                False         — disable SSL verification (self-signed certs)
                str           — path to a custom CA bundle / certificate file
        auth:   (username, password) tuple for HTTP Basic Auth, or None
    """
    try:
        if _is_url(location):
            ctx = _make_ssl_context(verify)
            https_handler = urllib.request.HTTPSHandler(context=ctx) if ctx else urllib.request.HTTPSHandler()
            # Allow HTTPS→HTTP redirects that urllib blocks by default
            http_handler = urllib.request.HTTPHandler()
            handlers: list[Any] = [http_handler, https_handler]
            if auth:
                username, password = auth
                password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
                password_mgr.add_password(None, location, username, password)
                handlers.append(urllib.request.HTTPBasicAuthHandler(password_mgr))
            opener = urllib.request.build_opener(*handlers)
            with opener.open(location, timeout=30) as resp:  # noqa: S310
                content = resp.read()
        else:
            content = Path(location).read_bytes()
        return etree.fromstring(content)
    except FileNotFoundError:
        raise WsdlNotFoundError(f"WSDL not found: {location}")
    except ssl.SSLError as e:
        host = urlparse(location).netloc or location
        raise WsdlNotFoundError(
            f"SSL verification failed for {location} — {e}\n\n"
            f"  The server's certificate could not be verified.\n\n"
            f"  Options:\n"
            f'    verify="/path/to/ca-bundle.pem"   # custom CA bundle\n'
            f"    verify=False                       # disable (development only)\n\n"
            f"  To extract the server certificate:\n"
            f"    openssl s_client -connect {host}:443 -showcerts 2>/dev/null \\\n"
            f"      | sed -n '/BEGIN CERTIFICATE/,/END CERTIFICATE/p' > ca.pem\n"
            f"  Then: verify='ca.pem'"
        ) from e
    except OSError as e:
        raise WsdlNotFoundError(f"Failed to load WSDL: {location} — {e}")
    except etree.XMLSyntaxError as e:
        raise WsdlNotFoundError(f"WSDL is not valid XML: {location} — {e}")


def _is_url(location: str) -> bool:
    return urlparse(location).scheme in ("http", "https", "ftp")


def _resolve_location(base: str, relative: str) -> str:
    """Resolve a relative schemaLocation against a base URL or file path."""
    if _is_url(relative):
        return relative
    if _is_url(base):
        return urljoin(base, relative)
    return str(Path(base).parent / relative)


class ImportResolver:
    """
    Recursively loads all xs:import and xs:include documents.
    Keeps track of already-loaded URIs to prevent infinite loops.
    """

    def __init__(self, verify: bool | str = True, auth: tuple[str, str] | None = None) -> None:
        self._loaded: set[str] = set()
        self._verify = verify
        self._auth = auth
        # namespace → root element of the loaded schema
        self.schemas: dict[str, etree._Element] = {}

    def resolve_all(self, root: etree._Element, base_location: str) -> None:
        """
        Walk the element tree and resolve all xs:import / xs:include elements.
        Mutates self.schemas with all discovered schemas.
        """
        self._resolve_element(root, base_location)

    def _resolve_element(
        self, element: etree._Element, base_location: str
    ) -> None:
        xsd_ns = NS_XSD

        for child in element:
            tag = child.tag
            # Skip comments, PIs and other non-element nodes (their tag is callable)
            if callable(tag):
                continue
            # Handle both Clark notation and plain local names
            local = tag.split("}")[-1] if "}" in tag else tag

            if local in ("import", "include"):
                schema_location = child.get("schemaLocation", "")
                namespace = child.get("namespace", "")

                if not schema_location:
                    continue

                resolved = _resolve_location(base_location, schema_location)
                norm_key = normalize_namespace(resolved)

                if norm_key in self._loaded:
                    continue

                self._loaded.add(norm_key)

                try:
                    schema_root = load_xml(resolved, verify=self._verify, auth=self._auth)
                    if namespace:
                        self.schemas[normalize_namespace(namespace)] = schema_root
                    else:
                        tns = schema_root.get("targetNamespace", "")
                        if tns:
                            self.schemas[normalize_namespace(tns)] = schema_root

                    # Recurse into the imported schema
                    self._resolve_element(schema_root, resolved)

                except (WsdlNotFoundError, WsdlImportError) as e:
                    raise WsdlImportError(
                        f"Failed to resolve xs:import: {schema_location} — {e}"
                    ) from e

            else:
                self._resolve_element(child, base_location)
