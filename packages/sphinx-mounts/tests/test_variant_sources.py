"""End-to-end coverage for ``[[source.variant_sources]]``.

The reader's whole job is to make ``sphinx-build`` produce the document set the
project's ``ubproject.toml`` describes for the current variant — the same set
ubCode produces from the same file. So these tests build real projects and look
at what came out, rather than at what the reader computed.

Four things are load-bearing enough to have their own sections below:

* the **fold into config values**, which is what makes a gating flip converge
  on the build where it happened, in both directions, with no invalidation
  story of its own;
* the **warning downgrade**, without which ``sphinx-build -W`` fails a build
  that has nothing wrong with it;
* the **hard refusals**, every one of which exists because report-and-drop
  fails open;
* the **variant-data read rule**, which has to give the same answer whether
  sphinx-needs is absent, present-but-not-yet-resolving, or present and
  already resolved.
"""

from __future__ import annotations

import gc
from io import StringIO
import json
import logging as stdlib_logging
import os
from pathlib import Path
import shutil
import textwrap
from typing import Any
import unicodedata

import pytest
from sphinx.application import Sphinx
from sphinx.config import Config as SphinxConfig

from sphinx_mounts import warnings as mount_warnings

FILLER_COUNT = 9
"""Enough extra host pages that a parallel read genuinely engages.

``sphinx-build -j`` chunks the document list, and the ``convert_serializable``
hazard the filter's attachment point exists to avoid is invisible in a build
small enough to stay in one chunk.
"""


@pytest.fixture(autouse=True)
def _detach_filters():
    """Keep the process-global logger filters from leaking between tests.

    The emitting loggers are module-level objects shared by every ``Sphinx``
    application in the process, so a test that installs a filter and never
    builds again would change what the next test sees.
    """
    yield
    mount_warnings.remove_downgrade_filters()


@pytest.fixture(autouse=True)
def _restore_the_shared_source_suffix_default():
    """Undo Sphinx's in-place mutation of a shared, class-level default.

    ``source_suffix``'s registered default is one mutable dict on
    ``Config.config_values``, and ``merge_source_suffix`` (``config-inited``
    priority 800) mutates ``config.source_suffix`` IN PLACE. For a project that
    never sets the confval, that object IS the shared default — so one test
    loading ``myst_parser`` leaves ``.md`` in the default for every later
    ``Config`` in the process.

    That is not cosmetic here: it makes the root-document guard's fence pass
    for the wrong reason. The MyST test below is red against the unfixed reader
    in isolation and green in a module run without this fixture, which is the
    worst possible shape for a regression test.
    """
    option = SphinxConfig.config_values["source_suffix"]
    snapshot = dict(option.default) if isinstance(option.default, dict) else None
    yield
    if snapshot is not None:
        option.default.clear()
        option.default.update(snapshot)


# ---------------------------------------------------------------------------
# Project construction
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def make_project(
    root: Path,
    *,
    toml: str,
    conf_extra: str = "",
    dangling: bool = False,
    srcdir_name: str | None = None,
) -> tuple[Path, Path]:
    """Materialise a host project plus an external bundle.

    :param root: A directory to build inside.
    :param toml: The whole ``ubproject.toml`` body, with ``{bundle}``
        substituted for the bundle's absolute path.
    :param conf_extra: Extra lines appended to ``conf.py``.
    :param dangling: Add a toctree entry naming a document that never exists
        and that no rule mentions — the negative control.
    :param srcdir_name: Put the Sphinx sources in this sub-directory instead of
        beside ``conf.py``, for the layout guard.
    :return: ``(confdir, bundle)``.
    """
    confdir = root / "proj"
    srcdir = confdir if srcdir_name is None else confdir / srcdir_name
    bundle = root / "bundle"

    _write(
        bundle / "index.rst",
        """
        Bundle
        ======

        .. toctree::

           binternal
    """,
    )
    _write(
        bundle / "binternal.rst",
        """
        Bundle internal
        ---------------

        BUNDLE_INTERNAL_MARKER
    """,
    )

    entries = ["hostkeep", "hostgated", "mnt/index", "mnt/binternal"]
    entries += [f"filler{index:02d}" for index in range(FILLER_COUNT)]
    if dangling:
        entries.append("nosuchdoc")
    listed = "\n           ".join(entries)
    _write(
        srcdir / "index.rst",
        f"""
        Host
        ====

        .. toctree::

           {listed}

        .. toctree::
           :glob:

           gated/*
    """,
    )
    for name in ("hostkeep", "hostgated"):
        _write(
            srcdir / f"{name}.rst",
            f"""
            {name.title()}
            {"=" * len(name)}

            {name.upper()}_MARKER
        """,
        )
    for index in range(FILLER_COUNT):
        _write(
            srcdir / f"filler{index:02d}.rst",
            f"""
            Filler {index}
            ============

            Padding so a parallel read chunks.
        """,
        )
    for name in ("a", "b"):
        _write(
            srcdir / "gated" / f"{name}.rst",
            f"""
            Gated {name}
            =========

            GATED_{name.upper()}_MARKER
        """,
        )

    _write(
        confdir / "conf.py",
        f"""
        project = "host"
        author = "tests"
        extensions = ["sphinx_mounts"]
        exclude_patterns: list[str] = []
        master_doc = "index"
        {conf_extra}
    """,
    )
    _write(confdir / "ubproject.toml", toml.replace("{bundle}", bundle.as_posix()))
    return confdir, bundle


_BASE_TOML = """
[[source.mounts]]
dir = "{bundle}"
mount_at = "mnt"

[[source.variant_sources]]
if = "var.edition == 'pro'"
files = ["hostgated.rst", "binternal.rst", "gated/**"]

[needs.variant_data]
edition = "EDITION"
"""


def base_toml(edition: str) -> str:
    """The standard three-arm rule set, for one variant.

    ``hostgated.rst`` and ``binternal.rst`` carry no path separator, so they
    gate by **file name** in every tree — host and mounted alike. ``gated/**``
    carries one, so it is root-anchored and reaches only the host tree.
    """
    return _BASE_TOML.replace("EDITION", edition)


def _build(
    make_app,
    confdir: Path,
    *,
    builddir: Path | None = None,
    freshenv: bool = True,
    **kwargs: Any,
):
    app = make_app(srcdir=confdir, builddir=builddir, freshenv=freshenv, **kwargs)
    app.build()
    return app


def _build_split(confdir: Path, srcdir: Path, builddir: Path):
    """Build with ``srcdir`` and ``confdir`` genuinely different.

    ``SphinxTestApp`` always sets ``confdir = srcdir``, so the layout guard —
    whose whole subject is the two directories disagreeing — has to go through
    ``Sphinx`` itself.
    """
    status, warning = StringIO(), StringIO()
    app = Sphinx(
        srcdir=str(srcdir),
        confdir=str(confdir),
        outdir=str(builddir / "html"),
        doctreedir=str(builddir / "doctrees"),
        buildername="html",
        status=status,
        warning=warning,
        freshenv=True,
    )
    app.build()
    return app


def _fails_under_dash_w(make_app, confdir: Path, builddir: Path) -> bool:
    """Whether ``sphinx-build -W`` would fail this project.

    Two supported Sphinx versions report it two ways: 7.4's
    ``WarningIsErrorFilter`` **raises** from the warning handler, while from 8.2
    plain ``-W`` only sets ``_fail_on_warnings`` and the build fails in the
    epilogue by setting a non-zero status code. Both count as a failure here.
    """
    try:
        app = _build(make_app, confdir, warningiserror=True, builddir=builddir)
    except Exception:
        return True
    return app.statuscode != 0


