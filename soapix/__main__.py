"""CLI entry point: python -m soapix  OR  soapix (via console_scripts)."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="soapix",
        description="soapix SOAP client toolkit",
    )
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate a typed Python client from a WSDL")
    gen.add_argument("wsdl", help="WSDL URL or file path")
    gen.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="Write generated code to FILE (default: stdout)",
    )

    args = parser.parse_args()

    if args.command == "generate":
        _cmd_generate(args.wsdl, args.output)
    else:
        parser.print_help()
        sys.exit(1)


def _cmd_generate(wsdl: str, output_path: str | None) -> None:
    from soapix.wsdl.parser import WsdlParser
    from soapix.codegen.generator import ClientGenerator

    try:
        doc = WsdlParser().load(wsdl)
    except Exception as e:
        print(f"Error loading WSDL: {e}", file=sys.stderr)
        sys.exit(1)

    code = ClientGenerator(doc).generate(wsdl)

    if output_path:
        from pathlib import Path
        Path(output_path).write_text(code, encoding="utf-8")
        print(f"Written to {output_path}")
    else:
        print(code)


if __name__ == "__main__":
    main()
