"""
soapix — A tolerant, self-documenting Python SOAP client library.

Usage:
    from soapix import SoapClient, AsyncSoapClient

    client = SoapClient('http://service.example.com/?wsdl')
    result = client.service.GetUser(userId=123)
"""

from soapix.client import AsyncSoapClient, SoapClient

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("soapix")
except PackageNotFoundError:
    __version__ = "unknown"
__all__ = ["SoapClient", "AsyncSoapClient"]