def _attribution() -> dict[str, str]:
    """The docname -> rule map the installed downgrade filter is holding.

    Read off the emitting loggers rather than off the app, because that is
    where the attribution actually lives and what the filter actually consults.
    An empty map means no filter is installed, which is the correct state for a
    build that excluded nothing.
    """
    for name in mount_warnings.FALLBACK_LOGGER_NAMES:
        for installed in stdlib_logging.getLogger(name).filters:
            if isinstance(installed, mount_warnings.DowngradeFilter):
                return dict(installed._excluded)
    return {}


def _pages(app) -> set[str]:
    outdir = Path(app.outdir)
    return {
        path.relative_to(outdir).as_posix()
        for path in outdir.rglob("*.html")
        if "_static" not in path.parts
    }


# ---------------------------------------------------------------------------
# The fold: which documents exist
# ---------------------------------------------------------------------------


def test_a_false_rule_removes_host_and_mounted_files(make_app, tmp_path):
    """One rule, three arms: a host file, a mounted file, and a glob tree.

    ``binternal.rst`` has no path separator, so it gates by **file name** in
    every tree — host and mounted alike. That reach is the documented footgun,
    and it is what makes a single rule able to narrow a bundle without knowing
    where the bundle is mounted.
    """
    confdir, _ = make_project(tmp_path, toml=base_toml("basic"))
    app = _build(make_app, confdir)
    pages = _pages(app)
    assert "hostkeep.html" in pages
    assert "mnt/index.html" in pages
    assert "hostgated.html" not in pages
    assert "mnt/binternal.html" not in pages
    assert "gated/a.html" not in pages
    assert "gated/b.html" not in pages


def test_a_true_rule_changes_nothing(make_app, tmp_path):
    """Rules only ever narrow, and only when their condition is false."""
    confdir, _ = make_project(tmp_path, toml=base_toml("pro"))
    app = _build(make_app, confdir)
    pages = _pages(app)
    assert {"hostgated.html", "mnt/binternal.html", "gated/a.html"} <= pages


def test_the_verdict_is_folded_into_config_values(make_app, tmp_path):
    """The patterns land in ``exclude_patterns`` and in the mount's ``exclude``.

    Asserted directly, because it is the mechanism a gating flip converges
    through: both confvals are ``rebuild="env"``, so a changed value is a
    config change Sphinx already knows how to act on. A reader that gated
    without touching a config value leaves both byte-identical across a flip.
    """
    confdir, _ = make_project(tmp_path, toml=base_toml("basic"))
    app = _build(make_app, confdir)
    assert "hostgated.rst" in app.config.exclude_patterns
    assert "**/hostgated.rst" in app.config.exclude_patterns
    assert "binternal.rst" in app.config.mounts[0]["exclude"]


def test_a_gating_flip_converges_in_both_directions(make_app, tmp_path):
    """Three builds over one doctree cache: gated, un-gated, gated again.

    Both directions have to converge on the build where the flip happened.
    This is the test the fold exists for — and the one that goes red if the
    mount arm becomes a post-walk filter, because ``config.mounts`` would then
    be byte-identical across the flip and nothing would re-read.
    """
    confdir, _ = make_project(tmp_path, toml=base_toml("pro"))
    builddir = tmp_path / "build"

    first = _build(make_app, confdir, builddir=builddir)
    assert "mnt/binternal.html" in _pages(first)

    _flip(confdir, "pro", "basic")
    second = _build(make_app, confdir, builddir=builddir, freshenv=False)
    assert "mnt/binternal" not in second.env.found_docs
    assert "hostgated" not in second.env.found_docs

    _flip(confdir, "basic", "pro")
    third = _build(make_app, confdir, builddir=builddir, freshenv=False)
    assert "mnt/binternal" in third.env.found_docs
    assert "hostgated" in third.env.found_docs


def _flip(confdir: Path, before: str, after: str) -> None:
    toml = confdir / "ubproject.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace(
            f'edition = "{before}"', f'edition = "{after}"'
        ),
        encoding="utf-8",
    )


MOUNT_ONLY_TOML = """
[[source.mounts]]
dir = "{bundle}"
mount_at = "mnt"

[[source.variant_sources]]
if = "var.edition == 'pro'"
files = ["binternal.rst"]

[needs.variant_data]
edition = "EDITION"
"""


def test_a_mount_only_flip_converges(make_app, tmp_path):
    """The mount arm's fold reaches a mount even when no host file is named.

    This does NOT isolate ``config.mounts`` as the invalidator, and an earlier
    version of this docstring claimed it did. Measured: the fold appends the
    translated host patterns for **every** false rule whether or not a host
    file matches, so ``exclude_patterns`` changes across this flip too and
    Sphinx reports ``[config changed ('exclude_patterns')]``. No configuration
    can isolate the mounts value, because both always move together.

    That behaviour is kept deliberately — it mirrors the sibling reader's
    append-to-every-root and is harmless — so what this test is worth is the
    other half: if the mount arm stopped folding, the gated document would
    still be built, and the assertions below would catch it.
    """
    confdir, _ = make_project(tmp_path, toml=MOUNT_ONLY_TOML.replace("EDITION", "pro"))
    builddir = tmp_path / "build"
    first = _build(make_app, confdir, builddir=builddir)
    assert "mnt/binternal" in first.env.found_docs

    _flip(confdir, "pro", "basic")
    second = _build(make_app, confdir, builddir=builddir, freshenv=False)
    assert "mnt/binternal" not in second.env.found_docs
    assert "mnt/index" in second.env.found_docs

    _flip(confdir, "basic", "pro")
    third = _build(make_app, confdir, builddir=builddir, freshenv=False)
    assert "mnt/binternal" in third.env.found_docs


def test_the_stale_output_caveat_is_real(make_app, tmp_path):
    """The gated page stays on disk after a flip, live and URL-reachable.

    Upstream behaviour — Sphinx does not delete output for removed documents —
    but it is the single most important operational consequence of this
    feature, so it is pinned here rather than only described in the docs. A
    per-variant CI publishing ``_build/html`` from a warm build directory ships
    the gated page.
    """
    confdir, _ = make_project(tmp_path, toml=base_toml("pro"))
    builddir = tmp_path / "build"
    _build(make_app, confdir, builddir=builddir)
    _flip(confdir, "pro", "basic")
    second = _build(make_app, confdir, builddir=builddir, freshenv=False)

    assert "hostgated" not in second.env.found_docs
    assert (Path(second.outdir) / "hostgated.html").exists(), (
        "Sphinx does not delete output for removed documents; build each "
        "variant into its own -d and output directory, or use -E with a clean "
        "outdir."
    )


