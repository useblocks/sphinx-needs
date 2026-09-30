"""The variant map from ``[variants]``, read through ``ub_project``.

``[variants]`` is the table every tool reading ``ubproject.toml`` shares for the
variant data; ``[needs] variant_data*`` is its legacy location, still read. The
map comes from three routes, and these tests build a real project for each:

* sphinx-needs **absent** -- nothing else computes the map, so this extension
  reads it from the file it already reads, and reports what ``ub_project``
  found (the only route that reports anything);
* sphinx-needs **present with a non-empty map** -- its map is taken as-is, and
  the TOML's variant data is not read at all;
* sphinx-needs **present with an EMPTY map** -- the TOML is read only to decide
  whether that empty map is a loss the guard must refuse.

Every present-route test simulates sphinx-needs with ``_stub_conf``. The
release workflow's compat cell runs this suite against the PUBLISHED
sphinx-needs, and a release that does not read ``[variants]`` would fail any
test here that expected a real sphinx-needs to.

Warnings are asserted by CODE and by the phrases a message has to carry, never
by whole-message equality: the finding texts are ``ub_project``'s, and their
wording is that package's to change.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from sphinx_mounts import warnings as mount_warnings
from sphinx_mounts.config import VariantRuleError
from tests.test_variant_sources import _build, _pages, _stub_conf, make_project

SRC_DIR = Path(__file__).resolve().parent.parent / "src" / "sphinx_mounts"

#: One plain mount (so the host's toctree resolves) and two rules, one fed by
#: each half of the map: ``edition`` comes from the inline table (over the
#: file's value) and ``cpu`` from the data file alone.
RULES = """
[[source.mounts]]
dir = "{bundle}"
mount_at = "mnt"

[[source.variant_sources]]
if = "var.edition == 'pro'"
files = ["hostgated.rst"]

[[source.variant_sources]]
if = "var.cpu == 'arm'"
files = ["gated/**"]
"""

#: The data file: ``edition`` is overridden inline, ``cpu`` is not.
DATA = {"edition": "basic", "cpu": "arm"}

MIGRATED = (
    RULES
    + """
[variants]
data_file = "vd.json"

[variants.data]
edition = "pro"
"""
)

GATED_PAGES = {"hostgated.html", "gated/a.html", "gated/b.html"}


@pytest.fixture(autouse=True)
def _detach_filters():
    """Keep the process-global logger filters from leaking between tests."""
    yield
    mount_warnings.remove_downgrade_filters()


def _project(tmp_path: Path, toml: str, data: object = DATA) -> Path:
    confdir, _ = make_project(tmp_path, toml=toml)
    (confdir / "vd.json").write_text(json.dumps(data), encoding="utf-8")
    return confdir


def _refusal(make_app, confdir: Path, **kwargs) -> str:
    """The message of the hard refusal the build is expected to raise."""
    with pytest.raises(VariantRuleError) as excinfo:
        _build(make_app, confdir, **kwargs)
    message = str(excinfo.value)
    assert message.rstrip().endswith("[mounts.variant_data_unreadable]"), message
    return message


# ---------------------------------------------------------------------------
# sphinx-needs absent: the map is read here
# ---------------------------------------------------------------------------


def test_a_variants_table_is_read_when_sphinx_needs_is_absent(make_app, tmp_path):
    """O1: the slice's purpose. Before it, both gated pages silently vanished.

    Both halves reach the map: ``edition`` from the inline table, over the
    file's value, and ``cpu`` from the file alone. sphinx-needs is importable
    in this environment but not in ``extensions``, so this is also O5.
    """
    confdir = _project(tmp_path, MIGRATED)
    app = _build(make_app, confdir)
    warnings = app._warning.getvalue()
    assert "mounts.variant_rule_unevaluable" not in warnings, warnings
    assert _pages(app) >= GATED_PAGES


def test_both_locations_read_variants_and_warn_once(make_app, tmp_path):
    """O6: ``[variants]`` wins whole, and the ignored ``[needs]`` key is named.

    The ``[needs]`` file would gate both pages off; the build keeps them, so
    ``[variants]`` is what was read. One warning per ignored key, under its
    own suppressible code.
    """
    toml = MIGRATED + '\n[needs]\nvariant_data_file = "x86.json"\n'
    confdir = _project(tmp_path, toml)
    (confdir / "x86.json").write_text(
        json.dumps({"edition": "basic", "cpu": "x86"}), encoding="utf-8"
    )
    app = _build(make_app, confdir)
    warnings = app._warning.getvalue()
    assert warnings.count("mounts.variant_data_location") == 1, warnings
    assert "variant_data_file" in warnings, warnings
    assert _pages(app) >= GATED_PAGES


def test_the_location_warning_is_suppressed_by_its_own_name(make_app, tmp_path):
    """O6's warning fails ``-W``, so it has to be silenceable on its own."""
    toml = MIGRATED + '\n[needs]\nvariant_data_file = "x86.json"\n'
    confdir = _project(tmp_path, toml)
    (confdir / "x86.json").write_text(json.dumps({"cpu": "x86"}), encoding="utf-8")
    app = _build(
        make_app,
        confdir,
        confoverrides={"suppress_warnings": ["mounts.variant_data_location"]},
    )
    assert "variant_data_location" not in app._warning.getvalue()
    assert _pages(app) >= GATED_PAGES


