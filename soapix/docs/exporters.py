"""
Markdown and HTML exporters for soapix documentation.
"""

from __future__ import annotations

from pathlib import Path

from soapix.wsdl.types import OperationInfo, ParameterInfo, WsdlDocument
from soapix.docs.examples import build_example, build_async_example
from soapix.docs.resolver import resolve_input_fields, resolve_output_fields


# ------------------------------------------------------------------
# Markdown
# ------------------------------------------------------------------

def render_markdown(doc: WsdlDocument) -> str:
    lines: list[str] = []
    lines.append(f"# {doc.service_name}")
    lines.append("")
    lines.append(f"**Endpoint:** `{doc.endpoint}`")
    lines.append("")

    if not doc.operations:
        lines.append("_No operations found in this service._")
        return "\n".join(lines)

    lines.append("## Operations")
    lines.append("")

    for _, op in sorted(doc.operations.items()):
        lines.extend(_operation_markdown(op, doc))

    return "\n".join(lines)


def _operation_markdown(op: OperationInfo, doc: WsdlDocument) -> list[str]:
    input_fields = resolve_input_fields(op, doc)
    output_fields = resolve_output_fields(op, doc)
    lines: list[str] = []

    lines.append(f"### {op.name}")
    lines.append("")

    if op.documentation:
        lines.append(op.documentation)
        lines.append("")

    # Parameters
    lines.append("**Parameters:**")
    lines.append("")
    if input_fields:
        lines.append("| Field | Type | Required | Default |")
        lines.append("|-------|------|----------|---------|")
        for p in input_fields:
            required = "✅ Yes" if p.required else "❌ No"
            default = str(p.default) if p.default is not None else "—"
            type_str = f"`list[{p.type_name}]`" if p.is_list else f"`{p.type_name}`"
            lines.append(f"| `{p.name}` | {type_str} | {required} | {default} |")
    else:
        lines.append("_No parameters_")
    lines.append("")

    # Returns
    lines.append("**Returns:**")
    lines.append("")
    if output_fields:
        lines.append("| Field | Type |")
        lines.append("|-------|------|")
        for p in output_fields:
            type_str = f"`list[{p.type_name}]`" if p.is_list else f"`{p.type_name}`"
            lines.append(f"| `{p.name}` | {type_str} |")
    else:
        lines.append("_No return information_")
    lines.append("")

    # Examples
    lines.append("**Example:**")
    lines.append("")
    lines.append("```python")
    lines.append(f"result = {build_example(op, doc=doc)}")
    lines.append("```")
    lines.append("")
    lines.append("```python")
    lines.append("# Async usage:")
    lines.append(build_async_example(op, doc=doc))
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    return lines


def export_markdown(doc: WsdlDocument, path: str) -> None:
    Path(path).write_text(render_markdown(doc), encoding="utf-8")


