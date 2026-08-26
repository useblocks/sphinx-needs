"""Tests for needs_variant_data configuration."""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from syrupy.extensions.json import JSONSnapshotExtension

from sphinx_needs.exceptions import NeedsConfigException


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_data_html(test_app):
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    print(warnings)
    # The needs_warnings check for wrong_platform should fire for REQ_002
    assert warnings == [
        "WARNING: wrong_platform: failed",
        "\t\tfailed needs: 1 (REQ_002)",
        "\t\tused filter: platform is not None and var.platform != platform [needs.warnings]",
    ]

    index_html = Path(app.outdir, "index.html").read_text()

    # needtable: var.platform == platform matches REQ_001 (platform=arm)
    assert "REQ_001" in index_html
    assert '<td class="needs_title"><p>ARM Requirement</p></td>' in index_html

    # needlist: "arm" in var.archs is always True, so all needs shown
    assert "REQ_002" in index_html
    assert "REQ_003" in index_html

    # needcount: var.build.debug == True is always True, so count = 3
    assert "Debug mode needs: 3" in index_html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data_file",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_data_file_html(test_app):
    """Test loading variant data from a JSON file with inline override."""
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == []

    index_html = Path(app.outdir, "index.html").read_text()

    # Inline needs_variant_data overrides env from "production" to "staging"
    # so var.env == "staging" matches all needs
    assert "REQ_STAGING" in index_html
    assert "REQ_PROD" in index_html

    # var.region == "us-east" still works (from file, not overridden)
    assert "US East Needs" in index_html


@pytest.fixture
def snapshot_json(snapshot):
    return snapshot.use_extension(JSONSnapshotExtension)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data_fields",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_data_fields_html(test_app, snapshot_json):
    """Test resolving ``<{...}>`` variant data references in need fields."""
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == []

    data = json.loads(Path(app.outdir, "needs.json").read_text())
    assert data["versions"][""]["needs"] == snapshot_json


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data_field_errors",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_data_field_errors_html(test_app, snapshot_json):
    """Test warnings for problematic ``<{...}>`` variant data references.

    Covers invalid ``var.*`` paths, missing variant keys (top-level and
    nested), and resolved values whose type does not match the field schema.
    """
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()

    assert warnings == [
        "srcdir/index.rst:4: WARNING: Error while resolving dynamic values for field 'mystring', of need 'REQ_SYNTAX': variant data reference 'platform' is invalid: expected a dotted 'var.*' path [needs.dynamic_function]",
        "srcdir/index.rst:8: WARNING: Error while resolving dynamic values for field 'mystring', of need 'REQ_MISSING': Unknown variant data key: 'var.nonexistent' [needs.dynamic_function]",
        "srcdir/index.rst:12: WARNING: Error while resolving dynamic values for field 'mystring', of need 'REQ_MISSING_NESTED': Unknown variant data key: 'var.build.missing' [needs.dynamic_function]",
        "srcdir/index.rst:16: WARNING: Error while resolving dynamic values for field 'myint', of need 'REQ_BADTYPE_STR': variant data value <class 'str'> is not of type 'integer' [needs.dynamic_function]",
        "srcdir/index.rst:20: WARNING: Error while resolving dynamic values for field 'mystring', of need 'REQ_BADTYPE_STRING': variant data reference 'var.build' resolves to a mapping ('var.build'); access a leaf value instead [needs.dynamic_function]",
        "srcdir/index.rst:24: WARNING: Error while resolving dynamic values for field 'myarray', of need 'REQ_BADTYPE_ARRAY': variant data value <class 'int'> is not of type 'array' or item type 'string' [needs.dynamic_function]",
    ]

    data = json.loads(Path(app.outdir, "needs.json").read_text())
    assert data["versions"][""]["needs"] == snapshot_json


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data_config_inited",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_data_resolved_at_config_inited(test_app):
    """The merged variant data must exist while ``config-inited`` is still running.

    Configuration that decides which documents exist at all -- ``exclude_patterns``
    above all -- can only be changed during ``config-inited``, so the merged map has
    to be available to handlers of that event. The ``test_app`` fixture has created
    the application, and so emitted ``config-inited``, but has not built it, hence
    nothing from the read phase can have contributed to what is asserted here.
    """
    app = test_app

    merged = {"env": "production", "build": {"debug": True, "opt_level": 3}}

    # recorded by a default-priority ``config-inited`` handler in the project's conf.py
    assert app.variant_data_at_config_inited == merged
    # ... and stored back onto the config, before any document has been read
    assert app.config.needs_variant_data == merged
    assert app.config.needs_variant_data_proxy is not None


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data_config_inited",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_data_nested_inline_overrides_file(test_app):
    """Inline variant data deep-merges over the file: the leaf wins, siblings survive."""
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == []

    index_html = Path(app.outdir, "index.html").read_text()

    # "env" comes from the file, the nested "opt_level" from the inline override
    assert "Built for production at optimisation level 3." in index_html
    # the inline override of "build.opt_level" must not drop its sibling "build.debug",
    # which this needtable filters on
    assert "Debug Needs" in index_html
    assert "REQ_OPT" in index_html


