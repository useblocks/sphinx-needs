"""The ``[variants]`` table of ``needs_from_toml``, read through ``ub_project``.

Each test pins one of the observable changes the reader brought, or one thing that must
stay as it was: the per-key ``-D`` override, the per-key merge with ``conf.py`` values, and
the confval's path string. Everything is a real build, because the reader runs during
``config-inited`` and its result is only visible through the configuration and the
output.
"""

from __future__ import annotations

import json
import re
import shutil
import textwrap
from pathlib import Path

import pytest

from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs_testkit import assert_no_warnings, build_warnings

TESTS_DIR = Path(__file__).parent

#: A page with no variant reference, and one showing two values through the ``variant``
#: role, for the projects whose data holds both keys.
RST = "Title\n=====\n\nText.\n"
ROLE_RST = "Title\n=====\n\nEdition: :variant:`edition`\n\nCPU: :variant:`cpu`\n"


def _write(srcdir: Path, files: dict[str, str | dict]) -> Path:
    """Write *files* under *srcdir*: a dict is written as JSON, a string as text."""
    for name, content in files.items():
        path = srcdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, dict):
            path.write_text(json.dumps(content), encoding="utf-8")
        else:
            path.write_text(textwrap.dedent(content), encoding="utf-8")
    return srcdir


def _conf(*lines: str) -> str:
    return "\n".join(['extensions = ["sphinx_needs"]', *lines]) + "\n"


TOML_CONF = _conf('needs_from_toml = "ubproject.toml"')


@pytest.fixture
def build(make_app, tmp_path):
    """Write a project, build it, and return the application."""

    def _build(files: dict[str, str | dict], **kwargs):
        srcdir = _write(tmp_path / "src", {"index.rst": RST, **files})
        app = make_app(srcdir=srcdir, freshenv=True, **kwargs)
        app.build()
        return app

    return _build


def _html(app) -> str:
    return Path(app.outdir, "index.html").read_text(encoding="utf-8")


# --- [variants] is read ---------------------------------------------------------------


def test_variants_inline_table_is_read(build):
    app = build(
        {
            "index.rst": ROLE_RST,
            "conf.py": TOML_CONF,
            "ubproject.toml": """\
                [variants.data]
                edition = "pro"
                cpu = "arm"
                """,
        }
    )
    assert_no_warnings(app)
    assert app.config.needs_variant_data == {"edition": "pro", "cpu": "arm"}
    assert "Edition: pro" in _html(app)
    assert "CPU: arm" in _html(app)


def test_variants_data_file_is_read(build):
    app = build(
        {
            "index.rst": ROLE_RST,
            "conf.py": TOML_CONF,
            "ubproject.toml": '[variants]\ndata_file = "vd.json"\n',
            "vd.json": {"edition": "base", "cpu": "x86"},
        }
    )
    assert_no_warnings(app)
    assert app.config.needs_variant_data == {"edition": "base", "cpu": "x86"}
    assert app.config.needs_variant_data_file == str(app.srcdir / "vd.json")
    assert "CPU: x86" in _html(app)


def test_variants_inline_table_is_merged_over_the_file(build):
    app = build(
        {
            "index.rst": ROLE_RST,
            "conf.py": TOML_CONF,
            "ubproject.toml": """\
                [variants]
                data_file = "vd.json"
                [variants.data]
                edition = "pro"
                """,
            "vd.json": {"edition": "base", "cpu": "x86"},
        }
    )
    assert_no_warnings(app)
    assert app.config.needs_variant_data == {"edition": "pro", "cpu": "x86"}
    assert "Edition: pro" in _html(app)


def test_variants_without_a_needs_table_is_read(build):
    """Today such a file warned ``'needs'`` and was not read at all."""
    app = build(
        {
            "conf.py": TOML_CONF,
            "ubproject.toml": '[variants.data]\nedition = "pro"\ncpu = "arm"\n',
        }
    )
    assert_no_warnings(app)
    assert app.config.needs_variant_data == {"edition": "pro", "cpu": "arm"}


def test_neither_table_keeps_todays_warning(build):
    app = build({"conf.py": TOML_CONF, "ubproject.toml": 'other = "x"\n'})
    assert build_warnings(app) == [
        "WARNING: Error loading 'needs_from_toml' file: 'needs' [needs.config]"
    ]


# --- the prefix ------------------------------------------------------------------------


