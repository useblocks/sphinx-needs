"""Tests for needs_variant_data configuration."""

from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path

import pytest
from syrupy.extensions.json import JSONSnapshotExtension

from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs_testkit import assert_no_warnings, build_warnings
from ub_project import ProjectConfigError


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data",
        }
    ],
    indirect=True,
)
def test_variant_data_html(test_app):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    print(warning_records)
    # The needs_warnings check for wrong_platform should fire for REQ_002
    assert warning_records == [
        "WARNING: wrong_platform: failed\n"
        "\t\tfailed needs: 1 (REQ_002)\n"
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
        }
    ],
    indirect=True,
)
def test_variant_data_file_html(test_app):
    """Test loading variant data from a JSON file with inline override."""
    app = test_app
    app.build()

    assert_no_warnings(app)

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
        }
    ],
    indirect=True,
)
def test_variant_data_fields_html(test_app, snapshot_json):
    """Test resolving ``<{...}>`` variant data references in need fields."""
    app = test_app
    app.build()

    assert_no_warnings(app)

    data = json.loads(Path(app.outdir, "needs.json").read_text())
    assert data["versions"][""]["needs"] == snapshot_json


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data_field_errors",
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

    warning_records = build_warnings(app)

    assert warning_records == [
        # in the order the values are computed: by need id, as no value reads another
        "<srcdir>/index.rst:24: WARNING: Error while resolving dynamic values for field 'myarray', of need 'REQ_BADTYPE_ARRAY': variant data value <class 'int'> is not of type 'array' or item type 'string' [needs.dynamic_function]",
        "<srcdir>/index.rst:16: WARNING: Error while resolving dynamic values for field 'myint', of need 'REQ_BADTYPE_STR': variant data value <class 'str'> is not of type 'integer' [needs.dynamic_function]",
        "<srcdir>/index.rst:20: WARNING: Error while resolving dynamic values for field 'mystring', of need 'REQ_BADTYPE_STRING': variant data reference 'var.build' resolves to a mapping ('var.build'); access a leaf value instead [needs.dynamic_function]",
        "<srcdir>/index.rst:8: WARNING: Error while resolving dynamic values for field 'mystring', of need 'REQ_MISSING': Unknown variant data key: 'var.nonexistent' [needs.dynamic_function]",
        "<srcdir>/index.rst:12: WARNING: Error while resolving dynamic values for field 'mystring', of need 'REQ_MISSING_NESTED': Unknown variant data key: 'var.build.missing' [needs.dynamic_function]",
        "<srcdir>/index.rst:4: WARNING: Error while resolving dynamic values for field 'mystring', of need 'REQ_SYNTAX': variant data reference 'platform' is invalid: expected a dotted 'var.*' path [needs.dynamic_function]",
    ]

    data = json.loads(Path(app.outdir, "needs.json").read_text())
    assert data["versions"][""]["needs"] == snapshot_json


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data_config_inited",
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
        }
    ],
    indirect=True,
)
def test_variant_data_nested_inline_overrides_file(test_app):
    """Inline variant data deep-merges over the file: the leaf wins, siblings survive."""
    app = test_app
    app.build()

    assert_no_warnings(app)

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
        pytest.param(None, "variant data file not found: {file}", id="missing"),
        pytest.param(
            "{not json",
            "variant data file {file} is not valid JSON: Expecting property name "
            "enclosed in double quotes: line 1 column 2 (char 1)",
            id="malformed",
        ),
        pytest.param(
            '["not", "an", "object"]',
            "variant data file {file} must hold a JSON object, got list",
            id="list",
        ),
        pytest.param(
            '{"x": null}',
            "variant data file {file}: var.x: a value must be a str, bool, int or "
            "float, an array or a table, got NoneType",
            id="bad_value",
        ),
    ],
)
def test_variant_data_file_errors_fail_the_build(
    tmpdir, make_app, write_fixture_files, file_content, expected
):
    """A missing or malformed variant data file fails the build.

    The exception type -- and so the severity -- is ``NeedsConfigException``, as it
    always was, and the message is ``ub_project``'s, the words the toml route uses too:
    pinned here by wrapping both the application creation and the build. The phase is
    pinned separately, by
    ``test_variant_data_file_missing_fails_at_application_creation``.
    """
    srcdir = _write_variant_data_file_project(tmpdir, write_fixture_files, file_content)

    with pytest.raises(NeedsConfigException) as excinfo:
        app = make_app(srcdir=srcdir, freshenv=True)
        app.build()

    assert str(excinfo.value) == expected.format(file=srcdir / "variant_data.json")


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

    assert str(excinfo.value) == (
        f"variant data file not found: {srcdir / 'variant_data.json'}"
    )


