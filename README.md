# soapix

A tolerant, self-documenting Python SOAP client library with an interactive browser playground.

soapix is designed to work with real-world SOAP services that don't perfectly
follow the spec — handling namespace quirks, loose validation, and unclear error
messages that break other libraries.

Built for the real world: where WSDL files are messy, error messages are cryptic,
and you need async out of the box.

## Quick Start

```python
pip install soapix
```

```python
from soapix import SoapClient

client = SoapClient("http://service.example.com/?wsdl")

# Explore and test operations in the browser — no extra tools needed
client.serve()

# Or call directly from code
result = client.service.GetUser(userId=123)
print(result["name"])
```

`client.serve()` opens an interactive UI at `http://localhost:8765` — test any operation instantly, directly from your WSDL, with no Postman, SoapUI, or extra setup required.

---

## Features

- **Interactive playground** — `client.serve()` launches a browser UI to test any operation instantly — no Postman, no SoapUI, no extra setup
- **Code generation** — `client.generate()` produces a fully typed Python client class with `@dataclass` types and IDE autocomplete
- **Tolerant validation** — optional fields can be omitted; required `None` fields send `xsi:nil` instead of crashing
- **Namespace tolerance** — trailing slashes, case differences, and URI fragments are normalized automatically
- **Auto-documentation** — generates terminal, Markdown, and HTML docs directly from the WSDL
- **Meaningful errors** — exceptions include service name, method, endpoint, sent payload, and a human-readable hint
- **Async support** — native `AsyncSoapClient` with `async/await`
- **WSDL caching** — in-memory and file-based caching with TTL
- **Retry & timeout** — configurable per-client
- **Type stubs** — full `.pyi` stubs for IDE autocomplete

## Requirements

- Python 3.9+
- Dependencies: `httpx`, `lxml`, `rich`

## Installation

```bash
pip install soapix
```

---

## Calling Operations

Operations are accessed through `client.service.<OperationName>(...)` using keyword arguments that match the WSDL parameter names.

```python
# Simple call
result = client.service.GetUser(userId=42)

# Multiple parameters
result = client.service.CreateUser(name="John Doe", email="john@example.com")

# Optional parameters can be omitted in tolerant mode (default)
result = client.service.GetUser(userId=42)            # locale is optional — omitted
result = client.service.GetUser(userId=42, locale="en-US")  # or explicitly passed

# Required field sent as None → xsi:nil in tolerant mode
result = client.service.GetUser(userId=None)
```

The return value is a plain Python `dict` (or scalar for leaf values). Nested elements become nested dicts; repeated elements become lists.

```python
# Nested elements → nested dicts
result = client.service.GetOrder(orderId=1)
# {
#   "orderId": 1,
#   "customer": {"id": 42, "name": "John Doe"},   # nested element
#   "items": [                                  # repeated element → list
#     {"sku": "A1", "qty": 2},
#     {"sku": "B3", "qty": 1},
#   ]
# }

result = client.service.GetUser(userId=1)
# {"userId": 1, "name": "John Doe", "email": "john@example.com", "active": True}
```

---

## Async Client

```python
import asyncio
from soapix import AsyncSoapClient

async def main():
    async with AsyncSoapClient("http://service.example.com/?wsdl") as client:
        result = await client.service.GetUser(userId=123)
        print(result["name"])

asyncio.run(main())
```

`AsyncSoapClient` accepts the same options as `SoapClient`. Use it as an async context manager to ensure the underlying HTTP connection is properly closed.

---

## Interactive Playground

> **Local development only.** The playground is intended for use on your local machine during development. It starts an unauthenticated HTTP server — do not run it on a remote server or expose it to a network.

Point soapix at a WSDL and instantly test any operation from your browser — no Postman, no SoapUI, no configuration.

```python
client = SoapClient("https://service.example.com/?wsdl")
client.serve()
```

This starts a local HTTP server (default: `http://localhost:8765`) and opens your browser automatically. From the UI you can:

- Browse all operations in the sidebar
- Fill in input parameters with a form
- Execute calls and see the response as formatted JSON
- Filter operations by name with the search box
- Use **Cmd+Enter** (Mac) / **Ctrl+Enter** to execute quickly

```
soapix playground — UserService
  Listening at http://localhost:8765
  5 operation(s) available
  Press Ctrl+C to stop
```

Options:

