"""The worked examples of the per-type configuration docs, kept true.

Two documentation pages include these projects with ``literalinclude`` and quote what
their builds report: the section "Per-type configuration or schema rules?" of
``docs/schema/index.rst`` (``doc_test/doc_schema_per_type``) and the how-to
``docs/need_types.rst`` (``doc_test/doc_need_types``). Each test pins the whole warning
list of its project and the needs the build keeps, so a change in what a need type's
entry does turns a test red before the pages quoting it go stale.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings


def _needs_json(app: SphinxTestApp) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]


def _schema_record(
    head: str, *, severity: str, field: str | None, need_path: str, rest: list[str]
) -> str:
    """One schema finding as ``build_warnings`` gives it: a head line, then the details."""
    lines = [head, f"  Severity:       {severity}"]
    if field is not None:
        lines.append(f"  Field:          {field}")
    lines.append(f"  Need path:      {need_path}")
    return "\n".join([*lines, *rest])


SCHEMA_PER_TYPE_WARNINGS = [
    # While reading: the structural declarations, with the source location.
    "<srcdir>/index.rst:17: WARNING: Need could not be created: Field 'asil' is not "
    "nullable, but no value or default was given. [needs.create_need]",
    "<srcdir>/index.rst:27: WARNING: Link type 'verifies' is not declared on need type "
    "'spec' and cannot be set in need 'S_003'; the value 'R_001' is ignored "
    "[needs.undeclared_for_type]",
    # The need that was not created is a dead link target.
    "<srcdir>/index.rst:43: WARNING: Need 'T_004' has unknown outgoing link 'SR_002' "
    "in field 'verifies' [needs.link_outgoing]",
    # The schema pass: the type entries' constraint keywords and the schema rules.
    _schema_record(
        "ERROR: Need 'R_002' has schema violations:",
        severity="violation",
        field="status",
        need_path="R_002",
        rest=[
            "  Schema path:    fields > schema > properties > status > enum",
            '  Schema message: "done" is not one of "draft" or "approved" '
            "[sn_schema_violation.field_fail]",
        ],
    ),
    _schema_record(
        "WARNING: Need 'R_002' has schema warnings:",
        severity="warning",
        field=None,
        need_path="R_002",
        rest=[
            "  Schema path:    req-has-asil[0] > local > required",
            "  User message:   a requirement states its ASIL",
            '  Schema message: "asil" is a required property '
            "[sn_schema_warning.local_fail]",
        ],
    ),
    # SR_001 is a safety_req: it has the status values of req through ``inherits``.
    _schema_record(
        "ERROR: Need 'SR_001' has schema violations:",
        severity="violation",
        field="status",
        need_path="SR_001",
        rest=[
            "  Schema path:    fields > schema > properties > status > enum",
            '  Schema message: "done" is not one of "draft" or "approved" '
            "[sn_schema_violation.field_fail]",
        ],
    ),
    _schema_record(
        "ERROR: Need 'S_001' has schema violations:",
        severity="violation",
        field="links",
        need_path="S_001",
        rest=[
            "  Schema path:    links > schema > properties > links > minItems",
            "  Schema message: [] has less than 1 item [sn_schema_violation.link_fail]",
        ],
    ),
    _schema_record(
        "ERROR: Need 'T_003' has schema violations:",
        severity="violation",
        field="verifies",
        need_path="T_003",
        rest=[
            "  Schema path:    links > schema > properties > verifies > minItems",
            "  Schema message: [] has less than 1 item [sn_schema_violation.link_fail]",
        ],
    ),
    _schema_record(
        "ERROR: Need 'S_002' has schema violations:",
        severity="violation",
        field="type",
        need_path="T_002 > verifies > S_002",
        rest=[
            "  Schema path:    test-verifies-req[1] > validate > network > verifies > "
            "items > local > properties > type > enum",
            '  Schema message: "spec" is not one of "req" or "safety_req" '
            "[sn_schema_violation.network_local_fail]",
        ],
    ),
    _schema_record(
        "ERROR: Need 'T_004' has schema violations:",
        severity="violation",
        field=None,
        need_path="T_004 > verifies",
        rest=[
            "  Schema path:    test-verifies-req[1] > validate > network > verifies",
            "  User message:   a test verifies requirements only",
            "  Schema message: Broken link of type 'verifies' to 'SR_002' "
            "[sn_schema_violation.network_missing_target]",
        ],
    ),
]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_schema_per_type"}],
    indirect=True,
)
def test_schema_per_type_example(test_app: SphinxTestApp) -> None:
    """The example of "Per-type configuration or schema rules?" reports what the page quotes.

    The two enforcement modes side by side: the structural declarations report while
    reading, with a location, and drop a value or the whole need (``SR_002``); the
    constraint keywords of a type entry report in the schema pass, beside the schema
    rules, and keep the need.
    """
    test_app.build()
    assert build_warnings(test_app) == SCHEMA_PER_TYPE_WARNINGS

    needs = _needs_json(test_app)["needs"]
    # SR_002 has no asil, which its type requires: it is not created at all.
    assert sorted(needs) == [
        "R_001",
        "R_002",
        "SR_001",
        "S_001",
        "S_002",
        "S_003",
        "T_001",
        "T_002",
        "T_003",
        "T_004",
    ]
    # The value of a link type the need's type does not declare is dropped.
    assert needs["S_003"]["verifies"] == []
    # A need the schema pass reports is kept, with its value.
    assert needs["R_002"]["status"] == "done"
    # A need of the type that sets no status takes the type's default.
    assert needs["R_001"]["status"] == "draft"


NEED_TYPES_WARNINGS = [
    "<srcdir>/index.rst:8: WARNING: Field 'verdict' is not declared on need type 'req' "
    "and cannot be set in need 'R_002'; the value 'passed' is ignored "
    "[needs.undeclared_for_type]",
    "<srcdir>/index.rst:25: WARNING: Need could not be created: Field 'hazard' is not "
    "nullable, but no value or default was given. [needs.create_need]",
    _schema_record(
        "ERROR: Need 'R_003' has schema violations:",
        severity="violation",
        field="status",
        need_path="R_003",
        rest=[
            "  Schema path:    fields > schema > properties > status > enum",
            '  Schema message: "done" is not one of "draft" or "approved" '
            "[sn_schema_violation.field_fail]",
        ],
    ),
    _schema_record(
        "ERROR: Need 'R_004' has schema violations:",
        severity="violation",
        field="tags.0",
        need_path="R_004",
        rest=[
            "  Schema path:    fields > schema > properties > tags > items > enum",
            '  Schema message: "security" is not one of "functional", "performance" '
            'or "safety" [sn_schema_violation.field_fail]',
        ],
    ),
    _schema_record(
        "ERROR: Need 'T_002' has schema violations:",
        severity="violation",
        field="verifies",
        need_path="T_002",
        rest=[
            "  Schema path:    links > schema > properties > verifies > minItems",
            "  Schema message: [] has less than 1 item [sn_schema_violation.link_fail]",
        ],
    ),
    # The unguarded filter, over a field only safety_req declares (None elsewhere).
    "<srcdir>/index.rst:51: WARNING: Filter 'hazard.startswith(\"loss\")' not valid. "
    "Error: 'NoneType' object has no attribute 'startswith'. [needs.filter]",
]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_need_types"}],
    indirect=True,
)
def test_need_types_example(test_app: SphinxTestApp) -> None:
    """The example of the "Modeling need types" how-to does what the page says.

    Pins the warnings the page quotes, the need its required field drops, the values the
    per-type defaults give (a subtype included), and what each of the three filters over
    a field of one type lists.
    """
    test_app.build()
    assert build_warnings(test_app) == NEED_TYPES_WARNINGS

    assert sorted(_needs_json(test_app)["needs"]) == [
        "R_001",
        "R_002",
        "R_003",
        "R_004",
        "SR_001",
        "T_001",
        "T_002",
    ]

    needs = SphinxNeedsData(test_app.env).get_needs_view()
    # Status values and defaults per type; a safety_req has the ones of a req.
    assert needs["R_001"]["status"] == "draft"
    assert needs["SR_001"]["status"] == "draft"
    assert needs["T_001"]["status"] == "open"
    # A field of tests alone: set on a test, dropped from a req, None on the others.
    assert needs["T_001"]["verdict"] == "passed"
    assert needs["R_002"]["verdict"] is None
    assert needs["SR_001"]["hazard"] == "loss of braking"
    assert needs["R_001"]["hazard"] is None
    # Per-type defaults of core fields; req's style default reaches its subtype.
    assert needs["R_001"]["style"] == "green_bar"
    assert needs["SR_001"]["style"] == "green_bar"
    assert needs["T_001"]["style"] is None
    assert needs["T_001"]["layout"] == "clean_l"
    assert needs["R_001"]["layout"] is None
    assert needs["T_001"]["collapse"] is True
    assert needs["R_001"]["collapse"] is False

    # Each of the three tables lists SR_001 alone: the unguarded filter warns once
    # and leaves out the needs it raised on, but still lists the ones it matched.
    html = Path(test_app.outdir, "index.html").read_text(encoding="utf-8")
    tables = re.findall(r'<table class="NEEDS_DATATABLES.*?</table>', html, re.DOTALL)
    assert [re.findall(r'data-need-id="([^"]+)"', table) for table in tables] == [
        ["SR_001"],
        ["SR_001"],
        ["SR_001"],
    ]


MISSPELT_TOML = """\
[needs]
build_json = true

