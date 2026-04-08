"""
soapix — A tolerant, self-documenting Python SOAP client library.

Usage:
    from soapix import SoapClient, AsyncSoapClient

    client = SoapClient('http://service.example.com/?wsdl')
    result = client.service.GetUser(userId=123)
"""

from soapix.client import AsyncSoapClient, SoapClient

__version__ = "0.1.0"
__all__ = ["SoapClient", "AsyncSoapClient"]