@pytest.mark.parametrize(
    "pattern",
    ["binternal.rst", "bundle/binternal.rst", "bundle/**", "*/binternal.rst"],
    ids=["basename", "path", "tree", "wildcard-dir"],
)
def test_a_file_list_mount_is_not_gated_by_any_rule_spelling(
    make_app, tmp_path, pattern: str
):
    """Parity: neither reader gates a file-list mount, under any spelling.

    ubCode cannot gate one — a ``files`` mount's entries are pushed straight
    into its result with no include or exclude consulted, and a variant rule
    reaches its discovery only through ``extend_exclude``
    (``rust/ubc_config/src/resolved.rs``). This reader used to gate one by
    basename, which put a file in ubCode's build and not in Sphinx's from one
    rule string — a divergence in the removes-more-here direction, and exactly
    what this key must never do.

    So the arm is gone rather than completed, and this test is what keeps it
    gone. Every spelling is exercised because "not gated" has to hold for the
    path forms too, not only the basename one that used to fire.
    """
    toml = f"""
    [[source.mounts]]
    files = ["{{bundle}}/index.rst", "{{bundle}}/binternal.rst"]
    mount_at = "mnt"

    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["{pattern}"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    app = _build(make_app, confdir)
    pages = _pages(app)
    assert "mnt/index.html" in pages
    assert "mnt/binternal.html" in pages, (
        "a file-list mount must survive every rule spelling, because ubCode's "
        "cannot be gated at all"
    )


def test_a_directory_mount_beside_a_file_list_mount_is_still_gated(make_app, tmp_path):
    """The limitation is per mount MODE, not per project.

    Dropping the file-list arm must not quietly stop gating the directory
    mounts in the same project — which is what a coarser "skip mounts when any
    is a file list" fix would have done.
    """
    toml = """
    [[source.mounts]]
    files = ["{bundle}/index.rst"]
    mount_at = "flat"

    [[source.mounts]]
    dir = "{bundle}"
    mount_at = "mnt"

    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["binternal.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    app = _build(make_app, confdir)
    pages = _pages(app)
    assert "flat/index.html" in pages
    assert "mnt/index.html" in pages
    assert "mnt/binternal.html" not in pages


def test_a_conf_py_mount_is_gated_too(make_app, tmp_path):
    """The legacy ``conf.py`` mount list gets the same fold.

    A variant rule must not mean one thing in TOML and another in ``conf.py``.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["binternal.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, bundle = make_project(tmp_path, toml=toml)
    conf = confdir / "conf.py"
    conf.write_text(
        conf.read_text(encoding="utf-8")
        + f"\nmounts = [{{'dir': r'{bundle}', 'mount_at': 'mnt'}}]\n",
        encoding="utf-8",
    )
    app = _build(make_app, confdir)
    assert "mnt/index.html" in _pages(app)
    assert "mnt/binternal.html" not in _pages(app)


def test_a_conf_py_mountconfig_instance_is_gated_too(make_app, tmp_path):
    """The `conf.py` dataclass path, which no test used to reach.

    ``parse_mounts`` documents ``mounts`` as "a sequence of mappings **or**
    ``MountConfig`` instances", and the fold has a dedicated branch for the
    second shape that a plain dict never exercises. Both mount modes are
    asserted: a directory mount gated, a file-list mount NOT gated — the same
    parity the TOML path keeps.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["binternal.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, bundle = make_project(tmp_path, toml=toml)
    conf = confdir / "conf.py"
    conf.write_text(
        conf.read_text(encoding="utf-8")
        + "\nfrom pathlib import Path\n"
        + "from sphinx_mounts.config import MountConfig\n"
        + f"mounts = [MountConfig(dir=Path(r'{bundle}'), mount_at='mnt'),\n"
        + f"          MountConfig(files=(Path(r'{bundle}/binternal.rst'),),"
        + " mount_at='flat')]\n",
        encoding="utf-8",
    )
    app = _build(make_app, confdir)
    pages = _pages(app)
    assert "mnt/index.html" in pages
    assert "mnt/binternal.html" not in pages, "the directory mount is gated"
    assert "flat/binternal.html" in pages, "the file-list mount is not"


# ---------------------------------------------------------------------------
# The downgrade
# ---------------------------------------------------------------------------


def test_a_gated_project_builds_clean_under_dash_w(make_app, tmp_path):
    """``-W`` on a correctly configured variant build exits 0.

    Three warnings would otherwise fire, one per arm: ``toc.excluded`` for the
    host file, ``toc.not_readable`` for the mounted one, and the type-less
    "glob matched nothing" for the ``:glob:`` tree. All three are attributable
    to a rule, so all three are reclassified rather than counted.
    """
    confdir, _ = make_project(tmp_path, toml=base_toml("basic"))
    app = _build(make_app, confdir, warningiserror=True)
    assert "WARNING" not in app._warning.getvalue()
    assert app.statuscode == 0


def test_a_gated_project_builds_clean_under_dash_w_parallel(make_app, tmp_path):
    """The same, under a parallel read.

    This is the cell a handler-level filter fails: the worker serialises its
    buffered records with ``convert_serializable``, which does ``r.args = ()``,
    so any attribution that reads ``record.args[0]`` in the parent silently
    stops matching. Attaching to the emitting child logger runs the filter in
    whatever process emits, before that call.
    """
    confdir, _ = make_project(tmp_path, toml=base_toml("basic"))
    app = _build(make_app, confdir, warningiserror=True, parallel=2)
    assert "WARNING" not in app._warning.getvalue()
    assert app.statuscode == 0


def test_a_gated_project_builds_clean_under_exception_on_warning(make_app, tmp_path):
    """``--exception-on-warning`` raises from a *handler* filter.

    A logger filter is upstream of every handler filter, so the record is
    already an INFO by the time ``_RaiseOnWarningFilter`` could look at it.
    """
    confdir, _ = make_project(tmp_path, toml=base_toml("basic"))
    app = _build(make_app, confdir, warningiserror=True, exception_on_warning=True)
    assert "WARNING" not in app._warning.getvalue()
    assert app.statuscode == 0


def test_the_downgraded_records_are_still_reported(make_app, tmp_path):
    """Downgraded, never dropped — asserted by PRESENCE, not by absence.

    The reference is the only place left where a rule that removed more than
    the author meant is still visible: the file itself is gone from search,
    ``objects.inv``, cross-references and the page tree. A filter returning
    ``False`` would make an over-broad rule completely silent.
    """
    confdir, _ = make_project(tmp_path, toml=base_toml("basic"))
    app = _build(make_app, confdir)
    status = app._status.getvalue()
    assert status.count(mount_warnings.VARIANT_EXCLUDED_CODE) >= 3
    assert "'hostgated'" in status
    assert "'mnt/binternal'" in status
    assert "'gated/*'" in status
    assert "var.edition == 'pro'" in status, "the rule that removed it is named"


def test_an_unattributed_missing_document_still_warns(make_app, tmp_path):
    """The negative control: a genuinely broken reference is untouched.

    A downgrade that fired on any missing document would be a way to hide
    typos, which is exactly what makes ``suppress_warnings`` the wrong tool
    here. ``nosuchdoc`` is in no rule's file set, so it stays a warning and
    still fails ``-W``.
    """
    confdir, _ = make_project(tmp_path, toml=base_toml("basic"), dangling=True)
    app = _build(make_app, confdir)
    warning = app._warning.getvalue()
    assert "nosuchdoc" in warning
    assert "WARNING" in warning

    assert _fails_under_dash_w(make_app, confdir, tmp_path / "b2")


def test_a_warning_about_an_asset_path_is_never_downgraded(make_app, tmp_path):
    """The attribution diff must use discovery's REAL inputs.

    ``find_files`` excludes ``exclude_patterns + templates_path +
    builder.get_asset_paths()``. Omitting the third put every source file under
    ``html_extra_path`` / ``html_static_path`` into the "before" set, so gating
    one of them minted a **phantom** docname — a name that was not a document
    in this variant and not a document in any variant.

    One phantom is enough to break the promise the whole downgrade rests on. In
    this project a ``:glob:`` toctree over ``legacy/*`` matches nothing in
    EVERY variant, because ``legacy/`` is an asset path and is never
    discovered. That warning is genuine and version-independent — and flipping
    the variant used to make it disappear, taking the ``-W`` failure with it.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["old.rst"]

    [needs.variant_data]
    edition = "EDITION"
    """
    for edition in ("pro", "basic"):
        confdir, _ = make_project(
            tmp_path / edition,
            toml=toml.replace("EDITION", edition),
            conf_extra='html_extra_path = ["legacy"]',
        )
        _write(
            confdir / "legacy" / "old.rst",
            """
            Legacy
            ======
        """,
        )
        index = confdir / "index.rst"
        index.write_text(
            index.read_text(encoding="utf-8")
            + "\n.. toctree::\n   :glob:\n\n   legacy/*\n",
            encoding="utf-8",
        )
        app = _build(make_app, confdir)
        warning = app._warning.getvalue()
        assert "legacy/*" in warning, (
            f"edition={edition}: the empty-glob warning is genuine in every "
            f"variant and must survive as a WARNING"
        )
        assert mount_warnings.VARIANT_EXCLUDED_CODE not in warning
        assert _fails_under_dash_w(make_app, confdir, tmp_path / edition / "b2"), (
            f"edition={edition}: and it must still fail -W"
        )


def _non_ascii_project(tmp_path, file_form: str):
    """A project gating ``café.rst``, the FILE written in ``file_form``."""
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["café.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    name = unicodedata.normalize(file_form, "café.rst")
    _write(
        confdir / name,
        """
        Cafe
        ====
    """,
    )
    index = confdir / "index.rst"
    index.write_text(
        index.read_text(encoding="utf-8").replace(
            "   hostkeep",
            "   " + unicodedata.normalize("NFC", "café") + "\n   hostkeep",
        ),
        encoding="utf-8",
    )
    return confdir


def _assert_cafe_downgraded(app):
    nfc = unicodedata.normalize("NFC", "café")
    assert nfc + ".html" not in _pages(app)
    # The toctree reference to it is downgraded, not left as a warning. Only
    # this docname is asserted on: the shared fixture's index also names a
    # mount that this project does not declare, and that warning is genuine.
    warning = app._warning.getvalue()
    assert nfc not in warning and "caf" not in warning
    assert nfc in app._status.getvalue()
    assert mount_warnings.VARIANT_EXCLUDED_CODE in app._status.getvalue()


def test_a_non_ascii_docname_is_attributed(make_app, tmp_path):
    """A gated non-ASCII document is attributed and downgraded — everywhere.

    The file is written in NFC, the form a git checkout carries on every
    platform, so this half of the fence runs unconditionally.
    """
    confdir = _non_ascii_project(tmp_path, "NFC")
    _assert_cafe_downgraded(_build(make_app, confdir))


def test_an_nfd_named_file_is_attributed_where_the_filesystem_equates_forms(
    make_app, tmp_path
):
    """The attribution set and ``found_docs`` must agree on Unicode form.

    ``Project.path2doc`` NFC-normalises via ``path_stabilize``, and macOS
    filesystems hand ``os.scandir`` NFD names while everything authored is
    NFC — so a reader keying the attribution set off a raw path would key it
    in NFD and the downgrade would miss. ``_docname_for`` NFC-normalises to
    close that, and this test writes the FILE in NFD to prove it.

    The scenario only EXISTS on a normalization-insensitive filesystem
    (macOS): released Sphinx 8/9 NFC-normalise inside ``get_matching_files``
    and stat the NFC name, and 7.4 reads back the docname's NFC path — so on
    a byte-exact filesystem (ext4) an NFD-named file referenced in NFC is
    invisible or unreadable to Sphinx ITSELF, in every variant, and the
    surviving warning is genuine rather than variant-caused. Probed at
    runtime rather than by platform name, because the property belongs to
    the filesystem, not the OS.

    History: this fence first ran only on macOS-backed environments, where a
    "get_matching_files already NFC-normalises" measurement looked
    universal; Linux CI proved the SCENARIO (not just the measurement) was
    platform-bound, hence the split and the probe.
    """
    confdir = _non_ascii_project(tmp_path, "NFD")
    nfc_name = unicodedata.normalize("NFC", "café.rst")
    if not (confdir / nfc_name).is_file():
        pytest.skip(
            "byte-exact filesystem: an NFD-named file is invisible to Sphinx "
            "itself under its NFC name, so the scenario cannot be constructed"
        )
    _assert_cafe_downgraded(_build(make_app, confdir))


def test_a_docname_another_file_still_provides_is_not_downgraded(make_app, tmp_path):
    """Gating one of two files that map to one docname leaves the doc ALIVE.

    ``Project.discover`` keeps the first file claiming a docname and warns
    about the rest, so ``a.rst`` beside ``a.md`` is one document. Diffing FILE
    NAMES rather than docnames marked ``a`` excluded when only ``a.md`` was
    gated — and then silently downgraded every toctree reference to a document
    that is very much in the build. A fail-open in the opposite direction from
    the phantom case, and invisible to the negative control.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["dup.md"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(
        tmp_path, toml=toml, conf_extra='extensions.append("myst_parser")'
    )
    _write(
        confdir / "dup.rst",
        """
        Dup from RST
        ============

        DUP_RST_MARKER
    """,
    )
    _write(confdir / "dup.md", "# Dup from Markdown\n\nDUP_MD_MARKER\n")
    index = confdir / "index.rst"
    index.write_text(
        index.read_text(encoding="utf-8").replace("   hostkeep", "   dup\n   hostkeep"),
        encoding="utf-8",
    )
    app = _build(make_app, confdir)
    assert "dup.html" in _pages(app), "the .rst file still provides the docname"
    assert "DUP_RST_MARKER" in (Path(app.outdir) / "dup.html").read_text(
        encoding="utf-8"
    )
    # Asserted on the attribution set itself, not on a build outcome: with
    # today's Sphinx warning inventory no warning names a docname that is IN
    # the build, so a polluted set is a LATENT fail-open — every future warning
    # naming `dup` would be wrongly downgraded, and nothing today would notice.
    # The set is where the defect lives, so the set is what is fenced.
    assert "dup" not in _attribution()
    assert mount_warnings.VARIANT_EXCLUDED_CODE not in app._status.getvalue()


def test_the_root_document_guard_sees_an_extension_registered_suffix(
    make_app, tmp_path
):
    """A MyST project with an ``index.md`` root document.

    An extension registers a suffix with ``app.add_source_suffix``, which
    writes ``app.registry.source_suffix`` — a different place from the
    ``source_suffix`` confval, which such a project never touches. Reading only
    the confval made the guard test ``patmatch('index.rst', 'index.md')``, pass
    the rule, and hand the user Sphinx's abort naming ``index.rst``: a file
    that does not exist, which is worse than the misleading message the guard
    exists to prevent.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["index.md"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(
        tmp_path, toml=toml, conf_extra='extensions.append("myst_parser")'
    )
    (confdir / "index.rst").unlink()
    _write(confdir / "index.md", "# Host\n\n```{toctree}\nhostkeep\n```\n")
    with pytest.raises(Exception) as excinfo:
        _build(make_app, confdir)
    message = str(excinfo.value)
    assert "root document" in message
    assert "variant_root_doc" in message
    assert "unable to load the master document" not in message


def test_a_second_build_in_one_process_keeps_its_own_warnings(make_app, tmp_path):
    """The cross-application leak, end to end and in one process.

    Project A gates ``hostgated`` by a false rule. Project B is a different
    project with no ``ubproject.toml`` at all, whose index names a genuinely
    missing ``hostgated``. If A's filter is still attached when B builds, B's
    broken reference is silenced and attributed to a rule in a project it has
    never heard of — and ``_warncount`` drops by one, so a ``-W`` build that
    should fail passes.

    The two builds share a test function on purpose: the module's autouse
    detach fixture must not run between them, or the production code being
    tested is never the thing under test.
    """
    a_toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir_a, _ = make_project(tmp_path / "a", toml=a_toml)
    app_a = _build(make_app, confdir_a)
    assert "hostgated.html" not in _pages(app_a)
    assert mount_warnings.VARIANT_EXCLUDED_CODE in app_a._status.getvalue()
    assert _attribution() == {}, "the filter comes off when A's build ends"

    root_b = tmp_path / "b"
    (root_b / "proj").mkdir(parents=True)
    _write(
        root_b / "proj" / "conf.py",
        """
        project = "b"
        author = "tests"
        extensions = ["sphinx_mounts"]
        master_doc = "index"
    """,
    )
    _write(
        root_b / "proj" / "index.rst",
        """
        B
        =

        .. toctree::

           hostgated
    """,
    )
    app_b = _build(make_app, root_b / "proj")
    warning = app_b._warning.getvalue()
    assert "hostgated" in warning
    assert "WARNING" in warning, "B's genuine broken reference must survive"
    assert mount_warnings.VARIANT_EXCLUDED_CODE not in warning
    assert app_b._warncount >= 1


def test_a_second_build_of_one_application_still_downgrades(make_app, tmp_path):
    """``Sphinx.build()`` may be called more than once, and each build needs it.

    The install used to sit on ``builder-inited``, which fires once per
    application *construction*. So the first build of an application was
    protected and every later one ran unfiltered: a correctly configured
    variant project emitted its variant-excluded toctree warning
    un-downgraded and returned a failing status under ``-W`` on rebuild.

    ``Sphinx.build(force_all=…)`` exists precisely for repeated builds, so this
    is in-contract usage — not the interleaved-applications shape the module
    declares out of contract.
    """
    confdir, _ = make_project(tmp_path, toml=base_toml("basic"))
    app = make_app(srcdir=confdir, freshenv=True, warningiserror=True)
    app.build()
    first = app._warning.getvalue()
    assert "WARNING" not in first
    assert app.statuscode == 0

    app.build(force_all=True)
    second = app._warning.getvalue()
    assert "WARNING" not in second, (
        "the second build must downgrade too; it used to emit "
        "`toctree contains reference to excluded document` un-downgraded"
    )
    assert "toctree contains reference" not in second
    assert app.statuscode == 0
    assert app._status.getvalue().count(mount_warnings.VARIANT_EXCLUDED_CODE) >= 6, (
        "both builds reported the downgrade"
    )


def test_an_application_that_never_builds_does_not_leak_its_filter(make_app, tmp_path):
    """The leak per-application keying could not close.

    Project A declares rules and is **constructed but never built**, so it
    never reaches ``build-finished`` and its filter has no other way off.
    Keying removal by owner left it attached; a ``weakref`` liveness sweep did
    not help either, because a ``Sphinx`` application stays reachable from
    process-global state and is never collected — measured, ``del`` plus an
    explicit ``gc.collect()`` does not free it.

    Project B has no ``ubproject.toml`` at all and an index naming a genuinely
    missing document. Its warning must survive and must still count, or a
    ``-W`` build that should fail passes for a reason in a project it has never
    heard of.
    """
    a_toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir_a, _ = make_project(tmp_path / "a", toml=a_toml)
    app_a = make_app(srcdir=confdir_a, freshenv=True)  # constructed, NOT built
    assert app_a is not None
    del app_a
    gc.collect()

    root_b = tmp_path / "b"
    (root_b / "proj").mkdir(parents=True)
    _write(
        root_b / "proj" / "conf.py",
        """
        project = "b"
        author = "tests"
        extensions = ["sphinx_mounts"]
        master_doc = "index"
    """,
    )
    _write(
        root_b / "proj" / "index.rst",
        """
        B
        =

        .. toctree::

           hostgated
    """,
    )
    app_b = _build(make_app, root_b / "proj")
    warning = app_b._warning.getvalue()
    assert "hostgated" in warning
    assert "WARNING" in warning, "B's genuine broken reference must survive"
    assert mount_warnings.VARIANT_EXCLUDED_CODE not in warning
    assert app_b._warncount >= 1


def test_the_filter_loggers_resolve_from_sphinx_itself(make_app, tmp_path):
    """The seam is derived from Sphinx's own modules, not hard-coded.

    The names are a function of Sphinx's module layout, so a module move
    upstream would un-hook the filter in silence. Resolving them from the
    modules' own logger objects makes such a move a loud fallback instead —
    and this test is what notices if the fallback is ever the *only* path.
    """
    names, degraded = mount_warnings.resolve_toctree_logger_names()
    assert degraded == (), f"fell back to hard-coded names: {degraded}"
    assert names == mount_warnings.FALLBACK_LOGGER_NAMES


# ---------------------------------------------------------------------------
# The hard refusals
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pattern", "match"),
    [
        ("docs/{a,b}/**", "alternation"),
        ("../outside/**", "climb"),
        ("/abs.rst", "absolute"),
        ("a?c/x.rst", r"`\?`"),
    ],
    ids=["braces", "climb", "absolute", "question-mark"],
)
def test_a_refused_glob_refuses_the_configuration(
    make_app, tmp_path, pattern: str, match: str
):
    """Not a warning that skips the rule — the whole configuration is refused.

    Skipping the rule would leave every file it names in the build, including
    the files its *other*, perfectly valid patterns name, behind a diagnostic
    the project could suppress. For a key whose only purpose is keeping content
    out of a build, failing open is the one outcome that must not be possible.
    """
    toml = f"""
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst", "{pattern}"]

    [needs.variant_data]
    edition = "pro"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    with pytest.raises(Exception, match=match):
        _build(make_app, confdir)


@pytest.mark.parametrize(
    "pattern", ["", "docs/", "**/", "docs/**/"], ids=["empty", "dir", "any", "deep"]
)
def test_a_pattern_that_means_two_things_is_refused_before_it_wipes_a_mount(
    make_app, tmp_path, pattern: str
):
    """The refusal that costs the most if it is missing.

    An empty pattern — a typo, a trailing comma, a templated value that came
    out blank — selects NOTHING under the authored dialect and EVERY file in a
    mount's walk. Before this refusal, ``files = [""]`` deleted an entire
    mounted bundle, left the host untouched, and reported ``build succeeded``
    with no warning at all: one rule string producing two document sets inside
    a single build, which is the exact hazard the dialect layer exists to
    remove. A trailing separator is the same shape, one subtree smaller.
    """
    toml = f"""
    [[source.mounts]]
    dir = "{{bundle}}"
    mount_at = "mnt"

    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["{pattern}"]

    [needs.variant_data]
    edition = "pro"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    with pytest.raises(Exception, match="variant_glob_dialect"):
        _build(make_app, confdir)


def test_a_literal_bracketed_wildcard_is_not_refused(make_app, tmp_path):
    """A ``?`` inside a character class is a literal in all three engines.

    Refusing it would abort every build of a project over a pattern that
    carries no hazard at all, which is the cost of testing the raw string
    rather than the pattern with its classes blanked out.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["gated/[?]missing.rst", "hostgated.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    app = _build(make_app, confdir)
    assert "hostgated.html" not in _pages(app)
    assert "hostkeep.html" in _pages(app)


def test_every_refused_glob_is_listed_at_once(make_app, tmp_path):
    """Fixing one refusal only to meet the next on the following build is the
    experience this avoids, and it is cheap to avoid: the check is a pure
    function of the pattern text."""
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["{a,b}.rst", "../up.rst", "/abs.rst"]

    [needs.variant_data]
    edition = "pro"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    with pytest.raises(Exception) as excinfo:
        _build(make_app, confdir)
    message = str(excinfo.value)
    assert "3 `variant_sources` glob(s)" in message
    assert "{a,b}.rst" in message
    assert "../up.rst" in message
    assert "/abs.rst" in message


def test_an_out_of_grammar_condition_refuses_the_configuration(make_app, tmp_path):
    """A condition outside the grammar is statically knowable, so it is a
    configuration error rather than something to evaluate."""
    toml = """
    [[source.variant_sources]]
    if = "var.debug"
    files = ["hostgated.rst"]

    [needs.variant_data]
    debug = false
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    with pytest.raises(Exception, match="outside the rule grammar"):
        _build(make_app, confdir)


def test_a_rule_that_would_remove_the_root_document_is_refused(make_app, tmp_path):
    """Sphinx's own abort blames the source directory for an exclusion.

    *"Sphinx is unable to load the master document … The master document must
    be within the source directory or a subdirectory of it"* is actively
    misleading for this cause: the document is inside the source directory,
    and excluded. That message must never be reachable through a variant rule.

    Variant-*dependent*, unlike the glob refusal: the same rule with a true
    condition is a perfectly legal "this whole tree, this variant only".
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["index.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    with pytest.raises(Exception) as excinfo:
        _build(make_app, confdir)
    message = str(excinfo.value)
    assert "root document" in message
    assert "unable to load the master document" not in message


def test_the_same_root_document_rule_is_fine_while_its_condition_holds(
    make_app, tmp_path
):
    """The variant-dependence of the root-doc guard, from the other side."""
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["index.rst"]

    [needs.variant_data]
    edition = "pro"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    app = _build(make_app, confdir)
    assert "index.html" in _pages(app)


def test_a_non_identity_layout_is_refused(tmp_path):
    """A rule glob and an ``exclude_patterns`` entry must share a base.

    When they do not, a prefix-shifted rewrite is mechanically possible for a
    path-naming pattern and has no correct form at all for a basename-matching
    one — and gating only the root that happens to coincide is the failure the
    whole feature exists to prevent. The message names both directories and the
    one-line fix.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml, srcdir_name="source")
    with pytest.raises(Exception) as excinfo:
        _build_split(confdir, confdir / "source", tmp_path / "build")
    message = str(excinfo.value)
    assert "source directory" in message
    assert "[source] dir = 'source'" in message, "the STRING form ubCode accepts"
    assert "DISCOVERY root" in message, "and the warning about widening it"


def test_a_declared_source_dir_makes_a_split_layout_identity(tmp_path):
    """The escape hatch the refusal points at, exercised.

    ``[source] dir`` is the same key ubCode reads for the same purpose, so a
    project that declares it is describing its layout once for both tools.
    """
    toml = """
    [source]
    dir = "source"

    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml, srcdir_name="source")
    app = _build_split(confdir, confdir / "source", tmp_path / "build")
    assert "hostgated.html" not in _pages(app)
    assert "hostkeep.html" in _pages(app)


def test_an_array_source_dir_is_refused_by_name(make_app, tmp_path):
    """``[source] dir`` is a STRING, and accepting an array is a divergence.

    Sibling readers of this same file declare the key as one path and reject
    any other shape, so a project that wrote the array form would build here
    and be unreadable to them. This refusal used to be worse than absent: the
    layout message *advised* the array form, which is a remedy that breaks the
    other reader of the shared file.
    """
    toml = """
    [source]
    dir = ["source"]

    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml, srcdir_name="source")
    with pytest.raises(Exception, match="must be a string"):
        _build_split(confdir, confdir / "source", tmp_path / "build")


def test_the_legacy_project_srcdir_is_read_as_the_anchor(tmp_path):
    """``[project] srcdir`` still anchors rule globs when ``[source] dir`` is unset.

    Reading only ``[source] dir`` was a fail-OPEN hole: a project on the legacy
    key anchored its rules at the TOML's directory here and at
    ``<toml dir>/<srcdir>`` in the sibling reader, and the layout guard — whose
    entire job is to make that impossible — passed on the wrong root with
    nothing said.
    """
    toml = """
    [project]
    srcdir = "source"

    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml, srcdir_name="source")
    app = _build_split(confdir, confdir / "source", tmp_path / "build")
    assert "hostgated.html" not in _pages(app)
    assert "hostkeep.html" in _pages(app)


def test_a_source_dir_wins_over_the_legacy_srcdir(tmp_path):
    """The precedence the sibling reader uses: ``dir`` first, then ``srcdir``."""
    toml = """
    [project]
    srcdir = "elsewhere"

    [source]
    dir = "source"

    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml, srcdir_name="source")
    app = _build_split(confdir, confdir / "source", tmp_path / "build")
    assert "hostgated.html" not in _pages(app)


