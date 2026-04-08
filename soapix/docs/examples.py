"""
Automatic code example generator — builds Python call snippets from OperationInfo.
"""

from __future__ import annotations

from soapix.wsdl.types import OperationInfo, ParameterInfo, WsdlDocument


# Default example values per XSD type
_TYPE_DEFAULTS: dict[str, str] = {
    "string": '"example"',
    "normalizedString": '"example"',
    "token": '"example"',
    "int": "1",
    "integer": "1",
    "long": "1",
    "short": "1",
    "byte": "1",
    "unsignedInt": "1",
    "unsignedLong": "1",
    "unsignedShort": "1",
    "unsignedByte": "1",
    "float": "1.0",
    "double": "1.0",
    "decimal": "1.0",
    "boolean": "True",
    "dateTime": '"2024-01-01T00:00:00"',
    "date": '"2024-01-01"',
    "time": '"00:00:00"',
    "base64Binary": '"..."',
    "hexBinary": '"..."',
    "anyURI": '"http://example.com"',
    "anyType": "{}",
    "anySimpleType": '"example"',
    "any": "{}",
}


def _example_value(param: ParameterInfo) -> str:
    raw = _TYPE_DEFAULTS.get(param.type_name, '"..."')
    if param.is_list:
        return f"[{raw}]"
    return raw


def build_example(
    op: OperationInfo,
    doc: WsdlDocument | None = None,
    client_var: str = "client",
) -> str:
    """
    Build a one-line Python example call for an operation.

    If doc is provided, resolves wrapped type fields for accurate examples.
    """
    fields = _get_fields(op, doc)

    # Only required params in example for brevity; show one optional as hint
    required = [p for p in fields if p.required and p.name != "_any"]
    optional_shown = [p for p in fields if not p.required and p.name != "_any"][:1]
    all_shown = required + optional_shown

    if not all_shown and fields:
        first = next((p for p in fields if p.name != "_any"), None)
        if first:
            all_shown = [first]

    args = ", ".join(f"{p.name}={_example_value(p)}" for p in all_shown)
    return f"{client_var}.service.{op.name}({args})"


def build_async_example(
    op: OperationInfo,
    doc: WsdlDocument | None = None,
    client_var: str = "client",
) -> str:
    call = build_example(op, doc=doc, client_var=client_var)
    return f"result = await {call}"


def _get_fields(
    op: OperationInfo, doc: WsdlDocument | None
) -> list[ParameterInfo]:
    """Resolve actual input fields, expanding wrapped types if doc is provided."""
    if doc is not None:
        from soapix.docs.resolver import resolve_input_fields
        fields = resolve_input_fields(op, doc)
        if fields:
            return fields
    return op.input_params
