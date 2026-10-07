"""A ``needextend`` option whose dynamic or variant function cannot be parsed (#2109).

The directive converts each option value through its field's
``convert_directive_option``, which raises ``FunctionParsingException`` for a
malformed ``[[...]]`` and ``VariantParsingException`` for a malformed ``<<...>>``.
Either is one ``needs.needextend`` warning at the directive, naming the option and
the parse error, and that option is skipped -- as for a value that cannot be
converted -- while the directive's other options still apply. The directive itself is
still recorded and applied, so the need counts it as a modification, as it does for an
extend whose every option was skipped for a value that cannot be converted.

A ``need.<attr>`` argument was such a parse error until 9.0.0, which admits it in
field and link values, a ``needextend``'s included: the value is applied, and the call
resolves against the need it is set on.
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

LINK_VARIANT_CONF = CONF + 'needs_links = {"blocks": {"parse_variants": True}}\n'

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

NOT_A_CALL = "Error parsing dynamic function: Not a function call"

UNPARSABLE_CASES = [
    # (id, conf, option, value, message)
    ("not-a-call", CONF, "status", "[[not a call]]", NOT_A_CALL),
    ("link", CONF, "links", "[[not a call]]", NOT_A_CALL),
    ("append", CONF, "+status", "[[not a call]]", NOT_A_CALL),
    (
        "variant",
        VARIANT_CONF,
        "status",
        "<<[x>>",
        "Error parsing variant function: Unclosed variant expression: [x",
    ),
    (
        "link-variant",
        LINK_VARIANT_CONF,
        "blocks",
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
            "files": _files(CONF, "   :status: [[not a call]]", "   :tags: a"),
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
        f"{LOCATION}: WARNING: Invalid value for 'status' option: {NOT_A_CALL} "
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


NEED_ATTR_CONF = CONF + 'needs_fields = {"source": {"nullable": True}}\n'

NEED_ATTR_INDEX = """\
Index
=====

.. req:: A plain need
   :id: REQ_C
   :status: open
   :source: REQ_D

.. req:: Linked
   :id: REQ_D
   :links: REQ_C

.. needextend:: REQ_C
{options}
"""


@pytest.mark.parametrize(
    ("test_app", "field", "value"),
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), NEED_ATTR_CONF),
                    (Path("index.rst"), NEED_ATTR_INDEX.format(options=option)),
                ],
            },
            field,
            value,
            id=case_id,
        )
        for case_id, option, field, value in [
            (
                "need-arg",
                '   :status: [[copy("title", need.source)]]',
                "status",
                "Linked",
            ),
            (
                "need-kwarg",
                '   :status: [[copy("title", need_id=need.source)]]',
                "status",
                "Linked",
            ),
            ("link", '   :links: [[copy("links", need.source)]]', "links", ["REQ_C"]),
            (
                "append",
                '   :+status: [[copy("title", need.source)]]',
                "status",
                "open Linked",
            ),
        ]
    ],
    indirect=["test_app"],
)
def test_need_attribute_is_applied_and_resolves(test_app: Sphinx, field: str, value):
    """A ``need.<field>`` argument parses, so the option is applied, and the call resolves.

    ``need.source`` names the need the call reads, on the need the extend modifies.
    """
    app = test_app
    app.build()
    assert app.statuscode == 0

    assert build_warnings(app) == []
    need = needs_by_id(app)["REQ_C"]
    assert need[field] == value
    assert need["is_modified"] is True
    assert need["modifications"] == 1


OWN_OPTION_INDEX = """\
Index
=====

.. req:: A plain need
   :id: REQ_C
   :status: [[copy("title", need.id)]]
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
    """Control: in a need's own option a ``need.<field>`` argument is admitted too.

    The need is created and the call resolves (until 9.0.0 the need was not created,
    with a ``needs.create_need`` warning).
    """
    app = test_app
    app.build()
    assert app.statuscode == 0

    assert build_warnings(app) == []
    assert needs_by_id(app)["REQ_C"]["status"] == "A plain need"