```python
client.serve(
    host="localhost",   # interface to bind (default: 'localhost')
    port=8765,          # TCP port (default: 8765)
    open_browser=True,  # open browser automatically (default: True)
)
```

`serve()` is also available on `AsyncSoapClient` and can be called after entering the async context manager.

---

## Code Generation

Generate a fully typed Python client class directly from a WSDL — with real method signatures, `@dataclass` types for nested parameters, and IDE autocomplete.

### CLI

```bash
soapix generate http://service.example.com/?wsdl -o my_client.py
```

Or with a local file:

```bash
soapix generate service.wsdl -o my_client.py
```

### Programmatic

```python
client = SoapClient("http://service.example.com/?wsdl")

# Write to file
client.generate(path="my_client.py")

# Or get as string
code = client.generate()
print(code)
```

### Example output

```python
# Generated by soapix — do not edit manually
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from soapix import SoapClient

@dataclass
class Credentials:
    appKey: str
    appSecret: Optional[str] = None

class UserServiceClient:
    def __init__(self, wsdl: str = "http://service.example.com/?wsdl", **kwargs) -> None:
        self._client = SoapClient(wsdl, **kwargs)

    def GetUser(self, userId: int, locale: Optional[str] = None) -> dict:
        """Retrieves user information by ID."""
        return self._client.service.GetUser(userId=userId, locale=locale)

    def Login(self, credentials: Credentials) -> dict:
        _kw: dict = {}
        _kw["credentials"] = {"appKey": credentials.appKey, "appSecret": credentials.appSecret}
        return self._client.service.Login(**_kw)
```

The generated class wraps `SoapClient` — all constructor options (`timeout`, `retries`, `auth`, `verify`, etc.) are forwarded via `**kwargs`.

> **Note:** Re-run `generate` whenever the WSDL changes to keep the class in sync.

---

## Auto-Documentation

soapix can generate human-readable documentation from the WSDL — terminal output, Markdown, or HTML.

### Terminal

```python
client.docs()
```

```
┌─────────────────────────────────────────────────────────┐
│  UserService                                            │
├──────────────┬───────────────┬──────────┬──────────────┤
│  Operation   │  Parameter    │  Type    │  Required    │
├──────────────┼───────────────┼──────────┼──────────────┤
│  GetUser     │  userId       │  int     │  Yes         │
│              │  locale       │  string  │  No          │
├──────────────┼───────────────┼──────────┼──────────────┤
│  CreateUser  │  name         │  string  │  Yes         │
│              │  email        │  string  │  Yes         │
└──────────────┴───────────────┴──────────┴──────────────┘
```

### Markdown

```python
# Returns a string
md = client.docs(output="markdown")

# Writes to a file
client.docs(output="markdown", path="api_docs.md")
```

### HTML

```python
# Returns a string
html = client.docs(output="html")

# Writes to a file (includes a search box)
client.docs(output="html", path="api_docs.html")
```

---

## Service Check

Before making your first call to an unfamiliar service, run `check()` to diagnose potential WSDL parsing issues without sending any requests.

```python
client = SoapClient("https://service.example.com/?wsdl")
client.check()
```

Example output:

```
soapix check — UserService
Endpoint: https://service.example.com/
SOAP 1.1 | qualified NS: 1

✓ 5 operation(s) found
✓ Endpoint: https://service.example.com/

 Operation   Input fields  Output fields  Status
 CreateUser  2             1              ✓
 GetUser     2             4              ✓
 ...

All checks passed.
```

If something is wrong:

```
✗ No operations found        ← WSDL may not have parsed correctly
⚠ Endpoint is empty          ← wsdl:service element may be missing
✗ input unresolved           ← fields declared but type chain could not be resolved
```

`check()` is also available on `AsyncSoapClient` and can be called before entering the async context manager.

---

## XML Text Fields

soapix follows the WSDL contract when parsing responses. If the WSDL declares a
field as `xs:string`, soapix returns that field as a Python `str` even when the
service puts a complete XML document inside it. This is common in e-invoice/UBL
services:

```python
result = client.service.GetApplicationResponse(...)
xml_text = result["applicationResponse"]  # raw XML string from the service
```

When you want a JSON-like dict for that embedded XML, parse the field explicitly:

```python
application_response = client.parse_xml_field(xml_text)

print(application_response["ID"])
print(application_response["DocumentResponse"]["Response"]["ResponseCode"])
```

