"""A ``needextend`` option whose dynamic or variant function cannot be parsed (#2109).

The directive converts each option value through its field's
``convert_directive_option``, which raises ``FunctionParsingException`` for a
malformed ``[[...]]`` and ``VariantParsingException`` for a malformed ``<<...>>``.
Either is one ``needs.needextend`` warning at the directive, naming the option and
the parse error, and that option is skipped -- as for a value that cannot be
converted -- while the directive's other options still apply. The directive itself is
still recorded and applied, so the need counts it as a modification, as it does for an
extend whose every option was skipped for a value that cannot be converted.

A ``need.<attr>`` argument is such a parse error at directive time: it is admitted
only where a need is in hand. Whether it should be admitted in a ``needextend`` value
is a separate question; these tests pin only that it no longer ends the build.
"""

from pathlib import Path
from typing import Any

import pytest
from sphinx.application import Sphinx

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.needs_schema import FieldLiteralValue
from sphinx_needs_testkit import build_warnings
from tests.util import needs_by_id

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
"""

VARIANT_CONF = CONF + 'needs_fields = {"status": {"parse_variants": True}}\n'

INDEX = """\
Index
=====

.. req:: A plain need
   :id: REQ_C
   :status: open

.. needextend:: REQ_C
{options}
"""

LOCATION = "<srcdir>/index.rst:8"

NEED_ARG = "Error parsing dynamic function 'copy': Unsupported arg 0 value type"

UNPARSABLE_CASES = [
    # (id, conf, option, value, message)
    ("need-arg", CONF, "status", "[[copy(need.id)]]", NEED_ARG),
    (
        "need-kwarg",
        CONF,
        "status",
        "[[copy(field=need.id)]]",
        "Error parsing dynamic function 'copy': Unsupported kwarg 'field' value type",
    ),
    (
        "not-a-call",
        CONF,
        "status",
        "[[not a call]]",
        "Error parsing dynamic function: Not a function call",
    ),
    ("link", CONF, "links", "[[copy(need.id)]]", NEED_ARG),
    ("append", CONF, "+status", "[[copy(need.id)]]", NEED_ARG),
    (
        "variant",
        VARIANT_CONF,
        "status",
        "<<[x>>",
        "Error parsing variant function: Unclosed variant expression: [x",
    ),
    # the precedent: a value that cannot be converted, reported and skipped the same way
    ("value-error", CONF, "hide", "bad", "Cannot convert 'bad' to boolean"),
]


def _files(conf: str, *options: str) -> list[tuple[Path, str]]:
    return [
        (Path("conf.py"), conf),
        (Path("index.rst"), INDEX.format(options="\n".join(options))),
    ]


def recorded_modifications(app: Sphinx) -> list[tuple[list[Any], list[Any]]]:
    """The field and link modifications each recorded ``needextend`` carries."""
    extends = SphinxNeedsData(app.env).get_or_create_extends()
    return [
        (extend["modifications"], extend["list_modifications"])
        for extend in extends.values()
    ]


@pytest.mark.parametrize(
    ("test_app", "option", "message"),
    [
        pytest.param(
            {"buildername": "html", "files": _files(conf, f"   :{option}: {value}")},
            option,
            message,
            id=case_id,
        )
        for case_id, conf, option, value, message in UNPARSABLE_CASES
    ],
    indirect=["test_app"],
)
def test_unparsable_function_is_reported_and_not_applied(
    test_app: Sphinx, option: str, message: str
):
    """The option is one ``needs.needextend`` warning, and the need keeps its value."""
    app = test_app
    app.build()
    assert app.statuscode == 0

    assert build_warnings(app) == [
        f"{LOCATION}: WARNING: Invalid value for '{option}' option: {message} "
        "[needs.needextend]"
    ]
    assert recorded_modifications(app) == [([], [])]
    need = needs_by_id(app)["REQ_C"]
    assert need["status"] == "open"
    assert need["links"] == []
    assert need["is_modified"] is True
    assert need["modifications"] == 1


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": _files(CONF, "   :status: [[copy(need.id)]]", "   :tags: a"),
        }
    ],
    indirect=True,
)
def test_other_options_of_the_directive_still_apply(test_app: Sphinx):
    """Only the option that cannot be parsed is skipped, not the whole directive."""
    app = test_app
    app.build()
    assert app.statuscode == 0

    assert build_warnings(app) == [
        f"{LOCATION}: WARNING: Invalid value for 'status' option: {NEED_ARG} "
        "[needs.needextend]"
    ]
    assert [
        [(key, value) for key, _etype, value in modifications]
        for modifications, _links in recorded_modifications(app)
    ] == [[("tags", FieldLiteralValue(["a"]))]]
    need = needs_by_id(app)["REQ_C"]
    assert need["status"] == "open"
    assert need["tags"] == ["a"]
    assert need["is_modified"] is True
    assert need["modifications"] == 1


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "files": _files(CONF, '   :status: [[copy("id")]]')}],
    indirect=True,
)
def test_function_without_need_argument_still_applies(test_app: Sphinx):
    """Control: a dynamic function that parses is applied as before."""
    app = test_app
    app.build()
    assert app.statuscode == 0

    assert build_warnings(app) == []
    need = needs_by_id(app)["REQ_C"]
    assert need["status"] == "REQ_C"
    assert need["is_modified"] is True
    assert need["modifications"] == 1


OWN_OPTION_INDEX = """\
Index
=====

.. req:: A plain need
   :id: REQ_C
   :status: [[copy(need.id)]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), OWN_OPTION_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_same_value_in_the_needs_own_option(test_app: Sphinx):
    """Control: in a need's own option the parse error is a ``needs.create_need`` warning.

    The need is not created; this path was never a crash, and is unchanged.
    """
    app = test_app
    app.build()
    assert app.statuscode == 0

    assert build_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: Need could not be created: "
        f"'status' value is invalid: {NEED_ARG} [needs.create_need]"
    ]
    assert "REQ_C" not in needs_by_id(app)
