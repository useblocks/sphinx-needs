import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx import version_info as sphinx_version
from sphinx.testing.util import SphinxTestApp
from syrupy.filters import props

from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs_testkit import assert_no_warnings, build_warnings

CURR_DIR = Path(__file__).parent


@pytest.mark.fixture_file(
    "schema/fixtures/config.yml",
)
def test_schema_config(
    tmpdir: Path,
    content: dict[str, Any],
    make_app: Callable[[], SphinxTestApp],
    write_fixture_files: Callable[[Path, dict[str, Any]], None],
    snapshot,
) -> None:
    # Check if test should be skipped based on min_python version
    if "mark" in content and "min_python" in content["mark"]:
        min_version = tuple(content["mark"]["min_python"])
        if sys.version_info < min_version:
            pytest.skip(
                f"Test requires Python {'.'.join(map(str, min_version))} or higher"
            )
    write_fixture_files(tmpdir, content)
    with pytest.raises(NeedsConfigException) as excinfo:
        app = make_app(srcdir=Path(tmpdir), freshenv=True)
        app.build()
    assert str(excinfo.value) == snapshot


@pytest.mark.fixture_file(
    "schema/fixtures/links.yml",
    "schema/fixtures/fields.yml",
    "schema/fixtures/network.yml",
    "schema/fixtures/reporting.yml",
    "schema/fixtures/unevaluated.yml",
)
def test_schemas(
    tmpdir: Path,
    content: dict[str, Any],
    make_app: Callable[[], SphinxTestApp],
    write_fixture_files: Callable[[Path, dict[str, Any]], None],
    snapshot,
) -> None:
    write_fixture_files(tmpdir, content)

    app: SphinxTestApp = make_app(srcdir=Path(tmpdir), freshenv=True)
    app.build()

    assert app.statuscode == 0
    warnings_text = "\n".join(build_warnings(app))
    assert warnings_text == snapshot

    schema_violations: dict[str, Any] = json.loads(
        Path(app.outdir, "schema_violations.json").read_text("utf8")
    )
    exclude_keys = {"validated_needs_per_second", "validation_summary"}
    for key in exclude_keys:
        schema_violations.pop(key, None)
    assert schema_violations == snapshot
    app.cleanup()


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/schema_typing"}],
    indirect=True,
)
def test_schema_typing(test_app: SphinxTestApp, snapshot) -> None:
    test_app.build()
    warning_records = build_warnings(test_app)
    print(warning_records)
    assert_no_warnings(test_app)

    needs = json.loads(Path(test_app.outdir, "needs.json").read_text("utf8"))
    assert needs == snapshot(exclude=props("created", "project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_schema_e2e"}],
    indirect=True,
)
def test_schema_e2e(test_app: SphinxTestApp, snapshot) -> None:
    test_app.build()
    warnings_text = "\n".join(build_warnings(test_app))
    assert warnings_text == snapshot

    json_data = Path(test_app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(exclude=props("created", "project", "creator"))

    html = Path(test_app.outdir, "index.html").read_text()
    assert html
    # check schema validation report JSON exist
    report_json = Path(test_app.outdir, "schema_violations.json")
    assert report_json.exists(), (
        f"Expected schema validation report JSON file not found: {report_json}"
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_schema_example",
        }
    ],
    indirect=True,
)
def test_schema_example(test_app: SphinxTestApp, snapshot) -> None:
    """Check error-free build of the example from the docs."""
    test_app.build()
    assert_no_warnings(test_app)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    "conf.py",
                    """

extensions = ["sphinx_needs"]
needs_schema_validation_enabled = False
needs_fields = {
    "extra": {"schema": {"type": "string", "enum": ["a", "b"]}}
        }
                """,
                ),
                (
                    "index.rst",
                    """
Test
====
.. req:: A requirement
  :extra: x
""",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_validation_disabled(test_app):
    """Test that disabling schema validation suppresses schema violation warnings and output."""
    app = test_app
    app.build()
    assert app.statuscode == 0
    assert not app._warning.getvalue()
    assert not Path(app.outdir, "schema_violations.json").exists()


@pytest.mark.parametrize("schema_benchmark_app", [10, 100], indirect=True)
@pytest.mark.skipif(
    sphinx_version < (8,),
    reason="sphinx 7 does not emit warning code prefixes, so snapshots differ",
)
def test_schema_benchmark(schema_benchmark_app, snapshot):
    """Test the benchmark project works."""
    schema_benchmark_app.build()
    assert schema_benchmark_app.statuscode == 0
    warnings_text = "\n".join(build_warnings(schema_benchmark_app))
    assert warnings_text == snapshot


_HEADER_CONF = """
extensions = ["sphinx_needs"]
needs_links = {
    "verifies": {"incoming": "is verified by", "outgoing": "verifies"},
    "implements": {"incoming": "is implemented by", "outgoing": "implements"},
}
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_"},
    {"directive": "spec", "title": "Specification", "prefix": "S_"},
    {"directive": "test", "title": "Test", "prefix": "T_"},
]
needs_schema_definitions = {"schemas": [{
    "id": "test-rule",
    "select": {"properties": {"type": {"const": "test"}}},
    "validate": {"network": {"verifies": {"items": %s}}},
}]}
"""
_HEADER_RST = """
Test
====

.. req:: A requirement
   :id: R_001

.. spec:: A spec
   :id: S_001
   :implements: %s

.. spec:: Another spec
   :id: S_002

.. test:: A test
   :id: T_001
   :verifies: S_001
"""


@pytest.mark.parametrize(
    "test_app, need_paths",
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (
                        "conf.py",
                        _HEADER_CONF
                        % '{"local": {"properties": {"type": {"const": "req"}}}}',
                    ),
                    ("index.rst", _HEADER_RST % "R_001"),
                ],
            },
            ["T_001 > verifies > S_001"],
            id="level-1-network-local-fail",
        ),
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (
                        "conf.py",
                        _HEADER_CONF
                        % (
                            '{"network": {"implements": {"items": {"local":'
                            ' {"properties": {"type": {"const": "req"}}}}}}}'
                        ),
                    ),
                    ("index.rst", _HEADER_RST % "S_002"),
                ],
            },
            ["T_001 > verifies > S_001 > implements > S_002"],
            id="level-2-network-local-fail",
        ),
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (
                        "conf.py",
                        _HEADER_CONF
                        % (
                            '{"network": {"implements": {"contains": {"local":'
                            ' {"properties": {"type": {"const": "req"}}}}}}}'
                        ),
                    ),
                    ("index.rst", _HEADER_RST % "S_002"),
                ],
            },
            ["T_001 > verifies > S_001 > implements"],
            id="level-1-network-contains-too-few",
        ),
    ],
    indirect=["test_app"],
)
def test_network_finding_header_names_selected_need(
    test_app: SphinxTestApp, need_paths: list[str]
) -> None:
    """A network finding's console header names the need the rule SELECTED (#2297).

    The rule selects ``T_001``; the failure is found on a need it links to,
    one or two hops away.
    The header used to name the need at the failing level (``S_001`` / ``S_002``),
    which reads as if the linked need broke the rule,
    while ``schema_violations.json`` files the finding under ``T_001``.
    The ``Need path`` line keeps the whole chain.
    """
    test_app.build()
    records = [r for r in build_warnings(test_app) if "Need path:" in r]
    assert len(records) == len(need_paths), records
    for record, need_path in zip(records, need_paths, strict=True):
        first_line = record.splitlines()[0]
        assert first_line == "ERROR: Need 'T_001' has schema violations:", record
        assert f"  Need path:      {need_path}" in record.splitlines(), record

    report = json.loads(
        Path(test_app.outdir, "schema_violations.json").read_text("utf8")
    )
    assert list(report["validation_warnings"]) == ["T_001"]