def _write_variant_data_file_project(
    tmpdir, write_fixture_files, file_content: str | None
) -> Path:
    """Write a project configured with ``needs_variant_data_file``.

    :param file_content: The contents to write to the file, or ``None`` to leave the
        configured file missing.
    :returns: The project's source directory.
    """
    write_fixture_files(
        tmpdir,
        {
            "conf": textwrap.dedent("""\
                extensions = ["sphinx_needs"]
                needs_variant_data_file = "variant_data.json"
                """),
            "rst": "Title\n=====\n",
        },
    )
    srcdir = Path(str(tmpdir))
    if file_content is not None:
        (srcdir / "variant_data.json").write_text(file_content, encoding="utf-8")
    return srcdir


@pytest.mark.parametrize(
    ("file_content", "expected"),
    [
        pytest.param(
            None, ("Variant data file not found", "variant_data.json"), id="missing"
        ),
        pytest.param(
            "{not json", ("Invalid JSON in", "variant_data.json"), id="malformed"
        ),
        # The two shape errors below come from the validator, which is not told which
        # file the data was read from, so their messages name no file. Naming it there
        # would be an improvement (a follow-up), so this test does not pin the absence.
        pytest.param(
            '["not", "an", "object"]', ("must contain a JSON object",), id="list"
        ),
        pytest.param('{"x": null}', ("expected str/bool/int/float",), id="bad_value"),
    ],
)
def test_variant_data_file_errors_fail_the_build(
    tmpdir, make_app, write_fixture_files, file_content, expected
):
    """A missing or malformed variant data file fails the build.

    Only the phase in which this is reported changed; the exception type -- and so
    the severity -- and the message are unchanged, which is what is pinned here by
    wrapping both the application creation and the build. The phase itself is pinned
    separately, by ``test_variant_data_file_missing_fails_at_application_creation``.
    """
    srcdir = _write_variant_data_file_project(tmpdir, write_fixture_files, file_content)

    with pytest.raises(NeedsConfigException) as excinfo:
        app = make_app(srcdir=srcdir, freshenv=True)
        app.build()

    for fragment in expected:
        assert fragment in str(excinfo.value)


def test_variant_data_file_missing_fails_at_application_creation(
    tmpdir, make_app, write_fixture_files
):
    """The error must escape application creation, before any document is read.

    This is the one part of the error behaviour that is new, and the test that wraps
    both creation and the build cannot see it: a version that resolved during
    ``config-inited`` but deferred the raise to the read phase would satisfy that one
    while making the documented "before any document is read" false. Wrapping only
    ``make_app`` is the assertion -- reaching ``app.build()`` is impossible, because no
    application is ever returned.
    """
    srcdir = _write_variant_data_file_project(tmpdir, write_fixture_files, None)

    with pytest.raises(NeedsConfigException) as excinfo:
        make_app(srcdir=srcdir, freshenv=True)

    assert "Variant data file not found" in str(excinfo.value)
    assert "variant_data.json" in str(excinfo.value)


def test_variant_data_file_confoverride_wins_over_toml(
    tmpdir, make_app, write_fixture_files
):
    """``-D needs_variant_data_file=...`` still beats the value read from TOML."""
    write_fixture_files(
        tmpdir,
        {
            "conf": textwrap.dedent("""\
                extensions = ["sphinx_needs"]
                needs_from_toml = "ubproject.toml"
                """),
            "ubproject": textwrap.dedent("""\
                [needs]
                variant_data_file = "from_toml.json"
                """),
            "rst": "Title\n=====\n\nSource: :variant:`source`\n",
        },
    )
    srcdir = Path(str(tmpdir))
    (srcdir / "from_toml.json").write_text(
        json.dumps({"source": "toml"}), encoding="utf-8"
    )
    (srcdir / "from_override.json").write_text(
        json.dumps({"source": "override"}), encoding="utf-8"
    )

    app = make_app(
        srcdir=srcdir,
        freshenv=True,
        confoverrides={"needs_variant_data_file": "from_override.json"},
    )
    app.build()

    assert app.config.needs_variant_data == {"source": "override"}
    assert "Source: override" in Path(app.outdir, "index.html").read_text()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data_extension_write",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_data_extension_write_stays_coherent(test_app):
    """The role and ``var.*`` filters must read the same map, whatever it holds.

    Resolution happens during ``config-inited``, so an extension that writes
    ``needs_variant_data`` from its own handler afterwards no longer has the file
    merged in or its values validated. That is a deliberate narrowing. What must
    never happen is the two read paths disagreeing inside one build: the ``variant``
    role reads ``needs_variant_data`` directly, while filter expressions read the
    ``var`` proxy derived from it.
    """
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == []

    index_html = Path(app.outdir, "index.html").read_text()

    # the role renders the value the extension wrote ...
    assert "Role renders: from_extension" in index_html
    # ... so a filter must match that same value, and not the one from the file
    assert "Extension value: 1" in index_html
    assert "File value: 0" in index_html