def test_a_conf_py_mount_with_a_relative_dir_is_attributed(
    make_app, tmp_path, monkeypatch
):
    """A relative ``conf.py`` mount dir gated but was never attributed.

    TOML mount paths are absolutised at priority 400, before the fold;
    ``conf.py`` ones are absolutised at 500, *after* it. The fold recorded the
    relative path as written, so the attribution walk resolved it against the
    process's working directory, found nothing, and dropped the whole mount's
    attribution — while the fold still gated its files. The result was the
    worst combination available: the pages gone AND the warnings not
    downgraded, so every variant build of such a project failed under ``-W``.

    The working directory is moved away from ``confdir`` on purpose: that is
    what separates "resolved against confdir" from "happened to work".
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["binternal.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, bundle = make_project(tmp_path, toml=toml)
    relative = os.path.relpath(bundle, confdir)
    conf = confdir / "conf.py"
    conf.write_text(
        conf.read_text(encoding="utf-8")
        + f"\nmounts = [{{'dir': r'{relative}', 'mount_at': 'mnt',"
        + " 'attach_to': 'index'}]\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    app = _build(make_app, confdir)
    assert "mnt/index.html" in _pages(app)
    assert "mnt/binternal.html" not in _pages(app)
    # The toctree references must be DOWNGRADED, not merely emitted. Asserting
    # on the toctree warnings rather than on a globally clean `-W` keeps the
    # test independent of unrelated cross-application noise in a shared
    # process; the `-W` legs elsewhere in this module cover the global posture.
    assert "toctree contains reference" not in app._warning.getvalue()
    assert mount_warnings.VARIANT_EXCLUDED_CODE in app._status.getvalue()


# ---------------------------------------------------------------------------
# Warn-and-exclude, and the safe drop
# ---------------------------------------------------------------------------


def test_an_unevaluable_condition_warns_and_excludes(make_app, tmp_path):
    """An unknown ``var.*`` key is data-dependent, so it is not a grammar error.

    Both engines fail to evaluate it the same way and both then exclude —
    warn-and-exclude, the contract the ``.. if::`` directive already has, and
    the safe direction for a rule whose purpose is keeping content out.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.missing == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "pro"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    app = _build(make_app, confdir)
    assert "mounts.variant_rule_unevaluable" in app._warning.getvalue()
    assert "hostgated.html" not in _pages(app)


