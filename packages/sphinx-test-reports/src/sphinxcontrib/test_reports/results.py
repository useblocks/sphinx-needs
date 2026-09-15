"""The vocabulary of the ``result`` field, and the one place it is decided.

Every state a test case can be in is spelled as a participle: ``passed``,
``failed``, ``error``, ``skipped``, ``disabled``. That is one decision applied
to two parsers, which is the point of this module -- before it, ``result`` was
whatever the input happened to call it. The JUnit parser passed the name of the
result-carrying ``<testcase>`` child through verbatim, so a failure was
``failure`` after the ``<failure>`` element, while the two states with no
element of their own were invented as participles (``passed``, and ``disabled``
for googletest's ``status="notrun"``). The JSON parser passed its report's own
value through untouched. So the same outcome could arrive under two spellings,
and a single test case was ``failure`` while the count of them on its suite was
``failed`` (:data:`~sphinxcontrib.test_reports.fields.FIELDS`).

``error`` stays a noun-state deliberately: it agrees with the ``errors`` count
beside it and with pytest, which spells that outcome ``error`` too. The pair
that disagreed was ``failure``/``failed``, and ``failed`` is the half that
already appeared in a field name.

**Nothing in this module may import Sphinx.** Both parsers run under the
``test-reports`` command, as a build action without the documentation
toolchain installed.
"""

#: Every value the parsers of this package put into ``result``. A documented
#: field value: a project filters on it (``'failed' == result``), the
#: directives turn it into the CSS class that colours a need and a table row
#: (``tr_failed``), and the converter writes it into ``needs.json`` for
#: consumers that never load this extension.
#:
#: A tuple, in the order a reader wants them rather than alphabetically:
#: :func:`~sphinxcontrib.test_reports.fields.declaration` renders it into the
#: declared description of the field, and the converter's output has to be
#: byte-stable, which a set's iteration order is not.
CANONICAL_RESULTS: tuple[str, ...] = (
    "passed",
    "failed",
    "error",
    "skipped",
    "disabled",
)

#: ``as read -> canonical``, for the input spellings that are not already the
#: vocabulary above. Only spellings some input really produces are listed, so
#: that a state this package does not know -- ``tr_json_mapping`` points at an
#: arbitrary report, whose states are its own -- survives untouched instead of
#: being rewritten into something a project's filters no longer match.
RESULT_ALIASES: dict[str, str] = {
    # The name of the JUnit ``<failure>`` element, which the JUnit parser reads
    # a case's result from, and which a JSON report written against the same
    # dialect uses as its value.
    "failure": "failed",
}


def normalize_result(result: str) -> str:
    """*result* in the vocabulary of :data:`CANONICAL_RESULTS`.

    Idempotent, and total: a value already canonical and a value this package
    does not know are both returned unchanged, so the function can be applied
    wherever a result is read without having to know where it came from.
    """
    return RESULT_ALIASES.get(result, result)