# ------------------------------------------------------------------
# HTML
# ------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{service_name} — soapix docs</title>
  <style>
    :root {{
      --bg: #0f1117; --surface: #1a1d27; --border: #2d3148;
      --text: #e2e8f0; --muted: #8892a4; --cyan: #67e8f9;
      --green: #86efac; --yellow: #fde68a; --red: #fca5a5;
      --code-bg: #12141e;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, sans-serif; background: var(--bg);
            color: var(--text); padding: 2rem; max-width: 960px; margin: 0 auto; }}
    h1 {{ color: var(--cyan); font-size: 1.8rem; margin-bottom: .25rem; }}
    .endpoint {{ color: var(--muted); font-size: .9rem; margin-bottom: 2rem; }}
    .endpoint code {{ color: var(--green); }}
    h2 {{ color: var(--yellow); font-size: 1.3rem; margin: 2rem 0 1rem; }}
    .op {{ background: var(--surface); border: 1px solid var(--border);
           border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }}
    .op-name {{ color: var(--yellow); font-size: 1.15rem;
                font-weight: bold; margin-bottom: .5rem; }}
    .op-doc {{ color: var(--muted); font-style: italic;
               margin-bottom: 1rem; font-size: .9rem; }}
    .section-label {{ font-size: .8rem; text-transform: uppercase;
                      letter-spacing: .08em; color: var(--muted);
                      margin: 1rem 0 .4rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
    th {{ text-align: left; padding: .4rem .6rem; color: var(--muted);
          font-weight: normal; border-bottom: 1px solid var(--border); }}
    td {{ padding: .4rem .6rem; border-bottom: 1px solid var(--border); }}
    td:first-child {{ color: var(--green); font-family: monospace; }}
    td:nth-child(2) {{ color: var(--cyan); font-family: monospace; }}
    .badge-required {{ color: var(--red); font-size: .8rem; }}
    .badge-optional {{ color: var(--muted); font-size: .8rem; }}
    pre {{ background: var(--code-bg); border: 1px solid var(--border);
           border-radius: 6px; padding: 1rem; overflow-x: auto;
           font-size: .85rem; margin-top: .5rem; }}
    code {{ color: var(--green); font-family: monospace; }}
    input[type=search] {{
      width: 100%; padding: .6rem 1rem; margin-bottom: 1.5rem;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 6px; color: var(--text); font-size: 1rem;
    }}
    input[type=search]::placeholder {{ color: var(--muted); }}
    .hidden {{ display: none; }}
  </style>
</head>
<body>
  <h1>{service_name}</h1>
  <div class="endpoint">Endpoint: <code>{endpoint}</code></div>

  <input type="search" id="search" placeholder="Search operation..." oninput="filterOps()">

  <h2>Operations</h2>
  <div id="ops-container">
{ops_html}
  </div>

  <script>
    function filterOps() {{
      const q = document.getElementById('search').value.toLowerCase();
      document.querySelectorAll('.op').forEach(el => {{
        el.classList.toggle('hidden', !el.dataset.name.includes(q));
      }});
    }}
  </script>
</body>
</html>
"""


def render_html(doc: WsdlDocument) -> str:
    ops_html = "\n".join(
        _operation_html(op, doc)
        for op in sorted(doc.operations.values(), key=lambda o: o.name)
    )
    return _HTML_TEMPLATE.format(
        service_name=_escape(doc.service_name),
        endpoint=_escape(doc.endpoint),
        ops_html=ops_html,
    )


def _operation_html(op: OperationInfo, doc: WsdlDocument) -> str:
    input_fields = resolve_input_fields(op, doc)
    output_fields = resolve_output_fields(op, doc)

    doc_html = (
        f'<div class="op-doc">{_escape(op.documentation)}</div>'
        if op.documentation else ""
    )

    if input_fields:
        rows = "".join(_param_row_html(p) for p in input_fields)
        input_html = f"""
    <div class="section-label">Parameters</div>
    <table>
      <tr><th>Field</th><th>Type</th><th>Status</th><th>Default</th></tr>
      {rows}
    </table>"""
    else:
        input_html = '<div class="op-doc">No parameters</div>'

    if output_fields:
        out_rows = "".join(
            f"<tr><td>{_escape(p.name)}</td><td>{_escape(p.type_name)}</td></tr>"
            for p in output_fields
        )
        output_html = f"""
    <div class="section-label">Returns</div>
    <table>
      <tr><th>Field</th><th>Type</th></tr>
      {out_rows}
    </table>"""
    else:
        output_html = ""

    example = _escape(build_example(op, doc=doc))

    return f"""    <div class="op" data-name="{_escape(op.name.lower())}">
      <div class="op-name">📌 {_escape(op.name)}</div>
      {doc_html}
      {input_html}
      {output_html}
      <div class="section-label">Example</div>
      <pre><code>result = {example}</code></pre>
    </div>"""


def _param_row_html(p: ParameterInfo) -> str:
    type_str = f"list[{p.type_name}]" if p.is_list else p.type_name
    badge = (
        '<span class="badge-required">required</span>'
        if p.required
        else '<span class="badge-optional">optional</span>'
    )
    default = str(p.default) if p.default is not None else "—"
    return (
        f"<tr><td>{_escape(p.name)}</td><td>{_escape(type_str)}</td>"
        f"<td>{badge}</td><td>{_escape(default)}</td></tr>"
    )


def export_html(doc: WsdlDocument, path: str) -> None:
    Path(path).write_text(render_html(doc), encoding="utf-8")


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
