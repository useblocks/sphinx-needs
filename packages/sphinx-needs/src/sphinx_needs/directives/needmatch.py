"""Directives for including one of several branches of content based on variant data.

A ``match`` holds ``case`` directives and comments, written in its own body,
and nothing else.
The first ``case`` whose condition holds is included;
a ``case`` with no condition is the default, and must be the last.

A ``case`` does not parse its content.
Inside a ``match`` body it returns a transient :class:`_CasePlaceholder`
carrying its condition and its raw content,
and the ``match`` parses its own body into a detached :class:`_MatchBody`
that it never returns.
Having seen every case at once, the ``match`` checks the structure,
evaluates the conditions in order with the evaluator of the ``if`` directive
(:func:`~sphinx_needs.directives.needif.evaluate_variant_condition`),
and parses only the content of the case it takes, returning those nodes.
So the content of every other case is never parsed:
the needs in it are never created and its mistakes are never reported,
exactly as for the body of a false ``if``.

Neither node class reaches a doctree or the need-node cache,
so neither is registered with Sphinx:
one that ever escaped would make a writer fail loudly rather than render silently.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import islice

from docutils import nodes
from docutils.parsers.rst.states import RSTState
from docutils.statemachine import StringList
from docutils.utils import Reporter, get_source_line
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import nested_parse_with_titles

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needif import evaluate_variant_condition
from sphinx_needs.logging import get_logger, log_warning

LOGGER = get_logger(__name__)

_DEPTH_KEY = "sphinx_needs_match_depth"
"""The ``env.temp_data`` key counting the ``match`` bodies being parsed.