def test_the_prefix_scopes_the_variants_table(build):
    """With ``needs_from_toml_table``, ``[<prefix>.variants]`` is read, and a top-level
    ``[variants]`` is someone else's: not read, not reported.

    This is what makes a ``pyproject.toml`` work, where PEP 518 reserves the top level.
    """
    app = build(
        {
            "conf.py": _conf(
                'needs_from_toml = "pyproject.toml"',
                'needs_from_toml_table = ["tool"]',
            ),
            "pyproject.toml": """\
                [variants]
                data_file = "never-opened.json"
                [variants.data]
                edition = "top-level"
                cpu = "top-level"

                [tool.needs]
                id_required = false

                [tool.variants]
                data_file = "vd.json"
                [tool.variants.data]
                edition = "pro"
                """,
            "vd.json": {"edition": "base", "cpu": "arm"},
        }
    )
    assert_no_warnings(app)
    assert app.config.needs_variant_data == {"edition": "pro", "cpu": "arm"}


def test_the_prefix_scopes_the_legacy_location_and_its_warning(build):
    app = build(
        {
            "conf.py": _conf(
                'needs_from_toml = "pyproject.toml"',
                'needs_from_toml_table = ["tool"]',
            ),
            "pyproject.toml": """\
                [tool.needs.variant_data]
                edition = "legacy"
                cpu = "arm"
                [tool.variants.data]
                edition = "pro"
                cpu = "x86"
                """,
        }
    )
    assert build_warnings(app) == [
        "WARNING: <srcdir>/pyproject.toml: [tool.needs] variant_data is "
        "ignored because [tool.variants] is set, and only one location is read; "
        "remove the [tool.needs] key [needs.variant_data_location]"
    ]
    assert app.config.needs_variant_data == {"edition": "pro", "cpu": "x86"}


# --- both locations, the legacy location, unknown keys --------------------------------

BOTH_TOML = """\
    [needs]
    variant_data_file = "legacy.json"
    [needs.variant_data]
    edition = "legacy"

    [variants]
    data_file = "vd.json"
    [variants.data]
    edition = "pro"
    """


def test_both_locations_read_variants_and_warn_per_ignored_key(build):
    app = build(
        {
            "conf.py": TOML_CONF,
            "ubproject.toml": BOTH_TOML,
            "vd.json": {"cpu": "arm"},
            # no legacy.json: the ignored location is not read
        }
    )
    assert build_warnings(app) == [
        "WARNING: <srcdir>/ubproject.toml: [needs] variant_data is ignored because [variants] is set, "
        "and only one location is read; remove the [needs] key "
        "[needs.variant_data_location]",
        "WARNING: <srcdir>/ubproject.toml: [needs] variant_data_file is ignored because [variants] is "
        "set, and only one location is read; remove the [needs] key "
        "[needs.variant_data_location]",
    ]
    assert app.config.needs_variant_data == {"edition": "pro", "cpu": "arm"}
    assert app.config.needs_variant_data_file == str(app.srcdir / "vd.json")


def test_both_locations_warning_is_silenced_by_its_own_subtype(build):
    app = build(
        {
            "conf.py": _conf(
                'needs_from_toml = "ubproject.toml"',
                'suppress_warnings = ["needs.variant_data_location"]',
            ),
            "ubproject.toml": BOTH_TOML,
            "vd.json": {"cpu": "arm"},
        }
    )
    assert_no_warnings(app)
    assert app.config.needs_variant_data == {"edition": "pro", "cpu": "arm"}


def _quickstart(tmp_path: Path) -> Path:
    srcdir = tmp_path / "quickstart"
    shutil.copytree(TESTS_DIR / "doc_test" / "doc_variants_quickstart", srcdir)
    return srcdir


def test_the_quickstart_legacy_location_builds_under_w_and_says_so_with_v(
    make_app, tmp_path
):
    """ubCode's quickstart ``variants`` template, as it ships, builds clean under ``-W``.

    ``doc_test/doc_variants_quickstart`` is a verbatim copy of ubCode's
    ``rust/ubc_quickstart/src/templates/variants/`` (``conf.py``, ``index.rst``,
    ``ubproject.toml``, ``variants.json``), which keeps its variant data in ``[needs]``.
    The legacy location is reported with ``-v`` only, so that the projects the quickstart
    has already created keep building under ``-W``.
    """
    srcdir = _quickstart(tmp_path)
    app = make_app(srcdir=srcdir, freshenv=True, warningiserror=True, verbosity=1)
    app.build()

    assert_no_warnings(app)
    assert app.statuscode == 0
    toml = srcdir / "ubproject.toml"
    status = app._status.getvalue()
    for key, current in (("variant_data", "data"), ("variant_data_file", "data_file")):
        assert (
            f"{toml}: variant data is read from its legacy location [needs] {key}; "
            f"[variants] {current} is the current one"
        ) in status
    html = _html(app)
    # the file's values, the inline table's, and the variant functions over them
    assert re.search(r"Built for\s+linux<", html)
    assert re.search(r"Compiler is\s+gcc<", html)
    assert "other_active" in html
    assert "arm_supported" in html
    assert app.config.needs_variant_data["edition"] == "pro"


