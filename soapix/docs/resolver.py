"""
Docs-layer type resolver — expands message parts to actual field lists.
"""

from __future__ import annotations

from soapix.wsdl.types import OperationInfo, ParameterInfo, WsdlDocument


def resolve_input_fields(
    op: OperationInfo, doc: WsdlDocument
) -> list[ParameterInfo]:
    """
    Return the actual input fields for an operation.

    For document/wrapped operations the message part references an element
    whose type contains the real fields. This function resolves that chain.
    """
    return _resolve_params(op.input_params, doc)


def resolve_output_fields(
    op: OperationInfo, doc: WsdlDocument
) -> list[ParameterInfo]:
    """Return the actual output fields for an operation."""
    return _resolve_params(op.output_params, doc)


def _resolve_params(
    params: list[ParameterInfo], doc: WsdlDocument
) -> list[ParameterInfo]:
    """
    If params is a single 'parameters' part pointing to a complex type,
    expand it to that type's fields. Otherwise return as-is.
    """
    if not params:
        return params

    # Wrapped pattern: single part named 'parameters' (or similar)
    # whose type_name resolves to a complex type in doc.types
    if len(params) == 1:
        part = params[0]
        fields = _expand_type(part.type_name, doc)
        if fields:
            return fields

    # Multiple parts or unexpandable — return as-is
    return params


def _expand_type(type_name: str, doc: WsdlDocument) -> list[ParameterInfo]:
    """
    Look up type_name in doc.types and return its fields.
    Returns empty list if not found or if type has no fields.
    """
    # Try with each registered namespace
    for key, type_info in doc.types.items():
        if type_info.name == type_name and type_info.fields:
            return type_info.fields
    return []
