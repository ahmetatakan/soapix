"""
Tolerant namespace normalization utilities.
"""

from __future__ import annotations


# Well-known SOAP/WSDL namespaces
NS_WSDL = "http://schemas.xmlsoap.org/wsdl/"
NS_SOAP_11 = "http://schemas.xmlsoap.org/wsdl/soap/"
NS_SOAP_12 = "http://schemas.xmlsoap.org/wsdl/soap12/"
NS_SOAP_ENV_11 = "http://schemas.xmlsoap.org/soap/envelope/"
NS_SOAP_ENV_12 = "http://www.w3.org/2003/05/soap-envelope"
NS_XSD = "http://www.w3.org/2001/XMLSchema"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS_XMLMIME = "http://www.w3.org/2005/05/xmlmime"


def normalize_namespace(uri: str) -> str:
    """
    Normalize a namespace URI for tolerant comparison.

    Handles:
    - Trailing slashes: http://example.com/v1/ → http://example.com/v1
    - Case differences: HTTP://Example.COM/v1 → http://example.com/v1
    - Fragment identifiers: http://example.com/v1#types → http://example.com/v1
    """
    if not uri:
        return uri
    uri = uri.strip()
    uri = uri.lower()
    uri = uri.split("#")[0]
    uri = uri.rstrip("/")
    return uri


def namespaces_match(a: str, b: str) -> bool:
    """Return True if two namespace URIs are equivalent after normalization."""
    return normalize_namespace(a) == normalize_namespace(b)


def localname(tag: str) -> str:
    """Extract local name from a Clark-notation tag: {ns}localname → localname."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def namespace_of(tag: str) -> str:
    """Extract namespace from a Clark-notation tag: {ns}localname → ns."""
    if tag.startswith("{"):
        return tag.split("}", 1)[0][1:]
    return ""


def clark(namespace: str, local: str) -> str:
    """Build a Clark-notation tag: clark('http://x.com', 'foo') → '{http://x.com}foo'."""
    if namespace:
        return f"{{{namespace}}}{local}"
    return local