# A link to a part reads as its need (design/parts-contract.md, "A link to a part"): the
# network rules validate the need, as for a link to the need itself (#2337). A link to a
# part its need does not have, or to a part of no need, is a broken link, as a link to no
# need is. A link to a need whose id holds a ``.`` (there is no need ``SPEC_9``) is
# validated as that need, as in 9.3.0, which takes no side on what such an id means.

_PART_LINK_CONF = """\
extensions = ["sphinx_needs"]
needs_schema_definitions = {
  "schemas": [
    {
      "select": {"properties": {"type": {"const": "impl"}}},
      "validate": {"network": {"links": %s}},
    }
  ]
}
"""

_PART_LINK_RST = """\
Index
=====

.. spec:: Spec
   :id: SPEC_1

   Text with :np:`(p1) the part`.

.. req:: Req
   :id: REQ_1

   Text with :np:`(r1) a part of a requirement`.

.. spec:: A need whose id holds a dot
   :id: SPEC_9.x

.. impl:: To the need
   :id: IMPL_1
   :links: SPEC_1

.. impl:: To a part
   :id: IMPL_2
   :links: SPEC_1.p1

.. impl:: To a part its need does not have
   :id: IMPL_3
   :links: SPEC_1.p9

.. impl:: To a part of no need
   :id: IMPL_4
   :links: NOPE_1.p1

.. impl:: To a need whose id holds a dot
   :id: IMPL_5
   :links: SPEC_9.x

.. impl:: To a part, with a condition after it
   :id: IMPL_6
   :links: SPEC_1.p1[status is None]

.. impl:: To a part of a requirement
   :id: IMPL_7
   :links: REQ_1.r1

.. impl:: To the empty part, which no need has
   :id: IMPL_8
   :links: SPEC_1.
"""