def test_an_unknown_variants_key_is_reported_as_an_unknown_key(make_app, tmp_path):
    """O7: mounts' own code for a key it does not model, and nothing stops."""
    confdir = _project(
        tmp_path, MIGRATED.replace("[variants]\n", "[variants]\nfuture_key = 1\n")
    )
    app = _build(make_app, confdir)
    warnings = app._warning.getvalue()
    assert warnings.count("mounts.unknown_key") == 1, warnings
    assert "future_key" in warnings, warnings
    assert _pages(app) >= GATED_PAGES


def test_the_unknown_key_warning_is_suppressed_by_its_own_name(make_app, tmp_path):
    confdir = _project(
        tmp_path, MIGRATED.replace("[variants]\n", "[variants]\nfuture_key = 1\n")
    )
    app = _build(
        make_app, confdir, confoverrides={"suppress_warnings": ["mounts.unknown_key"]}
    )
    assert "future_key" not in app._warning.getvalue()
    assert _pages(app) >= GATED_PAGES


LEGACY = (
    RULES
    + """
[needs]
variant_data_file = "vd.json"

[needs.variant_data]
edition = "pro"
"""
)


def test_the_legacy_location_is_not_a_warning(make_app, tmp_path):
    """``[needs] variant_data*`` is still read, and saying so is not a warning.

    A deprecation WARNING would fail every ``-W`` build that has not moved.
    """
    confdir = _project(tmp_path, LEGACY)
    app = _build(make_app, confdir)
    assert app._warning.getvalue() == "", app._warning.getvalue()
    assert "legacy location" not in app._status.getvalue()
    assert _pages(app) >= GATED_PAGES


def test_the_legacy_location_is_one_verbose_line(make_app, tmp_path):
    """With ``-v``, one line per key read from ``[needs]``, and still no warning."""
    confdir = _project(tmp_path, LEGACY)
    app = _build(make_app, confdir, verbosity=1)
    assert app._warning.getvalue() == "", app._warning.getvalue()
    lines = [
        line
        for line in app._status.getvalue().splitlines()
        if "legacy location" in line
    ]
    assert len(lines) == 2, lines
    assert all(line.startswith("sphinx-mounts: ") for line in lines), lines
    assert _pages(app) >= GATED_PAGES


def test_a_variants_key_that_is_not_a_table_is_refused(make_app, tmp_path):
    """O8: ``variants = "x"`` read as "no variant data" would be the silent loss."""
    confdir = _project(tmp_path, 'variants = "x"\n' + RULES)
    message = _refusal(make_app, confdir)
    assert "[variants]" in message, message
    assert "sphinx-needs is not installed" in message, message


@pytest.mark.parametrize(
    "tail",
    ['data_file = "nope.json"\n', 'data_file = ""\n'],
    ids=["missing-file", "empty-path"],
)
def test_a_malformed_variants_table_is_refused(make_app, tmp_path, tail: str):
    """O9: a ``[variants]`` that cannot be read has no defensible answer.

    The empty path is refused as one, rather than read as the TOML's own
    directory (C8).
    """
    confdir = _project(tmp_path, RULES + "\n[variants]\n" + tail)
    message = _refusal(make_app, confdir)
    assert "[variants]" in message, message
    assert "ubproject.toml" in message, message


def test_a_needs_key_that_is_not_a_table_is_refused(make_app, tmp_path):
    """O10: ``needs = "x"`` used to be silently no data, and every rule excluded."""
    confdir = _project(tmp_path, 'needs = "x"\n' + RULES)
    message = _refusal(make_app, confdir)
    assert "[needs]" in message, message


