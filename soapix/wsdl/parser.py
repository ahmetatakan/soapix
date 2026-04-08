"""
WSDL Parser — loads WSDL from URL or file, parses operations, types, and services.
"""

from __future__ import annotations

from typing import Any

from lxml import etree

from soapix.exceptions import WsdlNotFoundError, WsdlParseError
from soapix.wsdl.namespace import (
    NS_SOAP_11,
    NS_SOAP_12,
    NS_WSDL,
    NS_XSD,
    clark,
    localname,
    namespace_of,
    normalize_namespace,
    namespaces_match,
)
from soapix.wsdl.resolver import ImportResolver, load_xml
from soapix.wsdl.types import (
    BindingStyle,
    OperationInfo,
    ParameterInfo,
    ParameterUse,
    ServiceInfo,
    SoapVersion,
    TypeInfo,
    WsdlDocument,
)


class WsdlParser:
    """
    Parses a WSDL document into a WsdlDocument model.

    Features:
    - Loads from URL or file path
    - Resolves xs:import/xs:include chains recursively
    - Tolerant namespace matching
    - Circular reference protection
    - Supports SOAP 1.1 and 1.2
    """

    def __init__(self, strict: bool = False, verify: bool | str = True, auth: tuple[str, str] | None = None) -> None:
        self.strict = strict
        self.verify = verify
        self.auth = auth

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def load(self, location: str) -> WsdlDocument:
        """Load and parse a WSDL synchronously."""
        root = load_xml(location, verify=self.verify, auth=self.auth)
        return self._parse(root, location)

    async def load_async(self, location: str) -> WsdlDocument:
        """Load and parse a WSDL asynchronously (uses httpx)."""
        import asyncio
        import httpx
        from pathlib import Path
        from urllib.parse import urlparse

        if urlparse(location).scheme in ("http", "https"):
            async with httpx.AsyncClient(timeout=30, verify=self.verify, auth=self.auth) as client:
                resp = await client.get(location)
                resp.raise_for_status()
                content = resp.content
        else:
            content = Path(location).read_bytes()

        try:
            root = etree.fromstring(content)
        except etree.XMLSyntaxError as e:
            raise WsdlNotFoundError(f"WSDL is not valid XML: {location} — {e}")

        return self._parse(root, location)

    # ------------------------------------------------------------------
    # Internal parse pipeline
    # ------------------------------------------------------------------

    def _parse(self, root: etree._Element, base_location: str) -> WsdlDocument:
        # Resolve all xs:import/xs:include documents
        resolver = ImportResolver(verify=self.verify, auth=self.auth)
        resolver.resolve_all(root, base_location)

        target_ns = root.get("targetNamespace", "")
        soap_version = self._detect_soap_version(root)

        # Build namespace → prefix map from root
        nsmap: dict[str, str] = {v: k or "" for k, v in root.nsmap.items() if v}

        doc = WsdlDocument(
            target_namespace=target_ns,
            soap_version=soap_version,
        )

        # Named model groups collected during type parsing (local_name → element)
        self._schema_groups: dict[str, etree._Element] = {}

        # Parse in dependency order
        self._parse_types(root, doc, resolver)
        messages = self._parse_messages(root, target_ns)
        port_types = self._parse_port_types(root, messages, target_ns)
        bindings = self._parse_bindings(root, port_types, soap_version, target_ns)
        self._parse_services(root, doc, bindings, target_ns)

        # Bug 5: WSDL without wsdl:service — populate operations from first binding
        if not doc.operations and bindings:
            first_binding = next(iter(bindings.values()))
            for op_name, op_data in first_binding.get("ops", {}).items():
                doc.operations[op_name] = OperationInfo(
                    name=op_name,
                    endpoint="",
                    soap_action=op_data["soap_action"],
                    soap_version=doc.soap_version,
                    style=op_data["style"],
                    use=op_data["use"],
                    input_params=op_data["input"],
                    output_params=op_data["output"],
                    documentation=op_data["documentation"],
                )

        return doc

    # ------------------------------------------------------------------
    # SOAP version detection
    # ------------------------------------------------------------------

    def _detect_soap_version(self, root: etree._Element) -> SoapVersion:
        """Detect SOAP 1.1 or 1.2 from binding elements."""
        for elem in root.iter():
            if callable(elem.tag):
                continue
            ns = namespace_of(elem.tag)
            if namespaces_match(ns, NS_SOAP_12):
                return SoapVersion.SOAP_12
            if namespaces_match(ns, NS_SOAP_11):
                return SoapVersion.SOAP_11
        return SoapVersion.SOAP_11

    # ------------------------------------------------------------------
    # Types
    # ------------------------------------------------------------------

    def _parse_types(
        self,
        root: etree._Element,
        doc: WsdlDocument,
        resolver: ImportResolver,
    ) -> None:
        """Parse wsdl:types → xs:schema definitions."""
        types_el = self._find(root, NS_WSDL, "types")
        if types_el is None:
            return

        schemas = list(types_el)
        # Also include externally resolved schemas
        schemas.extend(resolver.schemas.values())

        for schema in schemas:
            if callable(schema.tag):
                continue
            if localname(schema.tag) != "schema":
                continue
            tns = schema.get("targetNamespace", "")
            self._parse_schema_types(schema, tns, doc)

    def _parse_schema_types(
        self,
        schema: etree._Element,
        tns: str,
        doc: WsdlDocument,
        _seen: set[str] | None = None,
    ) -> None:
        """Parse complex/simple type definitions from an xs:schema element."""
        if _seen is None:
            _seen = set()

        for child in schema:
            if callable(child.tag):
                continue
            local = localname(child.tag)
            name = child.get("name", "")

            if not name:
                continue

            key = f"{{{tns}}}{name}" if tns else name

            if key in _seen:
                continue
            _seen.add(key)

            if local == "complexType":
                type_info = self._parse_complex_type(child, name, tns, _seen)
                doc.types[key] = type_info

            elif local == "simpleType":
                base = self._get_restriction_base(child)
                doc.types[key] = TypeInfo(
                    name=name, namespace=tns, kind="simple", base_type=base
                )

            elif local == "element":
                type_name = child.get("type", "")
                complex_child = self._find(child, NS_XSD, "complexType")
                if complex_child is not None:
                    type_info = self._parse_complex_type(
                        complex_child, name, tns, _seen
                    )
                    doc.types[key] = type_info
                elif type_name:
                    doc.types[key] = TypeInfo(
                        name=name,
                        namespace=tns,
                        kind="simple",
                        base_type=type_name,
                    )

            elif local == "group" and name:
                # Store named model group for xs:group ref="..." resolution (Bug 3)
                self._schema_groups[name] = child
                if tns:
                    self._schema_groups[f"{{{tns}}}{name}"] = child

    def _parse_complex_type(
        self,
        element: etree._Element,
        name: str,
        tns: str,
        seen: set[str],
    ) -> TypeInfo:
        type_info = TypeInfo(name=name, namespace=tns, kind="complex")
        self._collect_fields(element, type_info, tns, seen, depth=0)
        return type_info

    def _collect_fields(
        self,
        element: etree._Element,
        type_info: TypeInfo,
        tns: str,
        seen: set[str],
        depth: int,
    ) -> None:
        """Recursively collect fields from a complexType, with depth guard."""
        if depth > 20:
            # Circular reference protection: bail out at unreasonable depth
            return

        for child in element:
            if callable(child.tag):
                continue
            local = localname(child.tag)

            if local == "element":
                param = self._element_to_param(child, tns)
                if param:
                    type_info.fields.append(param)
            elif local == "any":
                type_info.fields.append(
                    ParameterInfo(
                        name="_any",
                        type_name="any",
                        namespace=tns,
                        required=False,
                    )
                )
            elif local == "extension":
                # Bug 2: capture base type for inheritance; then descend for own fields
                base = child.get("base", "")
                if base:
                    if ":" in base:
                        base = base.split(":", 1)[1]
                    type_info.base_type = base
                self._collect_fields(child, type_info, tns, seen, depth + 1)
            elif local == "group":
                # Bug 3: xs:group ref="..." — resolve named model group
                ref = child.get("ref", "")
                if ref:
                    if ":" in ref:
                        ref = ref.split(":", 1)[1]
                    group_el = self._schema_groups.get(ref)
                    if group_el is not None:
                        self._collect_fields(group_el, type_info, tns, seen, depth + 1)
                else:
                    self._collect_fields(child, type_info, tns, seen, depth + 1)
            elif local in ("sequence", "all", "choice", "complexContent",
                           "simpleContent", "restriction", "attributeGroup"):
                # Descend into structural/grouping elements
                self._collect_fields(child, type_info, tns, seen, depth + 1)

    def _element_to_param(
        self, element: etree._Element, tns: str
    ) -> ParameterInfo | None:
        name = element.get("name", "")
        if not name:
            # Bug 1: xs:element ref="tns:SomeElement" — use ref local name
            ref = element.get("ref", "")
            if not ref:
                return None
            if ":" in ref:
                name = ref.split(":", 1)[1]
            else:
                name = ref
            type_name = name  # resolved by docs layer via doc.types

            min_occurs = int(element.get("minOccurs", "1"))
            max_occurs_raw = element.get("maxOccurs", "1")
            max_occurs = None if max_occurs_raw == "unbounded" else int(max_occurs_raw)
            nillable = element.get("nillable", "false").lower() == "true"

            return ParameterInfo(
                name=name,
                type_name=type_name,
                namespace=tns,
                required=min_occurs > 0 and not nillable,
                min_occurs=min_occurs,
                max_occurs=max_occurs,
            )

        type_name = element.get("type", "anyType")
        if ":" in type_name:
            type_name = type_name.split(":", 1)[1]

        min_occurs = int(element.get("minOccurs", "1"))
        max_occurs_raw = element.get("maxOccurs", "1")
        max_occurs = None if max_occurs_raw == "unbounded" else int(max_occurs_raw)
        nillable = element.get("nillable", "false").lower() == "true"
        default = element.get("default")

        return ParameterInfo(
            name=name,
            type_name=type_name,
            namespace=tns,
            required=min_occurs > 0 and not nillable,
            min_occurs=min_occurs,
            max_occurs=max_occurs,
            default=default,
        )

    def _get_restriction_base(self, element: etree._Element) -> str | None:
        for child in element.iter():
            if callable(child.tag):
                continue
            if localname(child.tag) == "restriction":
                base = child.get("base", "")
                if ":" in base:
                    return base.split(":", 1)[1]
                return base or None
        return None

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def _parse_messages(
        self, root: etree._Element, tns: str
    ) -> dict[str, list[ParameterInfo]]:
        """Parse wsdl:message definitions → {message_name: [ParameterInfo]}."""
        messages: dict[str, list[ParameterInfo]] = {}

        for msg_el in self._findall(root, NS_WSDL, "message"):
            name = msg_el.get("name", "")
            parts: list[ParameterInfo] = []

            for part in self._findall(msg_el, NS_WSDL, "part"):
                part_name = part.get("name", "")
                element_ref = part.get("element", "")
                type_ref = part.get("type", "")

                ref = element_ref or type_ref
                if ":" in ref:
                    ref = ref.split(":", 1)[1]

                parts.append(
                    ParameterInfo(
                        name=part_name,
                        type_name=ref,
                        namespace=tns,
                    )
                )

            messages[name] = parts

        return messages

    # ------------------------------------------------------------------
    # Port types (abstract operations)
    # ------------------------------------------------------------------

    def _parse_port_types(
        self,
        root: etree._Element,
        messages: dict[str, list[ParameterInfo]],
        tns: str,
    ) -> dict[str, dict[str, Any]]:
        """Parse wsdl:portType → abstract operation definitions."""
        port_types: dict[str, dict[str, Any]] = {}

        for pt in self._findall(root, NS_WSDL, "portType"):
            pt_name = pt.get("name", "")
            ops: dict[str, Any] = {}

            for op in self._findall(pt, NS_WSDL, "operation"):
                op_name = op.get("name", "")
                doc_el = self._find(op, NS_WSDL, "documentation")
                documentation = (doc_el.text or "").strip() if doc_el is not None else ""

                input_el = self._find(op, NS_WSDL, "input")
                output_el = self._find(op, NS_WSDL, "output")

                input_msg = self._resolve_message_ref(input_el, messages) if input_el is not None else []
                output_msg = self._resolve_message_ref(output_el, messages) if output_el is not None else []

                ops[op_name] = {
                    "input": input_msg,
                    "output": output_msg,
                    "documentation": documentation,
                }

            port_types[pt_name] = ops

        return port_types

    def _resolve_message_ref(
        self,
        element: etree._Element,
        messages: dict[str, list[ParameterInfo]],
    ) -> list[ParameterInfo]:
        msg_ref = element.get("message", "")
        if ":" in msg_ref:
            msg_ref = msg_ref.split(":", 1)[1]
        return messages.get(msg_ref, [])

    # ------------------------------------------------------------------
    # Bindings (concrete operations)
    # ------------------------------------------------------------------

    def _parse_bindings(
        self,
        root: etree._Element,
        port_types: dict[str, dict[str, Any]],
        soap_version: SoapVersion,
        tns: str,
    ) -> dict[str, dict[str, Any]]:
        """Parse wsdl:binding → concrete SOAP operation details."""
        soap_ns = NS_SOAP_12 if soap_version == SoapVersion.SOAP_12 else NS_SOAP_11
        bindings: dict[str, dict[str, Any]] = {}

        for binding_el in self._findall(root, NS_WSDL, "binding"):
            binding_name = binding_el.get("name", "")
            type_ref = binding_el.get("type", "")
            if ":" in type_ref:
                type_ref = type_ref.split(":", 1)[1]

            # Binding-level style (document/rpc)
            soap_binding = self._find_soap(binding_el, soap_ns, "binding")
            binding_style_str = "document"
            if soap_binding is not None:
                binding_style_str = soap_binding.get("style", "document")

            binding_style = (
                BindingStyle.RPC
                if binding_style_str == "rpc"
                else BindingStyle.DOCUMENT
            )

            ops: dict[str, Any] = {}
            abstract_ops = port_types.get(type_ref, {})

            for op_el in self._findall(binding_el, NS_WSDL, "operation"):
                op_name = op_el.get("name", "")

                soap_op = self._find_soap(op_el, soap_ns, "operation")
                soap_action = ""
                op_style = binding_style
                if soap_op is not None:
                    soap_action = soap_op.get("soapAction", "")
                    style_str = soap_op.get("style", binding_style_str)
                    op_style = (
                        BindingStyle.RPC if style_str == "rpc" else BindingStyle.DOCUMENT
                    )

                # Determine use (literal/encoded)
                use = ParameterUse.LITERAL
                body_el = self._find_soap(op_el, soap_ns, "body")
                if body_el is not None:
                    use_str = body_el.get("use", "literal")
                    use = ParameterUse.ENCODED if use_str == "encoded" else ParameterUse.LITERAL

                abstract = abstract_ops.get(op_name, {})

                ops[op_name] = {
                    "soap_action": soap_action,
                    "style": op_style,
                    "use": use,
                    "input": abstract.get("input", []),
                    "output": abstract.get("output", []),
                    "documentation": abstract.get("documentation", ""),
                }

            bindings[binding_name] = {"ops": ops, "type_ref": type_ref}

        return bindings

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    def _parse_services(
        self,
        root: etree._Element,
        doc: WsdlDocument,
        bindings: dict[str, dict[str, Any]],
        tns: str,
    ) -> None:
        """Parse wsdl:service → populate doc.services and doc.operations."""
        soap_ns = NS_SOAP_12 if doc.soap_version == SoapVersion.SOAP_12 else NS_SOAP_11

        for svc_el in self._findall(root, NS_WSDL, "service"):
            svc_name = svc_el.get("name", "")
            doc_el = self._find(svc_el, NS_WSDL, "documentation")
            svc_doc = (doc_el.text or "").strip() if doc_el is not None else ""

            for port_el in self._findall(svc_el, NS_WSDL, "port"):
                binding_ref = port_el.get("binding", "")
                if ":" in binding_ref:
                    binding_ref = binding_ref.split(":", 1)[1]

                # Get endpoint address
                endpoint = ""
                addr_el = self._find_soap(port_el, soap_ns, "address")
                if addr_el is None:
                    # Try HTTP binding address
                    for child in port_el:
                        if localname(child.tag) == "address":
                            addr_el = child
                            break
                if addr_el is not None:
                    endpoint = addr_el.get("location", "")

                doc.services.append(
                    ServiceInfo(
                        name=svc_name,
                        endpoint=endpoint,
                        documentation=svc_doc,
                    )
                )

                # Populate operations from matching binding
                binding = bindings.get(binding_ref, {})
                for op_name, op_data in binding.get("ops", {}).items():
                    if op_name in doc.operations:
                        continue  # first binding wins

                    doc.operations[op_name] = OperationInfo(
                        name=op_name,
                        endpoint=endpoint,
                        soap_action=op_data["soap_action"],
                        soap_version=doc.soap_version,
                        style=op_data["style"],
                        use=op_data["use"],
                        input_params=op_data["input"],
                        output_params=op_data["output"],
                        documentation=op_data["documentation"],
                    )

    # ------------------------------------------------------------------
    # Helper finders (namespace-tolerant)
    # ------------------------------------------------------------------

    def _find(
        self, parent: etree._Element, ns: str, local: str
    ) -> etree._Element | None:
        """Find first child matching namespace+localname, with tolerant NS match."""
        for child in parent:
            if callable(child.tag):
                continue
            child_ns = namespace_of(child.tag)
            child_local = localname(child.tag)
            if child_local == local and namespaces_match(child_ns, ns):
                return child
        return None

    def _findall(
        self, parent: etree._Element, ns: str, local: str
    ) -> list[etree._Element]:
        """Find all children matching namespace+localname, with tolerant NS match."""
        return [
            child for child in parent
            if not callable(child.tag)
            and localname(child.tag) == local
            and namespaces_match(namespace_of(child.tag), ns)
        ]

    def _find_soap(
        self, parent: etree._Element, soap_ns: str, local: str
    ) -> etree._Element | None:
        """Find a SOAP-namespaced child (checks both SOAP 1.1 and 1.2 NS)."""
        for child in parent:
            if callable(child.tag):
                continue
            child_ns = namespace_of(child.tag)
            child_local = localname(child.tag)
            if child_local == local and (
                namespaces_match(child_ns, soap_ns)
                or namespaces_match(child_ns, NS_SOAP_11)
                or namespaces_match(child_ns, NS_SOAP_12)
            ):
                return child
        return None
