"""Parse one need's content in a declared markup, into the host document.

``add_need(content_markup=...)`` comes here instead of the host state's own
``nested_parse``: the content is parsed by the parser the project registers for that
source suffix -- reStructuredText or MyST Markdown -- whatever the page's own parser is.

Both routes bind the content to the HOST document (``state.document``), never to a fresh
one, so a label written in the content registers with the page it is rendered on, and a
duplicate of a page label gets docutils' own ``Duplicate explicit target name`` warning.
Every docutils-level diagnostic raised while parsing the content, and every node created
from it, names the file and line the content was written on.

The content's lines are itemised as ``(source, first_line - 1 + i)`` (docutils items are
0-based), and the parse runs inside ``sphinx.util.docutils.switch_source_input``, which
points the reporter's line lookup at those items for the duration and restores it after:
the same mechanism ``sphinx.ext.autodoc`` uses to report a docstring's lines at the
Python file.

* **reStructuredText in a reStructuredText page**: autodoc's pattern as it is, the page
  state's own ``nested_parse``.
* **reStructuredText in a MyST page**: a MyST page's ``nested_parse`` renders Markdown,
  and no Sphinx or docutils API runs the RST parser into a node of an existing document
  without an RST state, so this one piece is built by hand: a nested state machine and a
  memo against the page's document, with the fields ``RSTStateMachine.run`` gives its own.
* **MyST**: a fresh myst-parser renderer bound to the host document renders the text at
  myst's own line offset, with ``document["source"]`` naming the content's file for the
  duration (it is what myst-parser writes on the nodes it creates). myst-parser reports
  at the content's own line, so the items it looks up are indexed by that line.

The page's ``document.current_source``/``current_line``, which a nested RST state machine
moves to the content's file as it reads, are put back afterwards. Measured with Sphinx
7.4.7 and 9.1, docutils 0.21.2 and 0.22.4, myst-parser 4.0.1 and 5.1.0.

Deliberately not done here (yet): no ``file_insertion_enabled``/``raw_enabled``
restrictions, no fence against need or ``needimport`` directives in the content, no
post-parse walk for MyST raw HTML or images, and no rewriting of the locations of the
warnings myst-parser logs itself (those name the host page, with the content's line).
"""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace
from typing import TYPE_CHECKING, Literal, cast

from docutils import nodes
from docutils.parsers import Parser
from docutils.parsers.rst import Parser as RstParser
from docutils.parsers.rst import languages, states
from docutils.parsers.rst.states import RSTState
from docutils.statemachine import StringList
from sphinx.util.docutils import switch_source_input

from sphinx_needs.exceptions import InvalidNeedException

if TYPE_CHECKING:
    from sphinx.application import Sphinx

ContentRoute = Literal["rst", "myst"]


def _myst_parser_class() -> type[Parser] | None:
    """myst-parser's Sphinx parser class, or ``None`` if myst-parser is not installed."""
    try:
        from myst_parser.parsers.sphinx_ import (  # ty: ignore[unresolved-import]
            MystParser,
        )
    except ImportError:
        return None
    return MystParser


def content_route(parser: type[Parser]) -> ContentRoute | None:
    """Which route parses content for ``parser``, or ``None`` if neither can."""
    if issubclass(parser, RstParser):
        return "rst"
    myst = _myst_parser_class()
    if myst is not None and issubclass(parser, myst):
        return "myst"
    return None


def resolve_content_parser(app: Sphinx, content_markup: str) -> type[Parser]:
    """Resolve a source suffix to the parser class the project registers for it.

    :param app: The Sphinx application.
    :param content_markup: A source suffix, such as ``".rst"`` or ``".md"``.
    :raises InvalidNeedException: If the suffix is not registered, its file type has no
        parser, or the parser is neither a reStructuredText nor a MyST parser.
    """
    suffixes = app.registry.source_suffix
    registered = ", ".join(repr(s) for s in sorted(suffixes))
    supported = "only reStructuredText and MyST parsers are supported"
    filetype = suffixes.get(content_markup)
    if filetype is None:
        raise InvalidNeedException(
            "content_markup",
            f"Content markup {content_markup!r} is not a registered source suffix "
            f"(registered: {registered}); {supported}.",
        )
    parser = app.registry.source_parsers.get(filetype)
    if parser is None:
        raise InvalidNeedException(
            "content_markup",
            f"Content markup {content_markup!r} maps to file type {filetype!r}, "
            f"which has no registered parser (registered suffixes: {registered}); "
            f"{supported}.",
        )
    if content_route(parser) is None:
        raise InvalidNeedException(
            "content_markup",
            f"Content markup {content_markup!r} is parsed by "
            f"{parser.__module__}.{parser.__qualname__} "
            f"(registered suffixes: {registered}); {supported}.",
        )
    return parser