#: A ``file_content`` that makes the data file a directory.
_DIRECTORY = object()
#: A ``file_content`` that makes the data file one that cannot be read.
_UNREADABLE = object()
#: A data file holding an integer beyond Python's int-string conversion limit.
_HUGE_INT = b'{"x": ' + b"1" * 5000 + b"}"

_SKIP_UNLESS_CHMOD_WORKS = [
    pytest.mark.skipif(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        reason="root reads a file whatever its permissions",
    ),
    pytest.mark.skipif(
        sys.platform == "win32",
        reason="os.chmod on Windows only sets the read-only attribute; the file stays readable",
    ),
]


def _write_data_file(path: Path, file_content: object) -> None:
    """Write the data file: ``None`` leaves it missing, a sentinel shapes it."""
    if file_content is _DIRECTORY:
        path.mkdir()
    elif file_content is _UNREADABLE:
        path.write_text("{}", encoding="utf-8")
        path.chmod(0o000)
    elif isinstance(file_content, bytes):
        path.write_bytes(file_content)


@pytest.mark.parametrize(
    ("file_content", "expected"),
    [
        pytest.param(
            _DIRECTORY, "variant data file {file} is a directory", id="directory"
        ),
        pytest.param(
            b'{"x": "\xff"}',
            "variant data file {file} is not valid JSON: 'utf-8' codec can't decode "
            "byte 0xff in position 7: invalid start byte",
            id="non_utf8",
        ),
        pytest.param(
            _UNREADABLE,
            "variant data file {file} cannot be read: [Errno 13] Permission denied: "
            "'{file}'",
            id="noperm",
            marks=_SKIP_UNLESS_CHMOD_WORKS,
        ),
    ],
)
def test_unreadable_variant_data_file_is_a_config_error(
    tmp_path, make_app, file_content, expected
):
    """A directory, a file that is not UTF-8, or one that cannot be read, is a
    ``NeedsConfigException`` naming the file, like every other bad data file; all three
    used to escape as a raw ``ExtensionError`` wrapping an ``OSError`` or a
    ``UnicodeDecodeError``."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\nneeds_variant_data_file = "vd.json"\n',
        encoding="utf-8",
    )
    (srcdir / "index.rst").write_text("Title\n=====\n", encoding="utf-8")
    _write_data_file(srcdir / "vd.json", file_content)

    with pytest.raises(NeedsConfigException) as excinfo:
        make_app(srcdir=srcdir, freshenv=True)

    assert str(excinfo.value) == expected.format(file=srcdir / "vd.json")
    assert isinstance(excinfo.value.__cause__, ProjectConfigError)


def test_variant_data_file_with_an_oversized_integer_is_a_config_error(
    tmp_path, make_app
):
    """An integer beyond Python's int-string conversion limit is a ``ValueError`` that
    ub_project lets through unwrapped (#1995); the resolver re-raises it as a
    ``NeedsConfigException``, rather than a raw ``ExtensionError``, and in the same
    words as the toml route -- which, as ub_project names neither the file nor the
    table here, carry no prefix on either route."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "index.rst").write_text("Title\n=====\n", encoding="utf-8")
    (srcdir / "ubproject.toml").write_text(
        '[variants]\ndata_file = "vd.json"\n', encoding="utf-8"
    )
    _write_data_file(srcdir / "vd.json", _HUGE_INT)

    messages = []
    for conf in (
        'needs_variant_data_file = "vd.json"',
        'needs_from_toml = "ubproject.toml"',
    ):
        (srcdir / "conf.py").write_text(
            f'extensions = ["sphinx_needs"]\n{conf}\n', encoding="utf-8"
        )
        with pytest.raises(NeedsConfigException) as excinfo:
            make_app(srcdir=srcdir, freshenv=True)
        assert isinstance(excinfo.value.__cause__, ValueError)
        messages.append(str(excinfo.value))

    conf_message, toml_message = messages
    assert conf_message.startswith("Exceeds the limit"), conf_message
    assert toml_message == conf_message


def test_invalid_inline_variant_data_without_a_file_fails_the_build(tmp_path, make_app):
    """Inline data is validated when no data file is set, too."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\nneeds_variant_data = {"x": None}\n',
        encoding="utf-8",
    )
    (srcdir / "index.rst").write_text("Title\n=====\n", encoding="utf-8")

    with pytest.raises(NeedsConfigException) as excinfo:
        make_app(srcdir=srcdir, freshenv=True)

    assert str(excinfo.value) == (
        "var.x: a value must be a str, bool, int or float, an array or a table, "
        "got NoneType"
    )


@pytest.mark.parametrize(
    ("conf", "confoverrides"),
    [
        pytest.param('needs_variant_data_file = ""', {}, id="conf"),
        pytest.param(
            'needs_variant_data_file = "missing.json"',
            {"needs_variant_data_file": ""},
            id="confoverride",
        ),
    ],
)
def test_empty_variant_data_file_means_no_file(tmp_path, make_app, conf, confoverrides):
    """``""`` is "no file" on the ``conf.py`` / ``-D`` route, as ``None`` is, and the
    inline data is used alone, with no error."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        textwrap.dedent(f"""\
            extensions = ["sphinx_needs"]
            needs_variant_data = {{"edition": "pro"}}
            {conf}
            """),
        encoding="utf-8",
    )
    (srcdir / "index.rst").write_text(
        "Title\n=====\n\nEdition: :variant:`edition`\n", encoding="utf-8"
    )

    app = make_app(srcdir=srcdir, freshenv=True, confoverrides=confoverrides)
    app.build()

    assert_no_warnings(app)
    assert app.config.needs_variant_data == {"edition": "pro"}
    assert "Edition: pro" in Path(app.outdir, "index.html").read_text()


@pytest.mark.parametrize(
    "file_content",
    [
        pytest.param(None, id="missing"),
        pytest.param(b"{not json", id="malformed"),
        pytest.param(b'["not", "an", "object"]', id="list"),
        pytest.param(b'{"x": null}', id="bad_value"),
        pytest.param(b'{"x": [1, "a"]}', id="mixed_array"),
        pytest.param(b'{"x": "\xff"}', id="non_utf8"),
        pytest.param(b"", id="empty"),
        pytest.param(_DIRECTORY, id="directory"),
        pytest.param(_UNREADABLE, id="noperm", marks=_SKIP_UNLESS_CHMOD_WORKS),
    ],
)
def test_bad_variant_data_file_reads_the_same_on_both_routes(
    tmp_path, make_app, file_content
):
    """The same bad data file, declared in the toml file or in ``conf.py``, is refused
    in the same words: the toml route only prefixes them with the file and the table."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "index.rst").write_text("Title\n=====\n", encoding="utf-8")
    (srcdir / "ubproject.toml").write_text(
        '[variants]\ndata_file = "vd.json"\n', encoding="utf-8"
    )
    _write_data_file(srcdir / "vd.json", file_content)

    messages = []
    for conf in (
        'needs_from_toml = "ubproject.toml"',
        'needs_variant_data_file = "vd.json"',
    ):
        (srcdir / "conf.py").write_text(
            f'extensions = ["sphinx_needs"]\n{conf}\n', encoding="utf-8"
        )
        with pytest.raises(NeedsConfigException) as excinfo:
            make_app(srcdir=srcdir, freshenv=True)
        messages.append(str(excinfo.value))

    toml_message, conf_message = messages
    assert toml_message == f"{srcdir / 'ubproject.toml'}: [variants]: {conf_message}"


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

    assert_no_warnings(app)

    index_html = Path(app.outdir, "index.html").read_text()

    # the role renders the value the extension wrote ...
    assert "Role renders: from_extension" in index_html
    # ... so a filter must match that same value, and not the one from the file
    assert "Extension value: 1" in index_html
    assert "File value: 0" in index_html