def test_the_legacy_location_line_needs_v(make_app, tmp_path):
    srcdir = _quickstart(tmp_path)
    app = make_app(srcdir=srcdir, freshenv=True)
    app.build()

    assert_no_warnings(app)
    assert "legacy location" not in app._status.getvalue()


UNKNOWN_KEY_TOML = """\
    [variants]
    future_key = 1
    [variants.data]
    edition = "pro"
    """


def test_an_unknown_variants_key_warns(build):
    app = build({"conf.py": TOML_CONF, "ubproject.toml": UNKNOWN_KEY_TOML})
    assert build_warnings(app) == [
        "WARNING: <srcdir>/ubproject.toml: ignoring unknown key 'future_key' "
        "in [variants]; this version reads data and data_file "
        "[needs.variants_unknown_key]"
    ]
    assert app.config.needs_variant_data == {"edition": "pro"}


def test_an_unknown_variants_key_is_silenced_by_its_own_subtype(build):
    app = build(
        {
            "conf.py": _conf(
                'needs_from_toml = "ubproject.toml"',
                'suppress_warnings = ["needs.variants_unknown_key"]',
            ),
            "ubproject.toml": UNKNOWN_KEY_TOML,
        }
    )
    assert_no_warnings(app)


# --- refusals ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        pytest.param(
            'variants = "x"\n[needs]\nid_required = false\n',
            "[variants] must be a table, got str",
            id="variants-not-a-table",
        ),
        pytest.param(
            'variants = "x"\n',
            "[variants] must be a table, got str",
            id="variants-not-a-table-no-needs",
        ),
        pytest.param(
            '[variants]\ndata_file = ""\n',
            "[variants] data_file must be one non-empty path string, got ''",
            id="variants-data-file-empty",
        ),
        pytest.param(
            '[needs]\nvariant_data_file = ""\n',
            "[needs] variant_data_file must be one non-empty path string, got ''",
            id="needs-data-file-empty",
        ),
        pytest.param(
            '[needs]\nvariant_data_file = ["a.json"]\n',
            "[needs] variant_data_file must be one non-empty path string, got list",
            id="needs-data-file-list",
        ),
    ],
)
def test_refused_variant_configuration_fails_the_build(
    make_app, tmp_path, toml, message
):
    """``ub_project`` refuses these, and the refusal is a ``NeedsConfigException``.

    ``variants = "x"`` used to be ignored; ``variant_data_file = ""`` or a list crashed in
    the resolver with an ``ExtensionError`` naming neither the file nor the key.
    """
    srcdir = _write(tmp_path / "src", {"conf.py": TOML_CONF, "ubproject.toml": toml})
    with pytest.raises(NeedsConfigException) as excinfo:
        make_app(srcdir=srcdir, freshenv=True)
    assert str(excinfo.value) == f"{srcdir / 'ubproject.toml'}: {message}"


@pytest.mark.parametrize("table", ["needs", "variants"])
def test_a_missing_toml_data_file_fails_at_application_creation(
    make_app, tmp_path, table
):
    """A data file declared in the TOML is loaded while the TOML is read, and a missing
    one is reported in ``ub_project``'s words, naming the TOML and the table.

    The ``conf.py`` route keeps sphinx-needs' own message
    (``test_variant_data_integration.py``).
    """
    key = "variant_data_file" if table == "needs" else "data_file"
    srcdir = _write(
        tmp_path / "src",
        {"conf.py": TOML_CONF, "ubproject.toml": f'[{table}]\n{key} = "nope.json"\n'},
    )
    with pytest.raises(NeedsConfigException) as excinfo:
        make_app(srcdir=srcdir, freshenv=True)
    assert str(excinfo.value) == (
        f"{srcdir / 'ubproject.toml'}: [{table}]: variant data file not found: "
        f"{srcdir / 'nope.json'}"
    )