def _schema_findings(app: SphinxTestApp) -> list[tuple[str, str, str]]:
    """Each schema finding as its need, its need path and its message."""
    found = []
    for record in build_warnings(app):
        if "has schema violations" not in record:
            continue
        lines = record.splitlines()
        need = lines[0].split("'")[1]
        path = next(line for line in lines if line.startswith("  Need path:"))
        message = next(line for line in lines if line.startswith("  Schema message:"))
        found.append(
            (
                need,
                path.removeprefix("  Need path:").strip(),
                message.removeprefix("  Schema message:").strip(),
            )
        )
    return found


def _broken(need: str, address: str) -> list[tuple[str, str, str]]:
    return [
        (
            need,
            f"{need} > links",
            f"Broken link of type 'links' to '{address}' "
            "[sn_schema_violation.network_missing_target]",
        ),
        (
            need,
            f"{need} > links",
            "Too few valid links of type 'links' (0 < 1) "
            "[sn_schema_violation.network_contains_too_few]",
        ),
    ]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    "conf.py",
                    _PART_LINK_CONF
                    % '{"contains": {"local": {"properties": {"type": {"enum":'
                    ' ["spec", "req"]}}}}, "minContains": 1}',
                ),
                ("index.rst", _PART_LINK_RST),
            ],
        }
    ],
    ids=["contains"],
    indirect=True,
)
def test_network_reads_a_link_to_a_part_as_its_need(test_app: SphinxTestApp) -> None:
    test_app.build()
    assert sorted(_schema_findings(test_app)) == sorted(
        _broken("IMPL_3", "SPEC_1.p9")
        + _broken("IMPL_4", "NOPE_1.p1")
        + _broken("IMPL_8", "SPEC_1.")
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    "conf.py",
                    _PART_LINK_CONF
                    % '{"items": {"local": {"properties": {"type": {"const":'
                    ' "spec"}}}}}',
                ),
                ("index.rst", _PART_LINK_RST),
            ],
        }
    ],
    ids=["items"],
    indirect=True,
)
def test_network_validates_the_need_of_a_part_link(test_app: SphinxTestApp) -> None:
    """``items`` tests the need a link to a part names: the part of a ``req`` fails a
    rule asking for a ``spec``, and the need path names the link as written."""
    test_app.build()
    findings = [f for f in _schema_findings(test_app) if f[0] == "IMPL_7"]
    assert findings == [
        (
            "IMPL_7",
            "IMPL_7 > links > REQ_1.r1",
            '"spec" was expected [sn_schema_violation.network_local_fail]',
        )
    ]
    assert {need for need, _, _ in _schema_findings(test_app)} == {
        "IMPL_3",
        "IMPL_4",
        "IMPL_7",
        "IMPL_8",
    }