def test_a_rule_naming_no_files_is_dropped(make_app, tmp_path):
    """The one safe drop: a rule that named nothing has nothing to leak."""
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = []

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    app = _build(make_app, confdir)
    assert "mounts.variant_rule_dropped" in app._warning.getvalue()
    assert "hostgated.html" in _pages(app)


def test_an_unknown_rule_key_is_reported_and_ignored(make_app, tmp_path):
    """Forward compatibility with a reader that models more keys than this one.

    The same posture mount entries take, and ubCode's
    ``config.variant_source_unknown_key``.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]
    wehn = "typo"

    [needs.variant_data]
    edition = "pro"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    app = _build(make_app, confdir)
    warning = app._warning.getvalue()
    assert "mounts.unknown_key" in warning
    assert "wehn" in warning
    assert "hostgated.html" in _pages(app)


# ---------------------------------------------------------------------------
# The variant-data read rule
# ---------------------------------------------------------------------------


NEEDS_STUB = """
def setup(app):
    app.add_config_value("needs_variant_data", {inline}, "env")
    app.add_config_value("needs_variant_data_file", {file_ref}, "env")
    app.add_config_value("needs_from_toml", {from_toml}, "env")
    return {{"parallel_read_safe": True, "parallel_write_safe": True}}
"""


def _stub_conf(
    confdir: Path,
    module: str,
    inline: str,
    file_ref: str,
    from_toml: str = "None",
) -> None:
    """Register the two sphinx-needs confvals without sphinx-needs.

    Simulating the confvals directly is what makes all three cells of the
    matrix reachable deterministically: which cell a real sphinx-needs puts a
    project in depends on which release is installed, and the whole point of
    the unconditional re-merge is that the reader does not have to know.

    ``module`` must be unique per test. ``sys.modules`` is process-global and
    survives a ``SphinxTestApp``'s ``sys.path`` restore, so two tests sharing a
    stub name would silently share the first one's confval defaults — and the
    second test would then pass or fail for the wrong reason.
    """
    _write(
        confdir / f"{module}.py",
        NEEDS_STUB.format(inline=inline, file_ref=file_ref, from_toml=from_toml),
    )
    conf = confdir / "conf.py"
    conf.write_text(
        conf.read_text(encoding="utf-8").replace(
            'extensions = ["sphinx_mounts"]',
            "import os, sys; sys.path.insert(0, os.path.dirname(__file__))\n"
            f'extensions = ["{module}", "sphinx_mounts"]',
        ),
        encoding="utf-8",
    )


FILE_TOML = """
[[source.variant_sources]]
if = "var.edition == 'pro' and var.build.debug == True"
files = ["hostgated.rst"]

