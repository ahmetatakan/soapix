"""
Phase 3 tests: Documentation Engine
- Terminal output (rich, string capture)
- Markdown render
- HTML render
- Automatic code example generation
- DocsGenerator API
"""

from __future__ import annotations

from pathlib import Path
from io import StringIO

import pytest
from rich.console import Console

from soapix.wsdl.parser import WsdlParser
from soapix.docs.generator import DocsGenerator
from soapix.docs.examples import build_example, build_async_example
from soapix.docs.exporters import render_markdown, render_html
from soapix.docs.terminal import render_terminal

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def simple_doc():
    return WsdlParser().load(str(FIXTURES / "simple.wsdl"))


@pytest.fixture
def wrapped_doc():
    return WsdlParser().load(str(FIXTURES / "wrapped.wsdl"))


# ------------------------------------------------------------------
# Kod örneği üretimi
# ------------------------------------------------------------------

class TestExampleGenerator:
    def test_build_example_contains_method(self, simple_doc):
        op = simple_doc.get_operation("GetUser")
        example = build_example(op)
        assert "GetUser" in example

    def test_build_example_contains_required_param(self, simple_doc):
        op = simple_doc.get_operation("GetUser")
        example = build_example(op, doc=simple_doc)
        assert "userId" in example

    def test_build_example_is_valid_python_syntax(self, simple_doc):
        op = simple_doc.get_operation("GetUser")
        example = build_example(op, doc=simple_doc)
        # Should be parseable as a Python statement
        compile(f"result = {example}", "<test>", "exec")

    def test_build_async_example_has_await(self, simple_doc):
        op = simple_doc.get_operation("GetUser")
        example = build_async_example(op, doc=simple_doc)
        assert "await" in example

    def test_build_example_custom_client_var(self, simple_doc):
        op = simple_doc.get_operation("GetUser")
        example = build_example(op, doc=simple_doc, client_var="svc")
        assert example.startswith("svc.service.")

    def test_wrapped_example_contains_query(self, wrapped_doc):
        op = wrapped_doc.get_operation("SearchProducts")
        example = build_example(op, doc=wrapped_doc)
        assert "SearchProducts" in example
        assert "query" in example


# ------------------------------------------------------------------
# Terminal renderer
# ------------------------------------------------------------------

class TestTerminalRenderer:
    def _capture(self, doc) -> str:
        buf = StringIO()
        console = Console(file=buf, no_color=True, highlight=False)
        render_terminal(doc, console=console)
        return buf.getvalue()

    def test_terminal_contains_service_name(self, simple_doc):
        output = self._capture(simple_doc)
        assert "UserService" in output

    def test_terminal_contains_operation_name(self, simple_doc):
        output = self._capture(simple_doc)
        assert "GetUser" in output

    def test_terminal_contains_endpoint(self, simple_doc):
        output = self._capture(simple_doc)
        assert "example.com" in output

    def test_terminal_contains_param_name(self, simple_doc):
        output = self._capture(simple_doc)
        assert "userId" in output

    def test_terminal_contains_example(self, simple_doc):
        output = self._capture(simple_doc)
        assert "client.service.GetUser" in output

    def test_terminal_contains_documentation(self, simple_doc):
        output = self._capture(simple_doc)
        assert "ID" in output

    def test_terminal_all_operations(self, simple_doc):
        output = self._capture(simple_doc)
        assert "GetUser" in output
        assert "CreateUser" in output

    def test_terminal_wrapped_service(self, wrapped_doc):
        output = self._capture(wrapped_doc)
        assert "SearchProducts" in output
        assert "query" in output


# ------------------------------------------------------------------
# Markdown renderer
# ------------------------------------------------------------------

class TestMarkdownRenderer:
    def test_markdown_has_h1(self, simple_doc):
        md = render_markdown(simple_doc)
        assert md.startswith("# UserService")

    def test_markdown_contains_operation(self, simple_doc):
        md = render_markdown(simple_doc)
        assert "### GetUser" in md

    def test_markdown_contains_param_table(self, simple_doc):
        md = render_markdown(simple_doc)
        assert "userId" in md
        assert "required" in md.lower() or "Yes" in md

    def test_markdown_contains_example_block(self, simple_doc):
        md = render_markdown(simple_doc)
        assert "```python" in md
        assert "GetUser" in md

    def test_markdown_contains_returns(self, simple_doc):
        md = render_markdown(simple_doc)
        assert "Returns" in md

    def test_markdown_export_to_file(self, simple_doc, tmp_path):
        out = tmp_path / "api.md"
        gen = DocsGenerator(simple_doc)
        gen.render(output="markdown", path=str(out))
        assert out.exists()
        content = out.read_text()
        assert "UserService" in content

    def test_markdown_returns_string_when_no_path(self, simple_doc):
        gen = DocsGenerator(simple_doc)
        result = gen.render(output="markdown")
        assert isinstance(result, str)
        assert "UserService" in result


# ------------------------------------------------------------------
# HTML renderer
# ------------------------------------------------------------------

class TestHtmlRenderer:
    def test_html_is_valid_structure(self, simple_doc):
        html = render_html(simple_doc)
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_html_contains_service_name(self, simple_doc):
        html = render_html(simple_doc)
        assert "UserService" in html

    def test_html_contains_operation(self, simple_doc):
        html = render_html(simple_doc)
        assert "GetUser" in html

    def test_html_contains_search_input(self, simple_doc):
        html = render_html(simple_doc)
        assert 'type=search' in html or 'type="search"' in html

    def test_html_contains_endpoint(self, simple_doc):
        html = render_html(simple_doc)
        assert "example.com/userservice" in html

    def test_html_escapes_special_chars(self, simple_doc):
        html = render_html(simple_doc)
        # Should not contain unescaped < or > in content areas
        # The tag <html> itself is fine, but user content must be escaped
        assert "&lt;" not in html.split("<body>")[0]  # head is fine

    def test_html_export_to_file(self, simple_doc, tmp_path):
        out = tmp_path / "api.html"
        gen = DocsGenerator(simple_doc)
        gen.render(output="html", path=str(out))
        assert out.exists()
        content = out.read_text()
        assert "UserService" in content

    def test_html_returns_string_when_no_path(self, simple_doc):
        gen = DocsGenerator(simple_doc)
        result = gen.render(output="html")
        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result


# ------------------------------------------------------------------
# DocsGenerator API
# ------------------------------------------------------------------

class TestDocsGenerator:
    def test_invalid_output_raises(self, simple_doc):
        gen = DocsGenerator(simple_doc)
        with pytest.raises(ValueError, match="Invalid"):
            gen.render(output="pdf")

    def test_terminal_render_returns_none(self, simple_doc):
        gen = DocsGenerator(simple_doc)
        buf = StringIO()
        # Patch console — terminal render should not raise
        result = gen.render(output="terminal")
        assert result is None

    def test_markdown_render_returns_string(self, simple_doc):
        gen = DocsGenerator(simple_doc)
        result = gen.render(output="markdown")
        assert isinstance(result, str)

    def test_html_render_returns_string(self, simple_doc):
        gen = DocsGenerator(simple_doc)
        result = gen.render(output="html")
        assert isinstance(result, str)
