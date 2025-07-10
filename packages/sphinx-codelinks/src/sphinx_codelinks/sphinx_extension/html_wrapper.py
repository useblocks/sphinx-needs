from collections.abc import Generator
from pathlib import Path
from typing import Any

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import CLexer


class LineFormatter(HtmlFormatter):  # type: ignore[type-arg]
    def __init__(self, lineno_href: dict[int, str], *args: Any, **kwargs: Any) -> None:  # type: ignore[explicit-any]
        super().__init__(*args, **kwargs)
        self.lineno_href = lineno_href

    def wrap(self, source: Generator[Any]) -> Generator[Any]:  # type: ignore[explicit-any]
        return self._wrap_custom_lines(super().wrap(source))  # type: ignore[no-untyped-call]

    def _wrap_custom_lines(self, source: Generator[Any]) -> Generator[Any]:  # type: ignore[explicit-any]
        lineno = 0
        for is_line, line_html in source:
            if is_line:
                lineno += 1
                if lineno in self.lineno_href:
                    lineno_achor, inline_lineno, code_span = line_html.split("</a>")
                    # Ensure the anchor is closed
                    inline_lineno = inline_lineno + "</a>"
                    lineno_achor = lineno_achor + "</a>"
                    # make the code as a link to the documentation
                    yield (
                        is_line,
                        f'<a class="viewcode-back" href="{self.lineno_href[lineno]}">[docs]</a>{line_html}',
                    )
                else:
                    yield is_line, f"{line_html}"
            else:
                yield is_line, line_html


def html_wrapper(filepath: Path, lineno_href: dict[int, str]) -> str:
    code = filepath.read_text()

    formatter = LineFormatter(
        lineno_href=lineno_href,
        # use inline, as table may make lineno and code misaligned with certain Sphinx themes
        linenos="inline",
        lineanchors="L",  # Adds anchor IDs like id="L-20"
        anchorlinenos=True,  # Makes line numbers clickable (link to #L-20)
        wrapcode=False,  # Wraps the code in a <div> with class "highlight"
    )

    html_content: str = highlight(code, CLexer(stripnl=False), formatter)
    return html_content
