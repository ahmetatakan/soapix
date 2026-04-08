"""
Documentation generator — routes to terminal, markdown, or HTML renderer.
"""

from __future__ import annotations

from soapix.wsdl.types import WsdlDocument


class DocsGenerator:
    """
    Generates documentation from a parsed WsdlDocument.

    Usage:
        gen = DocsGenerator(wsdl_doc)
        gen.render()                                  # terminal
        gen.render(output='markdown', path='api.md')  # markdown file
        gen.render(output='html',     path='api.html') # html file
    """

    def __init__(self, wsdl_doc: WsdlDocument) -> None:
        self._doc = wsdl_doc

    def render(
        self,
        output: str = "terminal",
        path: str | None = None,
    ) -> str | None:
        """
        Render documentation.

        Args:
            output: 'terminal' (default), 'markdown', or 'html'
            path:   File path for markdown/html output. If None, returns string.

        Returns:
            str if output is 'markdown' or 'html' and path is None, else None.
        """
        match output:
            case "terminal":
                self._render_terminal()
                return None
            case "markdown":
                return self._render_markdown(path)
            case "html":
                return self._render_html(path)
            case _:
                raise ValueError(
                    f"Invalid output format: '{output}'. "
                    f"Supported: 'terminal', 'markdown', 'html'"
                )

    def _render_terminal(self) -> None:
        from soapix.docs.terminal import render_terminal
        render_terminal(self._doc)

    def _render_markdown(self, path: str | None) -> str | None:
        from soapix.docs.exporters import render_markdown, export_markdown
        if path:
            export_markdown(self._doc, path)
            return None
        return render_markdown(self._doc)

    def _render_html(self, path: str | None) -> str | None:
        from soapix.docs.exporters import render_html, export_html
        if path:
            export_html(self._doc, path)
            return None
        return render_html(self._doc)
