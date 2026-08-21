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


@pytest.mark.parametrize(
    ("file_content", "message", "names_file"),
    [
        pytest.param(None, "Variant data file not found", True, id="missing"),
        pytest.param("{not json", "Invalid JSON in", True, id="malformed"),
        # the two shape errors below are raised by the validator, which has never
        # been told which file the data came from
        pytest.param(
            '["not", "an", "object"]', "must contain a JSON object", False, id="list"
        ),
        pytest.param(
            '{"x": null}', "expected str/bool/int/float", False, id="bad_value"
        ),
    ],
)
def test_variant_data_file_errors_fail_the_build(
    tmpdir, make_app, write_fixture_files, file_content, message, names_file
):
    """A missing or malformed variant data file fails the build, naming the file.

    Only the phase in which this is reported changed; the exception type -- and so
    the severity -- and the message are unchanged, which is what is pinned here by
    wrapping both the application creation and the build.
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
    if file_content is not None:
        Path(str(tmpdir), "variant_data.json").write_text(
            file_content, encoding="utf-8"
        )

    with pytest.raises(NeedsConfigException) as excinfo:
        app = make_app(srcdir=Path(str(tmpdir)), freshenv=True)
        app.build()

    assert message in str(excinfo.value)
    assert ("variant_data.json" in str(excinfo.value)) is names_file


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