@pytest.mark.parametrize(
    ("content", "tail"),
    [
        pytest.param(b"[needs\n", "invalid TOML: ", id="invalid"),
        pytest.param(b'[needs]\ntitle = "\xff"\n', "not valid UTF-8 TOML: ", id="utf8"),
        pytest.param(None, "cannot be read: ", id="directory"),
    ],
)
def test_an_unreadable_toml_file_warns_in_ub_projects_words(
    build, tmp_path, content, tail
):
    toml = tmp_path / "src" / "ubproject.toml"
    toml.parent.mkdir(parents=True)
    if content is None:
        toml.mkdir()
    else:
        toml.write_bytes(content)
    app = build({"conf.py": TOML_CONF})
    (warning,) = build_warnings(app)
    assert warning.startswith(
        f"WARNING: Error loading 'needs_from_toml' file: <srcdir>/ubproject.toml: {tail}"
    ), warning
    assert warning.endswith(" [needs.config]"), warning


# --- -D, conf.py, anchoring: per key, as before ------------------------------------------


def test_confoverride_file_over_variants_whose_own_file_is_missing(build):
    """``-D needs_variant_data_file`` replaces ONE key: the TOML's file is never
    opened, and the TOML's inline table still applies."""
    app = build(
        {
            "conf.py": TOML_CONF,
            "ubproject.toml": """\
                [variants]
                data_file = "missing.json"
                [variants.data]
                edition = "pro"
                """,
            "b.json": {"edition": "base", "cpu": "b"},
        },
        confoverrides={"needs_variant_data_file": "b.json"},
    )
    assert_no_warnings(app)
    assert app.config.needs_variant_data == {"edition": "pro", "cpu": "b"}
    assert app.config.needs_variant_data_file == "b.json"


def test_an_overridden_key_does_not_decide_the_location(build):
    """``[variants]`` loses its only key to ``-D``, so ``[needs]`` is the declared
    location: its inline table is read, with no ``variant_data_location`` warning."""
    app = build(
        {
            "conf.py": TOML_CONF,
            "ubproject.toml": """\
                [variants]
                data_file = "missing.json"
                [needs.variant_data]
                edition = "legacy"
                """,
            "b.json": {"cpu": "b"},
        },
        confoverrides={"needs_variant_data_file": "b.json"},
        verbosity=1,
    )
    assert_no_warnings(app)
    assert app.config.needs_variant_data == {"cpu": "b", "edition": "legacy"}
    assert "legacy location [needs] variant_data;" in app._status.getvalue()


def test_conf_inline_fills_over_a_variants_file(build):
    """A ``conf.py`` inline table is merged over a ``[variants]`` file, per key."""
    app = build(
        {
            "conf.py": _conf(
                'needs_from_toml = "ubproject.toml"',
                'needs_variant_data = {"edition": "conf"}',
            ),
            "ubproject.toml": '[variants]\ndata_file = "vd.json"\n',
            "vd.json": {"edition": "file", "cpu": "arm"},
        }
    )
    assert_no_warnings(app)
    assert app.config.needs_variant_data == {"edition": "conf", "cpu": "arm"}


def test_a_conf_file_under_a_variants_inline_table(build):
    """A ``conf.py`` data file is merged under a ``[variants]`` inline table, per key."""
    app = build(
        {
            "conf.py": _conf(
                'needs_from_toml = "ubproject.toml"',
                'needs_variant_data_file = "vd.json"',
            ),
            "ubproject.toml": '[variants.data]\nedition = "pro"\n',
            "vd.json": {"edition": "file", "cpu": "arm"},
        }
    )
    assert_no_warnings(app)
    assert app.config.needs_variant_data == {"edition": "pro", "cpu": "arm"}
    assert app.config.needs_variant_data_file == "vd.json"


@pytest.mark.parametrize("table", ["needs", "variants"])
def test_a_toml_data_file_is_anchored_and_resolved_as_before(build, tmp_path, table):
    """The confval holds the path ``_abs_path`` makes of the TOML value: anchored at
    the TOML's directory and RESOLVED, so a ``..`` and a symlinked component are folded
    away exactly as they were for ``[needs] variant_data_file``."""
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "vd.json").write_text(json.dumps({"cpu": "arm"}), encoding="utf-8")
    real = tmp_path / "real"
    real.mkdir()
    (real / "vd.json").write_text(json.dumps({"edition": "pro"}), encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    (src / "lnk").symlink_to(real, target_is_directory=True)
    key = "variant_data_file" if table == "needs" else "data_file"

    for raw, expected, data in (
        ("../shared/vd.json", shared / "vd.json", {"cpu": "arm"}),
        ("lnk/vd.json", real / "vd.json", {"edition": "pro"}),
    ):
        app = build(
            {"conf.py": TOML_CONF, "ubproject.toml": f'[{table}]\n{key} = "{raw}"\n'}
        )
        assert app.config.needs_variant_data_file == str(expected.resolve())
        assert app.config.needs_variant_data == data