def test_an_oversized_json_integer_is_the_wrapped_refusal(make_app, tmp_path):
    """C9: a data file Python cannot convert is this extension's refusal.

    ``json`` raises a bare ``ValueError`` for an integer past the conversion
    limit (#1995), which escaped as Sphinx's raw "Handler ... threw an
    exception" wrapper. The JSON is built here, not kept as a fixture.
    """
    confdir, _ = make_project(
        tmp_path, toml=RULES + '\n[needs]\nvariant_data_file = "big.json"\n'
    )
    (confdir / "big.json").write_text(
        '{"edition": ' + "9" * 5000 + "}", encoding="utf-8"
    )
    message = _refusal(make_app, confdir)
    assert "threw an exception" not in message, message
    assert "sphinx-needs is not installed" in message, message


# ---------------------------------------------------------------------------
# sphinx-needs present, its map empty: the guard, extended to [variants]
# ---------------------------------------------------------------------------


def test_a_variants_table_sphinx_needs_was_never_pointed_at_is_refused(
    make_app, tmp_path
):
    """O2: the ``[needs]`` refusal of today, for the table's new location."""
    confdir = _project(tmp_path, MIGRATED)
    _stub_conf(confdir, "needs_stub_vt_unpointed", inline="{}", file_ref="None")
    message = _refusal(make_app, confdir)
    assert "`[variants]`" in message, message
    assert "needs_from_toml" in message, message


def test_a_variants_table_sphinx_needs_is_not_reading_is_refused(make_app, tmp_path):
    """O3: sphinx-needs is pointed at another file, and the message names it."""
    confdir = _project(tmp_path, MIGRATED)
    (confdir / "other.toml").write_text("", encoding="utf-8")
    _stub_conf(
        confdir,
        "needs_stub_vt_elsewhere",
        inline="{}",
        file_ref="None",
        from_toml="'other.toml'",
    )
    message = _refusal(make_app, confdir)
    assert "`[variants]`" in message, message
    assert "other.toml" in message, message


def test_a_sphinx_needs_that_does_not_read_variants_is_refused(make_app, tmp_path):
    """O4, the new refusal: pointed at this file, and it still came back empty.

    A sphinx-needs that reads ``[variants]`` and is pointed at this file either
    refuses the table itself or resolves exactly the map this file yields. An
    empty map beside a non-empty file is therefore only reachable by one that
    does not read ``[variants]`` -- every release before 9.0.0.
    """
    confdir = _project(tmp_path, MIGRATED)
    _stub_conf(
        confdir,
        "needs_stub_vt_old",
        inline="{}",
        file_ref="None",
        from_toml="'ubproject.toml'",
    )
    message = _refusal(make_app, confdir)
    assert "`[variants]`" in message, message
    assert "EMPTY variant map" in message, message
    assert "9.0.0" in message, message
    assert "`[needs]`" in message, "the other remedy: keep the keys in [needs]"
    assert "[[source.variant_sources]]" in message, "the gating key is named"
    assert "needs_from_toml_table" not in message, message


def test_a_prefixed_sphinx_needs_is_refused_naming_the_prefix(make_app, tmp_path):
    """O4's other cause: ``needs_from_toml_table`` scopes sphinx-needs away.

    With a prefix, sphinx-needs reads ``[<prefix>.variants]`` and never the
    top-level table this extension reads. Upgrading would change nothing, so
    the message must not say to.
    """
    confdir = _project(tmp_path, MIGRATED)
    _stub_conf(
        confdir,
        "needs_stub_vt_prefixed",
        inline="{}",
        file_ref="None",
        from_toml="'ubproject.toml'",
        from_toml_table="['tool']",
    )
    message = _refusal(make_app, confdir)
    assert "needs_from_toml_table" in message, message
    assert "[tool.variants]" in message, message
    assert "9.0.0" not in message, message


@pytest.mark.parametrize(
    ("from_toml", "module"),
    [
        ("None", "needs_stub_vt_bad_unpointed"),
        ("'ubproject.toml'", "needs_stub_vt_bad_old"),
    ],
    ids=["unpointed", "pointed-but-not-reading-variants"],
)
def test_a_malformed_variants_table_is_refused_when_sphinx_needs_has_no_map(
    make_app, tmp_path, from_toml: str, module: str
):
    """O9 with sphinx-needs present: it read nothing here, so it refuses nothing.

    Both ways sphinx-needs can end up with an empty map beside this file --
    never pointed at it, or pointed but not reading ``[variants]`` -- leave
    the malformed table to this extension, and the message must be true of
    either.
    """
    confdir = _project(tmp_path, RULES + '\n[variants]\ndata_file = "nope.json"\n')
    _stub_conf(confdir, module, inline="{}", file_ref="None", from_toml=from_toml)
    message = _refusal(make_app, confdir)
    assert "nope.json" in message, message
    assert "resolved no variant data from this file" in message, message
    assert "not installed" not in message, message