Invalid XML is returned unchanged, so the helper is safe to call on optional or
service-dependent string fields.

For very large XML documents, `parse_xml_field()` builds a full Python dict for
the whole document. That is the right choice when you want JSON-like output. If
you only need one or two values from a large XML payload, parsing with `lxml` and
reading those values with XPath can be more efficient because it avoids building
a dict for the entire document.

```python
from lxml import etree

root = etree.fromstring(xml_text.encode("utf-8"))
response_code = root.xpath("string(//*[local-name()='ResponseCode'][1])")
```

---

## Error Handling

soapix raises structured exceptions with actionable context.

```python
from soapix.exceptions import (
    SoapFaultError,       # Server returned a soap:Fault
    HttpError,            # HTTP 4xx/5xx or connection failure
    TimeoutError,         # Request exceeded the timeout
    SerializationError,   # Python value could not be serialised to XML
    WsdlParseError,       # WSDL could not be read or parsed
    WsdlNotFoundError,    # WSDL URL or path not reachable
    WsdlImportError,      # xs:import could not be resolved
)
```

### Exception hierarchy

```
SoapixError
├── WsdlParseError
│   ├── WsdlNotFoundError
│   └── WsdlImportError
├── SoapCallError
│   ├── SoapFaultError
│   ├── HttpError
│   └── TimeoutError
└── SerializationError
```

### Catching errors

```python
from soapix.exceptions import SoapFaultError, HttpError, TimeoutError

try:
    result = client.service.GetUser(userId=999)
except SoapFaultError as e:
    print(e.fault_code)    # e.g. "Server"
    print(e.fault_string)  # e.g. "User not found"
    print(e.detail)        # raw XML detail block, if any
except TimeoutError:
    print("Request timed out — increase timeout or check the endpoint")
except HttpError as e:
    print(f"HTTP error: {e}")
```

Error messages include structured context:

```
'GetUser' call failed

  Service  : UserService
  Method   : GetUser
  Endpoint : http://service.example.com/
  Sent     : {'userId': None}

  Hint  : userId is required (int) — None cannot be sent in strict mode
```

---

## Configuration

All options are keyword-only and passed to the constructor.

```python
client = SoapClient(
    "http://service.example.com/?wsdl",
    timeout=60.0,    # HTTP timeout in seconds (default: 30.0)
    retries=3,       # Retry count on transient failures (default: 0)
    strict=False,    # Strict WSDL validation (default: False)
    debug=True,      # Print request/response XML to terminal (default: False)
    cache=None,      # Cache instance, or None to disable (default: MemoryCache)
)
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `timeout` | `float` | `30.0` | HTTP request timeout in seconds |
| `retries` | `int` | `0` | Retry attempts on 5xx server errors and connection/timeout failures (4xx errors are never retried) |
| `strict` | `bool` | `False` | If `True`, raises on missing required fields instead of sending `xsi:nil` |
| `debug` | `bool` | `False` | Prints colourised request and response XML to the terminal |
| `cache` | `Cache \| None` | `MemoryCache` | WSDL parse cache; `None` disables caching |
| `verify` | `bool \| str` | `True` | SSL verification: `True` (system certs), `False` (skip), or path to a CA bundle file |
| `auth` | `tuple \| None` | `None` | HTTP Basic Auth credentials as `(username, password)` |

---

## Strict Mode

By default, soapix operates in **tolerant mode**: missing required fields send `xsi:nil`, and unknown namespaces are silently normalised. Enable **strict mode** to raise exceptions instead:

```python
client = SoapClient("http://service.example.com/?wsdl", strict=True)

# Raises SerializationError if a required field is missing
client.service.GetUser()         # userId is required → raises
client.service.GetUser(userId=None)  # None on required field → raises
```

---

## SSL & Authentication

### SSL verification

```python
# Default — uses system certificate store
client = SoapClient("https://service.example.com/?wsdl")

# Custom CA bundle (corporate / self-signed certificates)
client = SoapClient("https://service.example.com/?wsdl", verify="/path/to/ca-bundle.pem")

# Disable SSL verification — development only, not recommended for production
client = SoapClient("https://service.example.com/?wsdl", verify=False)
```

To obtain the server's CA certificate:

```bash
openssl s_client -connect service.example.com:443 -showcerts 2>/dev/null \
  | sed -n '/BEGIN CERTIFICATE/,/END CERTIFICATE/p' > ca.pem