[needs.types.safety_req]
title = "Safety requirement"
prefix = "SR_"

[needs.types.safety_req.fields.hazard]
schema = { type = "string" }

[needs.types.safety_req.fields.hazrd]
schema = { type = "string" }

[needs.types.safety_req.fields.hazzard]
description = "no schema type"
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs"]\nneeds_from_toml = "ubproject.toml"\n',
                ),
                (Path("ubproject.toml"), MISSPELT_TOML),
                (Path("index.rst"), "Case\n====\n"),
            ],
        }
    ],
    indirect=True,
)
def test_misspelt_field_of_a_type(test_app: SphinxTestApp) -> None:
    """The pitfall the how-to warns of: a misspelt field name in a type's ``fields``.

    With a ``schema`` ``type`` it silently declares a new field of the type; without one
    it is refused with a warning.
    """
    test_app.build()
    assert build_warnings(test_app) == [
        "WARNING: needs_types['safety_req'].fields['hazzard'] declares 'hazzard', which "
        "no needs_fields entry declares, and no need type without an ancestor declaring "
        "it gives it a 'schema' 'type'; the entry is ignored [needs.type_conflict]",
    ]
    properties = _needs_json(test_app)["needs_schema"]["properties"]
    assert properties["hazrd"]["description"] == "Declared by need types 'safety_req'"
    assert "hazzard" not in properties