@pytest.mark.parametrize(
    ("tail", "data"),
    [
        ('[variants]\ndata_file = "vd.json"\n', {}),
        ("[variants.data]\n", DATA),
    ],
    ids=["data-file-of-an-empty-object", "empty-inline-table"],
)
def test_a_legitimately_empty_variants_table_is_not_refused(
    make_app, tmp_path, tail: str, data: object
):
    """The new cell's reachable false positive: the file's own map is empty.

    A base-variant data file of ``{}``, or an empty ``[variants.data]``
    placeholder, resolves to an empty map in EVERY sphinx-needs. That is the
    ordinary warn-and-exclude path, not a configuration error.
    """
    confdir = _project(tmp_path, RULES + "\n" + tail, data=data)
    _stub_conf(
        confdir,
        f"needs_stub_vt_empty_{len(tail)}",
        inline="{}",
        file_ref="None",
        from_toml="'ubproject.toml'",
    )
    app = _build(make_app, confdir)
    assert "mounts.variant_rule_unevaluable" in app._warning.getvalue()
    assert "hostgated.html" not in _pages(app)


@pytest.mark.parametrize(
    ("overrides", "module"),
    [
        ({"needs_variant_data_file": "empty.json"}, "needs_stub_vt_dash_d"),
        ({"needs_variant_data.edition": "basic"}, "needs_stub_vt_dash_d_dotted"),
    ],
    ids=["data-file", "dotted-inline-key"],
)
def test_a_dash_d_override_is_not_mistaken_for_an_old_sphinx_needs(
    make_app, tmp_path, overrides: dict[str, str], module: str
):
    """``-D needs_variant_data*`` may legitimately empty what the file fills.

    sphinx-needs drops a ``-D``'d key from both locations before it reads the
    file, so its map can be empty where this extension's own read -- which
    does not apply ``-D`` -- is not. Without the exemption a correct 9.0
    project run with ``-D`` would be refused as an old sphinx-needs.
    """
    confdir = _project(tmp_path, MIGRATED)
    (confdir / "empty.json").write_text("{}", encoding="utf-8")
    _stub_conf(
        confdir,
        module,
        inline="{}",
        file_ref="None",
        from_toml="'ubproject.toml'",
    )
    app = _build(make_app, confdir, confoverrides=overrides)
    assert "hostgated.html" not in _pages(app), "the override is honoured"


def test_both_locations_are_not_reported_twice_when_sphinx_needs_has_a_map(
    make_app, tmp_path
):
    """sphinx-needs reports its own file; a second warning would be noise."""
    toml = MIGRATED + '\n[needs]\nvariant_data_file = "x86.json"\n'
    confdir = _project(tmp_path, toml)
    _stub_conf(
        confdir,
        "needs_stub_vt_both_map",
        inline='{"edition": "pro", "cpu": "arm"}',
        file_ref="None",
        from_toml="'ubproject.toml'",
    )
    app = _build(make_app, confdir)
    assert "mounts." not in app._warning.getvalue(), app._warning.getvalue()
    assert _pages(app) >= GATED_PAGES


def test_both_locations_are_not_reported_twice_when_the_map_is_empty(
    make_app, tmp_path
):
    """The same with an EMPTY map, where this extension does read the file.

    It reads the file only to decide whether to refuse; a finding in it is
    sphinx-needs' to report, and a 9.0 sphinx-needs pointed here already has.
    """
    toml = RULES + '\n[variants.data]\n\n[needs]\nvariant_data_file = "vd.json"\n'
    confdir = _project(tmp_path, toml)
    _stub_conf(
        confdir,
        "needs_stub_vt_both_empty",
        inline="{}",
        file_ref="None",
        from_toml="'ubproject.toml'",
    )
    app = _build(make_app, confdir)
    warnings = app._warning.getvalue()
    assert "variant_data_location" not in warnings, warnings
    assert "mounts.variant_rule_unevaluable" in warnings, warnings


# ---------------------------------------------------------------------------
# The import fence
# ---------------------------------------------------------------------------


def test_sphinx_mounts_never_imports_sphinx_needs():
    """The map comes from ``ub_project`` or from the config, never from an import.

    An import -- even a guarded one -- would make this extension's answer
    depend on which sphinx-needs is installed, which is the version matrix the
    config-only read exists to avoid.
    """
    sources = sorted(SRC_DIR.glob("*.py"))
    assert sources, SRC_DIR
    offenders = []
    for source in sources:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            offenders += [
                f"{source.name}:{node.lineno} {name}"
                for name in names
                if name == "sphinx_needs" or name.startswith("sphinx_needs.")
            ]
    assert not offenders, offenders