A ``case`` is a child of a ``match`` body exactly when the count is above 0.
A ``match`` raises it only around the parse of its own body,
and parses the content of the case it takes at 0,
so a ``case`` written loose in a case's content is reported as well.
"""


class _CasePlaceholder(nodes.Element):
    """What a ``case`` leaves in the body of its ``match``; it never reaches a doctree.

    The payload is held in plain Python attributes rather than docutils attributes:
    the ``match`` reads it once and discards it with the body.
    """

    condition: str | None
    """The condition, or ``None`` for the default case."""
    content: StringList
    """The raw content of the case, parsed only if the case is taken."""
    content_offset: int
    """The ``content_offset`` of the ``case`` directive."""
    lineno: int
    """The ``lineno`` of the ``case`` directive."""
    location: str | None
    """Where warnings about the case are reported."""
    source: str | None
    """The file the ``case`` directive is written in, as docutils or MyST reports it."""
    owner: nodes.Element | None
    """The node the ``case`` directive's result is appended to.

    That is the body of its ``match`` exactly when the ``case`` is written directly in it,
    rather than inside another directive whose content was parsed into a node of its own.
    """


class _MatchBody(nodes.Element):
    """The detached node a ``match`` parses its own body into; it is never returned."""


class CaseDirective(SphinxDirective):
    """One branch of a ``match``, included if it is the first whose condition holds.

    The directive argument is a condition, exactly as for the ``if`` directive;
    a ``case`` with no argument is the default of its ``match``.
    Its content is not parsed here: the ``match`` parses it if it takes the case.

    Example::

        .. match::

           .. case:: var.arch == "arm"

              ARM content.

           .. case::

              Content for every other architecture.
    """

    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True
    has_content = True

    def run(self) -> Sequence[nodes.Node]:
        if self.env.temp_data.get(_DEPTH_KEY, 0) <= 0:
            log_warning(
                LOGGER,
                "'case' directive outside a 'match' (a 'case' must be a direct child "
                "of a 'match'); its content is skipped",
                "match",
                location=self.get_location(),
            )
            return []

        placeholder = _CasePlaceholder()
        # an argument of only whitespace is no condition: the default case
        has_condition = bool(self.arguments and self.arguments[0].strip())
        placeholder.condition = self.arguments[0] if has_condition else None
        placeholder.content = self.content
        placeholder.content_offset = self.content_offset
        placeholder.lineno = self.lineno
        placeholder.location = self.get_location()
        placeholder.source = self.get_source_info()[0]
        # docutils' `RSTState.parent` is this very node, and MyST's mock state machine
        # holds the renderer's current node here, which is where MyST appends the result
        placeholder.owner = self.state_machine.node
        return [placeholder]


class MatchDirective(SphinxDirective):
    """Include the content of the first ``case`` whose condition holds.

    The content may hold only ``case`` directives and comments.
    Every mistake is warned about once, and skips the whole ``match``:
    content that is neither a ``case`` nor a comment, a ``case`` inside another
    directive or supplied through an include,
    a default ``case`` that is not the last or is not the only one,
    variant data that is not configured,
    and a condition that cannot be evaluated before a case is taken.
    So a mistake that makes a condition unevaluable, such as a misspelt key
    or a syntax error, never renders a later case or the default in its place.

    Example::

        .. match::

           .. case:: var.arch == "arm"

              ARM content.

           .. case:: var.arch == "x86"

              x86 content.

           .. case::

              Content for every other architecture.
    """

    required_arguments = 0
    # reserved, and refused: with no argument declared, MyST would move the text into
    # the content and docutils would reject the directive, so neither could say why
    optional_arguments = 1
    final_argument_whitespace = True
    has_content = True

    def run(self) -> Sequence[nodes.Node]:
        if self.arguments and self.arguments[0].strip():
            self._warn(
                f"'match' directive takes no argument, got {self.arguments[0]!r} "
                "(write a condition on each 'case'); the whole match is skipped"
            )
            return []

        cases = self._collect_cases(self.get_source_info()[0])
        if cases is None:
            return []

        if NeedsSphinxConfig(self.env.config).variant_data_proxy is None:
            self._warn(
                "'match' directive used but needs_variant_data is not configured; "
                "the whole match is skipped"
            )
            return []

        for case in cases:
            if case.condition is None:
                return self._parse_case(case)
            taken = evaluate_variant_condition(
                self.env,
                case.condition,
                directive="case",
                subtype="match",
                location=case.location,
            )
            if taken is None:
                # poisoned: no later case is evaluated or taken, the default included
                return []
            if taken:
                # the first case that holds wins; the later ones are not evaluated
                return self._parse_case(case)
        return []

    def _warn(self, message: str, location: str | nodes.Node | None = None, /) -> None:
        log_warning(
            LOGGER,
            message,
            "match",
            location=self.get_location() if location is None else location,
        )

    def _parse_body(self) -> _MatchBody:
        """Parse the content into a detached node, with every ``case`` deferred.

        Because the content of every case is deferred,
        a need created while the body is parsed can only come from content
        written outside a case, which is a mistake that skips the whole ``match``:
        such needs are removed again, so that the mistake creates none.

        :return: The parsed body.
        """
        body = _MatchBody()
        body.document = self.state.document

        data = SphinxNeedsData(self.env)
        # outside the read phase no need can be added, so there is nothing to undo
        needs = None if data.needs_is_post_processed else data.get_needs_mutable()
        before = 0 if needs is None else len(needs)

        temp_data = self.env.temp_data
        depth = temp_data.get(_DEPTH_KEY, 0)
        temp_data[_DEPTH_KEY] = depth + 1
        try:
            self.state.nested_parse(self.content, self.content_offset, body)
        finally:
            temp_data[_DEPTH_KEY] = depth

        if needs is not None and len(needs) > before:
            # the newest entries are the ones the body added: O(new needs)
            for need_id in list(islice(reversed(needs), len(needs) - before)):
                data.remove_need(need_id)

        return body

    def _collect_cases(self, source: str | None, /) -> list[_CasePlaceholder] | None:
        """Parse the body and check its structure.

        The cases must be written in the body itself:
        a ``case`` inside another directive (one whose content is parsed into a node
        of its own, even if it then returns that node's children, such as a true ``if``)
        is refused, and so is a ``case`` an ``.. include::`` supplies,
        so that one ``match`` is one directive in one file.

        :param source: The file this ``match`` is written in,
            as its cases report theirs.
        :return: The cases, in order,
            or ``None`` if the body is not a valid ``match`` (a warning has been emitted).
        """
        body = self._parse_body()
        children = list(body.children)
        cases: list[_CasePlaceholder] = []
        for index, child in enumerate(children):
            if isinstance(child, _CasePlaceholder):
                # the source first: a case an include supplies is reported as such,
                # also when the include stands inside another directive
                if child.source != source:
                    self._warn(
                        "'case' supplied through an include is not supported (write "
                        "the cases in the body of the 'match'); the whole match is "
                        "skipped",
                        child.location,
                    )
                    return None
                if child.owner is not body:
                    self._warn(
                        "'case' directive is not a direct child of its 'match' (it is "
                        "inside another directive); the whole match is skipped",
                        child.location,
                    )
                    return None
                cases.append(child)
            elif isinstance(child, nodes.comment):
                continue
            elif isinstance(child, nodes.system_message):
                reported = max(
                    self.state.document.reporter.report_level, Reporter.WARNING_LEVEL
                )
                if child["level"] < reported:
                    # never shown as a problem (below the report level, or below WARNING
                    # however low that level is set): judge what follows it instead
                    # (docutils puts an INFO before the paragraph of a `---` line)
                    continue
                # reported by docutils or MyST when it was created: skip, silently
                return None
            else:
                offender = self._offender(children[index:])
                tagname = (
                    offender.tagname if isinstance(offender, nodes.Element) else "#text"
                )
                self._warn(
                    "'match' directive may contain only 'case' directives and "
                    f"comments, got <{tagname}>; the whole match is skipped",
                    self._location_of(children[index:]),
                )
                return None

        if not cases:
            self._warn("'match' directive has no 'case'")
            return None

        defaults = [case for case in cases if case.condition is None]
        if len(defaults) > 1:
            self._warn(
                "'match' directive has more than one default 'case' (a 'case' with "
                "no condition); the whole match is skipped",
                defaults[1].location,
            )
            return None
        if defaults and defaults[0] is not cases[-1]:
            self._warn(
                "'match' directive has a default 'case' (a 'case' with no condition) "
                "that is not its last 'case'; the whole match is skipped",
                defaults[0].location,
            )
            return None

        return cases

    @staticmethod
    def _offender(candidates: Sequence[nodes.Node]) -> nodes.Node:
        """The node a warning about the first of ``candidates`` names.

        A need directive emits a target before the need,
        which carries no line and is nothing the author wrote:
        such leading targets are passed over, so that the warning names the need.

        :param candidates: The offending child and the children after it.
        """
        for node in candidates:
            if isinstance(node, nodes.target) and not get_source_line(node)[1]:
                continue
            if isinstance(node, _CasePlaceholder | nodes.comment):
                break
            return node
        return candidates[0]

    def _location_of(self, candidates: Sequence[nodes.Node]) -> nodes.Node | str | None:
        """Where to report the first of ``candidates``.

        That is the first node, in or under them, that knows its source and line:
        the body is detached, so no node can inherit them from an ancestor,
        and some nodes carry none of their own
        (such as the target a need directive emits before the need).

        :param candidates: The offending child and the children after it.
        :return: That node, or the location of the ``match`` if none has both.
        """
        for candidate in candidates:
            for node in candidate.findall(nodes.Element):
                source, line = get_source_line(node)
                if source and line:
                    return node
        return self.get_location()

    def _parse_case(self, case: _CasePlaceholder) -> list[nodes.Node]:
        """Parse the content of the case that is taken, with section titles allowed.

        It is parsed outside every ``match`` body (at depth 0),
        whatever encloses this ``match``,
        so that a ``case`` written loose in it is reported rather than collected.

        :param case: The case that is taken.
        :return: The parsed nodes.
        """
        node = nodes.container()
        node.document = self.state.document
        temp_data = self.env.temp_data
        depth = temp_data.get(_DEPTH_KEY, 0)
        temp_data[_DEPTH_KEY] = 0
        try:
            nested_parse_with_titles(
                self.state, case.content, node, self._content_offset_of(case)
            )
        finally:
            temp_data[_DEPTH_KEY] = depth
        return node.children

    def _content_offset_of(self, case: _CasePlaceholder) -> int:
        """The offset at which this directive's state parses the content of ``case``.

        Under docutils a directive's ``content_offset`` is absolute in the input,
        so the case's own offset is valid for any state.
        Under MyST it is relative to the directive's own line
        (the mock state adds the line it was created at),
        so it is re-based from the case's line onto this directive's line.

        :param case: The case that is taken.
        """
        if isinstance(self.state, RSTState):
            return case.content_offset
        return case.lineno - self.lineno + case.content_offset