def parse_need_content(
    state: RSTState,
    lines: Sequence[str],
    *,
    parser: type[Parser],
    source: str,
    first_line: int,
    node: nodes.Element,
) -> None:
    """Parse a need's content with ``parser``, appending the result to ``node``.

    :param state: The host document's parser state (an RST state, or myst-parser's).
    :param lines: The content, one entry per source line.
    :param parser: The parser class resolved for the content's markup
        (:func:`resolve_content_parser`).
    :param source: The file the content lines come from.
    :param first_line: The 1-based line of the first content line in ``source``.
    :param node: The node to append the parsed content to.
    """
    route = content_route(parser)
    if route == "rst":
        _parse_rst(state, lines, source=source, first_line=first_line, node=node)
    elif route == "myst":
        _parse_myst(state, lines, source=source, first_line=first_line, node=node)
    else:  # resolve_content_parser refuses these before the need is recorded
        raise ValueError(f"Unsupported content parser: {parser!r}")


def _parse_rst(
    state: RSTState,
    lines: Sequence[str],
    *,
    source: str,
    first_line: int,
    node: nodes.Element,
) -> None:
    document = state.document
    block = StringList(
        list(lines), items=[(source, first_line - 1 + i) for i in range(len(lines))]
    )
    # the nested machine notes every line it reads on the document (``note_source``);
    # put back what the page had, so the nodes created after the content (the need's
    # own among them) do not take the content's file
    current = (document.current_source, document.current_line)
    try:
        if isinstance(state, RSTState):
            # what ``sphinx.ext.autodoc`` does with a docstring's lines
            with switch_source_input(state, block):
                state.nested_parse(block, 0, node, match_titles=False)
        else:
            _parse_rst_in_myst_page(state, block, node)
    finally:
        document.current_source, document.current_line = current


def _parse_rst_in_myst_page(
    state: RSTState, block: StringList, node: nodes.Element
) -> None:
    """Run the reStructuredText parser on ``block``, into a node of a MyST page.

    A MyST page's ``state.nested_parse`` renders Markdown, and no Sphinx or docutils
    API runs the RST parser into a node of an existing document without an RST state:
    so this builds the nested state machine, and a memo against the page's document
    with the fields ``RSTStateMachine.run`` gives its own.
    """
    document = state.document
    inliner = states.Inliner()
    inliner.init_customizations(document.settings)
    memo = SimpleNamespace(
        document=document,
        reporter=document.reporter,
        language=languages.get_language(
            document.settings.language_code, document.reporter
        ),
        title_styles=[],
        section_level=0,
        section_bubble_up_kludge=False,
        inliner=inliner,
    )
    machine = states.NestedStateMachine(states.state_classes, "Body")
    try:
        with switch_source_input(state, block):
            machine.run(block, 0, memo=memo, node=node, match_titles=False)
    finally:
        machine.unlink()


def _parse_myst(
    state: RSTState,
    lines: Sequence[str],
    *,
    source: str,
    first_line: int,
    node: nodes.Element,
) -> None:
    # myst-parser is an optional dependency, and not in the type-checking environment
    from myst_parser.mdit_to_docutils.sphinx_ import (  # ty: ignore[unresolved-import]
        SphinxRenderer,
    )
    from myst_parser.parsers.mdit import (  # ty: ignore[unresolved-import]
        create_md_parser,
    )

    document = state.document
    env = document.settings.env
    # a fresh renderer rather than a MyST page's own: one path for both hosts, and the
    # content gets its own markdown-it env (its reference-link definitions)
    md = create_md_parser(env.myst_config, SphinxRenderer)
    renderer = cast(SphinxRenderer, md.renderer)
    renderer.setup_render(
        {**md.options, "document": document, "current_node": node}, {}
    )
    # myst-parser reports at the line it renders a token at, here the content's own
    # line in ``source``, so the lines the reporter looks up are indexed by it: the
    # content's lines after ``first_line - 1`` placeholders
    block = StringList(
        [""] * (first_line - 1) + list(lines),
        items=[(source, i) for i in range(first_line - 1 + len(lines))],
    )
    previous_source = document["source"]
    # what myst-parser writes on the nodes it creates
    document["source"] = source
    try:
        with switch_source_input(state, block):
            # myst's offset is 0-based: a token on the text's first line gets
            # ``first_line``
            renderer.nested_render_text("\n".join(lines), first_line - 1)
    finally:
        document["source"] = previous_source