[needs]
variant_data_file = "variants.json"

[needs.variant_data]
edition = "pro"
"""


def test_the_file_side_is_read_when_sphinx_needs_is_absent(make_app, tmp_path):
    """Cell 1 of the matrix: nothing else computes the map, so this does."""
    confdir, _ = make_project(tmp_path, toml=FILE_TOML)
    (confdir / "variants.json").write_text(
        json.dumps({"edition": "basic", "build": {"debug": True}}), encoding="utf-8"
    )
    app = _build(make_app, confdir)
    # Inline `edition = "pro"` wins over the file's "basic"; the file supplies
    # `build.debug`, which the inline table does not have. Rule holds.
    assert "hostgated.html" in _pages(app)


def test_the_file_side_survives_an_unmerged_inline_map(make_app, tmp_path):
    """Cell 2: sphinx-needs present, resolution not yet performed.

    Every release up to and including 8.3.1 resolves the variant map at
    ``env-before-read-docs``, long after ``config-inited``, so at this seam
    ``needs_variant_data`` holds the **inline half only**. Without the
    unconditional re-merge the file-side keys are simply missing, every
    reference to one is an unknown key, and every rule excludes.
    """
    confdir, _ = make_project(tmp_path, toml=FILE_TOML)
    (confdir / "variants.json").write_text(
        json.dumps({"edition": "basic", "build": {"debug": True}}), encoding="utf-8"
    )
    _stub_conf(
        confdir,
        "needs_stub_unmerged",
        inline='{"edition": "pro"}',
        file_ref='"variants.json"',
    )
    app = _build(make_app, confdir)
    assert "mounts.variant_rule_unevaluable" not in app._warning.getvalue()
    assert "hostgated.html" in _pages(app)


def test_the_merge_is_a_no_op_on_an_already_merged_map(make_app, tmp_path):
    """Cell 3: sphinx-needs present and already resolved.

    ``deep_merge(file, already_merged) == already_merged``, so the re-merge
    changes nothing and the two tools cannot disagree about which documents
    exist. The output has to be identical to cell 2's.
    """
    confdir, _ = make_project(tmp_path, toml=FILE_TOML)
    (confdir / "variants.json").write_text(
        json.dumps({"edition": "basic", "build": {"debug": True}}), encoding="utf-8"
    )
    _stub_conf(
        confdir,
        "needs_stub_merged",
        inline='{"edition": "pro", "build": {"debug": True}}',
        file_ref='"variants.json"',
    )
    app = _build(make_app, confdir)
    assert "hostgated.html" in _pages(app)


def test_a_toml_declared_data_file_anchors_at_the_toml_directory(make_app, tmp_path):
    """The first of the two anchors, with the two directories kept distinct.

    A relative ``variant_data_file`` declared in the TOML resolves against the
    **TOML's own directory**; one declared in ``conf.py`` or with ``-D``
    resolves against ``confdir``. Reading only one anchor means reading the
    wrong file for one of the two routes — and here that would mean reading no
    file at all.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs]
    variant_data_file = "variants.json"

    [source]
    dir = ".."
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    # Move the TOML into a sub-directory, with its data file beside it. A
    # confdir anchor would look for `<confdir>/variants.json`, which is absent.
    # `[source] dir = [".."]` keeps the rules anchored at the Sphinx source
    # directory, which is what the layout guard requires — and it is a separate
    # anchor from the data file's, which is the point of the test.
    configs = confdir / "configs"
    configs.mkdir()
    shutil.move(str(confdir / "ubproject.toml"), str(configs / "ubproject.toml"))
    (configs / "variants.json").write_text(
        json.dumps({"edition": "pro"}), encoding="utf-8"
    )
    conf = confdir / "conf.py"
    conf.write_text(
        conf.read_text(encoding="utf-8")
        + '\nsources_from_toml = "configs/ubproject.toml"\n',
        encoding="utf-8",
    )
    app = _build(make_app, confdir)
    assert "mounts.variant_rule_unevaluable" not in app._warning.getvalue()
    assert "hostgated.html" in _pages(app)