```

### HTTP Basic Auth

Some services require credentials to access the WSDL itself and/or to call operations. Pass `auth` as a `(username, password)` tuple — it applies to both WSDL fetching and all SOAP calls:

```python
client = SoapClient(
    "https://service.example.com/?wsdl",
    auth=("username", "password"),
)
```

### Combined

```python
client = SoapClient(
    "https://service.example.com/?wsdl",
    verify="/path/to/ca-bundle.pem",
    auth=("username", "password"),
)
```

---

## Debug Mode

Enable `debug=True` to print the full SOAP envelope sent and the raw XML response to the terminal, with syntax highlighting via `rich`.

```python
client = SoapClient("http://service.example.com/?wsdl", debug=True)
client.service.GetUser(userId=1)
# ── REQUEST ──────────────────────────────
# POST http://service.example.com/
# SOAPAction: "..."
#
# <?xml version="1.0" ...>
# <soap:Envelope ...>
#   ...
# </soap:Envelope>
#
# ── RESPONSE (200 OK, 42ms) ──────────────
# <?xml version="1.0" ...>
# ...
```

---

## WSDL Caching

soapix caches parsed WSDL documents to avoid re-fetching and re-parsing on every instantiation.

### MemoryCache (default)

```python
from soapix.cache import MemoryCache

cache = MemoryCache(
    ttl=300,      # Seconds until entries expire (default: 300, None = no expiry)
    maxsize=64,   # Max entries before oldest is evicted (default: 64)
)

client = SoapClient("http://service.example.com/?wsdl", cache=cache)
```

A module-level default cache is shared across all `SoapClient` instances that don't specify one. Use `get_default_cache()` to access it:

```python
from soapix.cache import get_default_cache
get_default_cache().clear()   # flush all cached WSDLs
```

### FileCache

`FileCache` persists parsed WSDL documents to disk using `pickle`. Useful across process restarts.

```python
from soapix.cache import FileCache

cache = FileCache(
    cache_dir=".soapix_cache",  # Directory to store cache files (created if absent)
    ttl=3600,                   # Seconds until entries expire (default: 3600)
)

client = SoapClient("http://service.example.com/?wsdl", cache=cache)
```

> **Note:** FileCache uses `pickle` for serialisation. Only use it with WSDL
> sources you trust — do not load cache files from untrusted or user-supplied paths.

### Disable caching

```python
client = SoapClient("http://service.example.com/?wsdl", cache=None)
# WSDL is fetched and parsed on every instantiation
```

---

## Retry & Timeout

```python
client = SoapClient(
    "http://service.example.com/?wsdl",
    timeout=10.0,   # fail fast
    retries=3,      # retry up to 3 times on connection/timeout errors
)
```

Retries apply to transient 5xx server errors (no SOAP body), connection failures (`HttpError`), and timeouts (`TimeoutError`). 4xx client errors and SSL failures are never retried.

If a 5xx response contains a `soap:Fault` body (common for authentication failures, invalid input, etc.), it is treated as a definitive fault — `SoapFaultError` is raised immediately without retrying.

---

## Comparison

| Feature | Zeep | Suds | soapix |
|---------|------|------|--------|
| Tolerant validation | No | No | Yes |
| Namespace tolerance | Partial | Partial | Full |
| Meaningful errors | No | No | Yes |
| Auto documentation | No | No | Yes |
| Interactive playground (`serve()`) | No | No | Yes |
| Code generation (`generate()`) | Partial | No | Yes |
| Service diagnostics (`check()`) | No | No | Yes |
| Async support | Partial | No | Native |
| WSDL caching | No | No | Yes |
| Retry & timeout | Manual | Manual | Built-in |
| Type stubs | Partial | No | Yes |
| Python 3.9+ | Yes | No | Yes |

> **Notes:**
> - *Zeep meaningful errors:* Zeep raises structured `Fault` exceptions but does not include sent payload, endpoint, or human-readable hints in the error output.
> - *Zeep async (Partial):* Zeep supports async via a separate `AsyncTransport` configuration; soapix's `AsyncSoapClient` works natively with `async/await` and no extra setup.
> - *Zeep WSDL caching (No):* Zeep re-parses the WSDL on every instantiation by default; caching requires a custom transport wrapper.
> - *Suds:* The original `suds` library is unmaintained. Comparison is based on `suds-community`, its last active fork.

---

## License

MIT — see [LICENSE](LICENSE).
