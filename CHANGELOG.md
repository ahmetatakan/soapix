# Changelog

All notable changes to this project are documented here.

---

## [0.5.0] — 2026-04-10

### Added

- **Code generation** (`client.generate()` / `soapix generate` CLI) — generates a
  fully typed Python client class from a WSDL. Complex nested types become
  `@dataclass` definitions; required parameters have no default, optional parameters
  default to `None`. The generated class wraps `SoapClient` and forwards all
  constructor options via `**kwargs`.

  ```bash
  soapix generate http://service.example.com/?wsdl -o my_client.py
  ```

  ```python
  client = SoapClient("http://service/?wsdl")
  client.generate(path="my_client.py")
  ```

- **`soapix` CLI entry point** — `soapix generate <wsdl> [-o FILE]` available after
  `pip install soapix`. Also accessible as `python -m soapix generate`.

---

## [0.4.4] — 2026-04-09

### Changed

- **Python 3.9+ support** — minimum required version lowered from 3.10 to 3.9.

---

## [0.4.3] — 2026-04-09

### Added

- **Interactive playground response formatting** — JSON responses are now syntax-
  highlighted (keys, strings, numbers, booleans, null each in distinct colours).
  A **Copy** button appears on successful responses. Error messages with a `Hint:`
  section are rendered in two parts for readability.

### Fixed

- **500 + SOAP Fault now raises `SoapFaultError`** — SOAP services return HTTP 500
  when a business-level fault occurs (wrong credentials, invalid input, etc.).
  Previously soapix raised a generic `HttpError: HTTP 500 error`. Now the response
  body is inspected: if it contains a `soap:Fault`, the body is returned to the
  parser which raises a structured `SoapFaultError` with `fault_code` and
  `fault_string`. Genuine transient 500s (no SOAP body) still retry as before.

---

## [0.4.2] — 2026-04-09

### Fixed

- **Response parser crash on XML comments** — SOAP servers that include comment or
  processing-instruction nodes inside `Envelope` or `Body` no longer cause an
  `AttributeError`. Affected `_find_body`, `_find_fault`, `_unwrap`, and
  `_element_to_dict` in `xml/parser.py`.

- **RPC/encoded `use` not detected** — `<soap:body use="encoded">` nested inside
  `<input>` was silently ignored; the parser now looks inside the `<input>` element
  when the body is not a direct child of `<operation>`.

- **`_anyAttribute` leaking into docs and examples** — `xs:anyAttribute` placeholder
  fields were appearing in generated examples, terminal docs, and the playground UI.
  They are now filtered the same way `_any` is.

- **`pydantic` removed from dependencies** — it was declared as a runtime dependency
  but never imported; the data model uses stdlib `dataclasses`.

### Tests

- Added `tests/test_transport.py` — sync and async transport retry semantics:
  4xx raises immediately without retrying, 5xx retries up to `retries` count,
  SSL `ConnectError` raises immediately, timeout raises `TimeoutError`.

- Added `tests/test_builder_advanced.py` — RPC/encoded builder (xsi:type annotations,
  nil, values) and `xs:list` space-separated serialization.

- Added fixtures `tests/fixtures/rpc_encoded.wsdl` and `tests/fixtures/xs_list.wsdl`.

---

## [0.4.1] — 2026-04-08

### Added

- **Interactive playground** (`client.serve()`) — browser-based UI to test any
  operation directly from the WSDL; no Postman or SoapUI needed.
  Supports nested complex types, `Cmd/Ctrl+Enter` shortcut, and live JSON responses.

- **Nested type expansion** — terminal docs, examples, and playground now recursively
  expand complex types (e.g. `auth (Authentication)` → `appKey`, `appSecret`) with
  cycle detection via `frozenset`.

### Fixed

- `xs:attribute` fields serialised as XML attributes (not child elements).
- `xs:attributeGroup ref="..."` resolved to named attribute group fields.
- `xs:restriction` now inherits base type fields instead of being treated as a dead end.
- `wsdl:fault` messages parsed and stored on `OperationInfo.fault_params`.
- `xsi:nil` namespace corrected (`NS_XSI` instead of `NS_SOAP_ENV_11`).
- XML response attributes preserved in parsed result dict.
- Mixed content (`element.text` alongside child elements) preserved as `_text`.
- Leading zeros in numeric strings preserved (`"007"` stays `"007"`).
- `xs:list` detected and serialised as space-separated text.
- Inline `xs:complexType` (no `type=""` attribute) resolved by element name.

### Changed

- SSL errors now raise with an actionable hint (openssl extraction command,
  `verify` options) instead of a bare exception.
- 4xx HTTP errors raise immediately without retrying; 5xx errors retry up to
  `retries` count; SSL errors raise immediately.
- `MemoryCache` is thread-safe (`threading.Lock` on all operations).
- `__version__` is read from installed package metadata (`importlib.metadata`).
- `pyproject.toml` — author metadata added.

---

## [0.3.0] — 2026-04-07

### Added

- `client.check()` — pre-flight WSDL diagnostics without making any service calls.
- `FileCache` — disk-based WSDL cache with TTL and path traversal protection.
- `verify` and `auth` parameters on both clients and the WSDL resolver.
- SOAP 1.2 envelope support.
- `elementFormDefault="qualified"` namespace handling for child elements.
- `xs:group ref` resolution.
- Element-reference (`element="tns:Foo"`) part detection and correct wrapper naming.
- `client.pyi` type stubs for IDE autocomplete.
- HTML export for `client.docs()`.

---

## [0.2.0] — 2026-04-06

### Added

- `AsyncSoapClient` with native `async/await` support.
- Retry logic (`retries` parameter) with exponential-style attempt counting.
- `MemoryCache` with TTL and LRU-like eviction.
- Terminal and Markdown documentation generation (`client.docs()`).
- Structured exceptions with service name, method, endpoint, and hint.

---

## [0.1.0] — 2026-04-05

Initial release.

- `SoapClient` with document/literal SOAP 1.1 support.
- WSDL loading from URL and file path.
- `xs:import` / `xs:include` chain resolution.
- Tolerant namespace normalization.
- Basic `xsi:nil` handling for `None` values.
