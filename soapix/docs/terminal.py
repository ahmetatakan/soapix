"""
Terminal documentation renderer — colourful, readable output (rich).
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

from soapix.wsdl.types import OperationInfo, ParameterInfo, WsdlDocument
from soapix.docs.examples import build_example
from soapix.docs.resolver import resolve_input_fields, resolve_output_fields


def _type_label(param: ParameterInfo) -> str:
    t = param.type_name
    if param.is_list:
        return f"list[{t}]"
    return t


def _required_label(param: ParameterInfo) -> str:
    if param.is_optional:
        default = f"  default: {param.default!r}" if param.default is not None else ""
        return f"[dim]optional{default}[/dim]"
    return "[bold red]required[/bold red]"


def render_terminal(doc: WsdlDocument, console: Console | None = None) -> None:
    """Render full service documentation to the terminal using rich."""
    c = console or Console()

    service_name = doc.service_name
    endpoint = doc.endpoint
    op_count = len(doc.operations)

    header = Text()
    header.append(f" SERVICE: {service_name}\n", style="bold cyan")
    header.append(f" Endpoint: {endpoint}\n", style="cyan")
    header.append(f" {op_count} operation(s)", style="dim")

    c.print()
    c.print(Panel(header, box=box.DOUBLE, border_style="cyan", expand=False))

    if not doc.operations:
        c.print("[yellow]No operations found in this service.[/yellow]")
        return

    for _, op in sorted(doc.operations.items()):
        _render_operation(c, op, doc)


def _render_operation(c: Console, op: OperationInfo, doc: WsdlDocument) -> None:
    input_fields = resolve_input_fields(op, doc)
    output_fields = resolve_output_fields(op, doc)

    c.print()
    c.print(f"  [bold yellow]📌 {op.name}[/bold yellow]")
    c.print(f"  [dim]{'─' * 50}[/dim]")

    if op.documentation:
        c.print(f"  [italic]{op.documentation}[/italic]")
        c.print()

    # Input parameters table
    if input_fields:
        c.print("  [bold]Parameters:[/bold]")
        tbl = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
        tbl.add_column(style="green", no_wrap=True)
        tbl.add_column(style="cyan", no_wrap=True)
        tbl.add_column()

        for param in input_fields:
            if param.name == "_any":
                tbl.add_row("*", "any", "[dim]optional — any value[/dim]")
            else:
                tbl.add_row(
                    param.name,
                    f"({_type_label(param)})",
                    _required_label(param),
                )
        c.print(tbl)
    else:
        c.print("  [dim]No parameters[/dim]")

    c.print()

    # Output fields
    if output_fields:
        c.print("  [bold]Returns:[/bold]")
        tbl = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
        tbl.add_column(style="green", no_wrap=True)
        tbl.add_column(style="cyan", no_wrap=True)

        for param in output_fields:
            tbl.add_row(param.name, f"({_type_label(param)})")
        c.print(tbl)
    else:
        c.print("  [dim]No return information[/dim]")

    c.print()

    # Example call
    example = build_example(op, doc=doc)
    c.print("  [bold]Example:[/bold]")
    c.print(f"  [dim green]{example}[/dim green]")