def test_a_mispointed_sphinx_needs_is_refused(make_app, tmp_path):
    """The corner where a project silently loses every gated file.

    sphinx-needs is loaded but was never pointed at this file, so its resolved
    map is empty — and this reader takes the map FROM sphinx-needs whenever it
    is installed, precisely so the two tools cannot disagree. Every rule then
    reports an unknown key and excludes, and the whole gated document set
    disappears.

    It used to be a per-rule *suppressible* warning, which contradicts this
    key's own rule: for a gating key, a failure behind a diagnostic a project
    can silence is not a failure — and ``suppress_warnings = ["mounts"]`` is
    recommended in these very docs.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    _stub_conf(confdir, "needs_stub_unpointed", inline="{}", file_ref="None")
    with pytest.raises(Exception) as excinfo:
        _build(make_app, confdir)
    message = str(excinfo.value)
    assert "needs_from_toml" in message, "the one-line fix is named"
    assert "variant_data_unreadable" in message


@pytest.mark.parametrize(
    ("toml_tail", "stub_file_ref"),
    [
        ("[needs.variant_data]\n", "None"),
        ('[needs]\nvariant_data_file = "v.json"\n', "None"),
    ],
    ids=["empty-inline-table", "empty-data-file"],
)
def test_a_correctly_pointed_project_with_empty_data_is_not_refused(
    make_app, tmp_path, toml_tail: str, stub_file_ref: str
):
    """The mispointing guard's reachable false positive.

    The conjunct that matters is not "the map is empty" but "the map is empty
    AND sphinx-needs is not reading this file". Without it, a project that had
    already done exactly what the message advises — ``needs_from_toml`` set to
    this very file — was hard-errored for having legitimately empty data: an
    empty ``[needs.variant_data]`` placeholder, or a base-variant
    ``variant_data_file`` of ``{}``. Both are ordinary, and the message named a
    fix the project's ``conf.py`` already contained.
    """
    toml = (
        """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    """
        + toml_tail
    )
    confdir, _ = make_project(tmp_path, toml=toml)
    (confdir / "v.json").write_text("{}", encoding="utf-8")
    _stub_conf(
        confdir,
        "needs_stub_pointed",
        inline="{}",
        file_ref=stub_file_ref,
        from_toml='"ubproject.toml"',
    )
    app = _build(make_app, confdir)
    # Empty data is not a configuration error; the rule simply cannot be
    # evaluated, which is the ordinary warn-and-exclude path.
    assert "mounts.variant_rule_unevaluable" in app._warning.getvalue()
    assert "hostgated.html" not in _pages(app)


def test_a_sphinx_needs_pointed_at_a_different_file_is_still_refused(
    make_app, tmp_path
):
    """The other half of the same conjunct, and the message says which file."""
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    (confdir / "other.toml").write_text("", encoding="utf-8")
    _stub_conf(
        confdir,
        "needs_stub_elsewhere",
        inline="{}",
        file_ref="None",
        from_toml='"other.toml"',
    )
    with pytest.raises(Exception) as excinfo:
        _build(make_app, confdir)
    message = str(excinfo.value)
    assert "other.toml" in message, "the message names where it IS reading"
    assert "variant_data_unreadable" in message


def test_a_conf_py_supplied_map_is_not_mistaken_for_a_mispointing(make_app, tmp_path):
    """The negative half: a non-empty map from anywhere is legitimate.

    A project may supply the variant map from ``conf.py`` or ``-D`` while the
    TOML also declares one. That is not a mispointing, and the conjunction is
    narrow enough to say so — the resolved map is not empty.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    _stub_conf(
        confdir, "needs_stub_confpy", inline='{"edition": "pro"}', file_ref="None"
    )
    app = _build(make_app, confdir)
    assert "hostgated.html" in _pages(app), "the conf.py map wins and the rule holds"


def test_unreadable_variant_data_is_a_hard_error_without_sphinx_needs(
    make_app, tmp_path
):
    """With no variant map there is no defensible answer to "which files".

    Hard only when sphinx-needs is absent: when it is present it raises its own
    ``NeedsConfigException`` for the same file, and reporting here as well
    would be two messages for one problem.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs]
    variant_data_file = "variants.json"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    (confdir / "variants.json").write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(Exception, match="variant_data_unreadable"):
        _build(make_app, confdir)


# ---------------------------------------------------------------------------
# The confvals
# ---------------------------------------------------------------------------


def test_the_deprecated_confval_is_honoured_and_reported(make_app, tmp_path):
    confdir, _ = make_project(tmp_path, toml=base_toml("basic"))
    shutil.move(str(confdir / "ubproject.toml"), str(confdir / "custom.toml"))
    conf = confdir / "conf.py"
    conf.write_text(
        conf.read_text(encoding="utf-8") + '\nmounts_from_toml = "custom.toml"\n',
        encoding="utf-8",
    )
    app = _build(make_app, confdir)
    assert "mounts.deprecated_confval" in app._warning.getvalue()
    assert "hostgated.html" not in _pages(app)


def test_setting_both_confvals_differently_is_a_hard_error(make_app, tmp_path):
    """Not a precedence puzzle: which file is read must be readable off conf.py."""
    confdir, _ = make_project(tmp_path, toml=base_toml("basic"))
    conf = confdir / "conf.py"
    conf.write_text(
        conf.read_text(encoding="utf-8")
        + '\nmounts_from_toml = "a.toml"\nsources_from_toml = "b.toml"\n',
        encoding="utf-8",
    )
    with pytest.raises(Exception, match="Keep exactly one"):
        _build(make_app, confdir)


def test_sources_from_toml_none_disables_the_variant_reader_too(make_app, tmp_path):
    """The coupling, named rather than discovered.

    ``sources_from_toml = None`` means "never read that file", and variant
    rules live in it, so they stop being read as well. That is a **fail-open**
    coupling — content the rules gate gets published — which is exactly why the
    documentation states it by name.
    """
    confdir, _ = make_project(tmp_path, toml=base_toml("basic"))
    conf = confdir / "conf.py"
    conf.write_text(
        conf.read_text(encoding="utf-8") + "\nsources_from_toml = None\n",
        encoding="utf-8",
    )
    app = _build(make_app, confdir)
    assert "hostgated.html" in _pages(app)


#: ``(conf.py lines, which file is read, whether the deprecation fires)``.
#:
#: The wrong-file row is the third one: the author used the CURRENT spelling and
#: named a file explicitly, and the DEPRECATED key won — because inferring
#: "explicit" from the value cannot tell "wrote the default" from "wrote
#: nothing". It is reachable during exactly the migration the pair exists for.
CONFVAL_MATRIX = [
    ("", "ubproject.toml", False),
    ('sources_from_toml = "other.toml"', "other.toml", False),
    ('mounts_from_toml = "other.toml"', "other.toml", True),
    (
        'sources_from_toml = "ubproject.toml"\nmounts_from_toml = "other.toml"',
        None,
        None,
    ),
    (
        'sources_from_toml = "other.toml"\nmounts_from_toml = "other.toml"',
        "other.toml",
        True,
    ),
    ('mounts_from_toml = "ubproject.toml"', "ubproject.toml", True),
]


@pytest.mark.parametrize(
    ("lines", "reads", "deprecates"),
    CONFVAL_MATRIX,
    ids=[
        "neither",
        "new-only",
        "old-only",
        "new-default-plus-old-elsewhere",
        "both-same",
        "old-set-to-default",
    ],
)
def test_the_confval_matrix(
    make_app, tmp_path, lines: str, reads: str | None, deprecates: bool | None
):
    """Which file is read, and whether the rename is nudged.

    Both TOML files exist and disagree, so "which file was read" is observable
    from the output rather than inferred: ``ubproject.toml`` keeps
    ``hostgated``, ``other.toml`` gates it away.
    """
    keeping = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "pro"
    """
    gating = keeping.replace('edition = "pro"', 'edition = "basic"')
    confdir, _ = make_project(tmp_path, toml=keeping)
    _write(confdir / "other.toml", gating)
    conf = confdir / "conf.py"
    conf.write_text(
        conf.read_text(encoding="utf-8") + "\n" + lines + "\n", encoding="utf-8"
    )

    if reads is None:
        with pytest.raises(Exception, match="Keep exactly one"):
            _build(make_app, confdir)
        return

    app = _build(make_app, confdir)
    gated = "hostgated.html" not in _pages(app)
    assert gated is (reads == "other.toml"), f"expected to read {reads}"
    assert ("mounts.deprecated_confval" in app._warning.getvalue()) is deprecates


def test_a_project_with_no_mounts_can_use_variant_rules(make_app, tmp_path):
    """The whole justification for homing the reader here, from a user's view.

    A project with no mounts at all can install sphinx-mounts purely to have
    ``sphinx-build`` narrow its document set per variant, exactly as ubCode
    does.
    """
    toml = """
    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    app = _build(make_app, confdir)
    assert app.config.mounts == []
    assert "hostgated.html" not in _pages(app)
    assert "hostkeep.html" in _pages(app)
