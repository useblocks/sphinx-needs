"""End-to-end coverage for ``if`` on a ``[[source.mounts]]`` entry.

Whole-bundle variant gating. ``[[source.variant_sources]]`` narrows a file set
by glob; this key removes a whole mount, which makes it the blunter of the two
and the one whose failure modes are larger:

* it must **fail closed** on every path — a condition that is false, one that
  cannot be validated, one that cannot be evaluated, and one this reader never
  got to look at all end with the bundle out of the build;
* it must be **silent in the right places**: a mount whose condition holds must
  produce no ``mounts.unknown_key``, and a mount that is gated off must produce
  no ``attach_to`` complaint, no dangling toctree entry and no ``-W`` failure;
* it must be **loud in the one place that matters**: a gated-off bundle is a
  large, silent absence, so the record fires whether or not anything in the
  project references it.

So these tests build real projects and look at what came out, rather than at
what the reader computed.
"""

from __future__ import annotations

import logging as stdlib_logging
from pathlib import Path
import pickle
import textwrap
from typing import Any

import pytest

from sphinx_mounts import warnings as mount_warnings
from sphinx_mounts.extension import _DECIDED_GATES_KEY
from sphinx_mounts.logging import MOUNT_GATED_CODE
from tests.test_variant_sources import _stub_conf


@pytest.fixture(autouse=True)
def _detach_filters():
    """Keep the process-global logger filters from leaking between tests.

    The emitting loggers are module-level objects shared by every ``Sphinx``
    application in the process, so a test that installs a filter and never
    builds again would change what the next test sees.
    """
    yield
    mount_warnings.remove_downgrade_filters()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def bundle_path(root: Path) -> str:
    """The directory bundle :func:`make_project` writes, as a ``conf.py`` literal.

    Needed by the ``conf.py`` routes, which declare their mounts before the
    project exists and so cannot be handed the path the TOML substitution
    would have given them.
    """
    return (root / "bundle").as_posix()


def make_project(
    root: Path,
    *,
    toml: str,
    conf_extra: str = "",
    srcdir_name: str | None = None,
    host_entries: tuple[str, ...] = (),
    host_glob: str | None = None,
    host_files: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    """Materialise a host project plus two external bundles.

    The host index toctrees only what ``host_entries`` names, so a mount is
    reachable through its own ``attach_to`` wiring and through nothing else.
    That is what makes "the mount contributed nothing" observable without a
    dangling reference confusing the picture — a reference INTO a gated bundle
    is its own scenario, and the tests that want one ask for it.

    ``{bundle}``, ``{rival}``, ``{loose}``, ``{alpha}`` and ``{beta}`` are
    substituted into ``toml`` with absolute paths. ``rival`` exists so that two
    mounts can contest one ``mount_at``, which is the natural shape for this
    key and the shape the attribution's ordering has to survive.

    :return: ``(confdir, bundle)``.
    """
    confdir = root / "proj"
    srcdir = confdir if srcdir_name is None else confdir / srcdir_name
    bundle = root / "bundle"
    rival = root / "rival"
    loose = root / "loose"

    _write(
        bundle / "index.rst",
        """
        Bundle
        ======

        BUNDLE_INDEX_MARKER

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
    _write(
        rival / "index.rst",
        """
        Rival
        =====

        RIVAL_INDEX_MARKER
    """,
    )
    for name in ("alpha", "beta"):
        _write(
            loose / f"{name}.rst",
            f"""
            {name.title()}
            {"=" * len(name)}

            {name.upper()}_MARKER
        """,
        )
    for name, body in (host_files or {}).items():
        _write(srcdir / name, body)

    # Assembled line by line rather than through a dedented template, for the
    # reason the conf.py below spells out: an interpolated multi-line block
    # would leave `textwrap.dedent` nothing in common to strip, and the whole
    # document would keep its template indentation.
    lines = ["Host", "====", "", "HOST_MARKER", "", ".. toctree::", ""]
    lines += [f"   {entry}" for entry in host_entries]
    lines.append("")
    if host_glob:
        lines += [".. toctree::", "   :glob:", "", f"   {host_glob}", ""]
    srcdir.mkdir(parents=True, exist_ok=True)
    (srcdir / "index.rst").write_text("\n".join(lines), encoding="utf-8")
    # Written line by line rather than through a dedented template: a
    # multi-line ``conf_extra`` interpolated into one would leave its
    # continuation lines un-indented, which makes `textwrap.dedent` a no-op and
    # the whole file a syntax error.
    confdir.mkdir(parents=True, exist_ok=True)
    (confdir / "conf.py").write_text(
        "\n".join(
            [
                'project = "host"',
                'author = "tests"',
                'extensions = ["sphinx_mounts"]',
                "exclude_patterns: list[str] = []",
                'master_doc = "index"',
                conf_extra,
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write(
        confdir / "ubproject.toml",
        toml.replace("{bundle}", bundle.as_posix())
        .replace("{rival}", rival.as_posix())
        .replace("{loose}", loose.as_posix())
        .replace("{alpha}", (loose / "alpha.rst").as_posix())
        .replace("{beta}", (loose / "beta.rst").as_posix()),
    )
    return confdir, bundle


def _build(
    make_app,
    confdir: Path,
    *,
    builddir: Path | None = None,
    freshenv: bool = True,
    attribution: dict[str, str] | None = None,
    **kwargs: Any,
):
    """Build the project, optionally snapshotting the downgrade attribution.

    The downgrade filter lives on process-global loggers and is detached at
    ``build-finished``, so a caller that looks at it after ``app.build()``
    returns always sees an empty map — correctly, since a finished build no
    longer owns those loggers. Passing ``attribution`` connects a listener at
    priority 1, ahead of the extension's own detach at the default 500, and
    fills the given dict with what the filter was holding.
    """
    app = make_app(srcdir=confdir, builddir=builddir, freshenv=freshenv, **kwargs)
    if attribution is not None:
        app.connect(
            "build-finished",
            lambda *_: attribution.update(_attribution()),
            priority=1,
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

    # Only ever used to assert that a build DOES fail. Constructing a second
    # `SphinxTestApp` in one process re-registers the `sphinx.addnodes` node
    # classes and emits an `app.add_node` warning for each, which under `-W`
    # is enough to fail any second build — so "it passed -W" has to be
    # asserted on a test's FIRST and only application, never through here.


def _attribution() -> dict[str, str]:
    """The docname -> gate/rule map the installed downgrade filter is holding.

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


DIR_MOUNT_TOML = """
[[source.mounts]]
dir = "{bundle}"
mount_at = "mnt"
attach_to = "index"
if = "var.edition == 'pro'"

[needs.variant_data]
edition = "EDITION"
"""

FILE_MOUNT_TOML = """
[[source.mounts]]
files = ["{alpha}", "{beta}"]
mount_at = "loose"
attach_to = "index"
attach_each = true
if = "var.edition == 'pro'"

[needs.variant_data]
edition = "EDITION"
"""


# ---------------------------------------------------------------------------
# The gate itself, in both mount modes
# ---------------------------------------------------------------------------


def test_a_false_condition_gates_the_whole_mount_off(make_app, tmp_path):
    """The bundle is out of the build entirely — not merely unwired."""
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "basic"))
    app = _build(make_app, confdir)
    assert "mnt/index" not in app.env.found_docs
    assert "mnt/binternal" not in app.env.found_docs
    assert not (Path(app.outdir) / "mnt" / "index.html").exists()


def test_a_true_condition_leaves_the_mount_mounted(make_app, tmp_path):
    """The control. Same file, same key, the other variant."""
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "pro"))
    app = _build(make_app, confdir)
    assert "mnt/index" in app.env.found_docs
    assert "mnt/binternal" in app.env.found_docs


def test_a_gated_on_mount_reports_no_unknown_key(make_app, tmp_path):
    """The key must be STRIPPED from a surviving table, not merely read.

    ``if`` is a Python keyword, so ``MountConfig`` can never model it as a
    field and ``from_dict`` would report ``mounts.unknown_key`` for it. That is
    a *warning*, so the trap is not cosmetic: it fails ``sphinx-build -W`` on a
    project whose only sin is using the key exactly as documented.
    """
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "pro"))
    app = _build(make_app, confdir)
    warning = app._warning.getvalue()
    assert "mounts.unknown_key" not in warning
    assert warning.strip() == ""


@pytest.mark.parametrize("edition", ["pro", "basic"])
def test_neither_arm_fails_under_dash_w(make_app, tmp_path, edition):
    """Both verdicts have to be clean under ``-W``, for opposite reasons.

    Gated ON, the risk is the unstripped key. Gated OFF, the risk is every
    diagnostic about a mount that is not in the build: the ``attach_to`` host
    that was never extended, the bundle root that no longer matters.
    """
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", edition))
    assert not _fails_under_dash_w(make_app, confdir, tmp_path / "build")


@pytest.mark.parametrize("edition", ["pro", "basic"])
def test_a_file_list_mount_is_gated_uniformly(make_app, tmp_path, edition):
    """A whole-mount ``if`` gates a ``files`` mount exactly as it gates a ``dir``.

    This is a different question from the one ``[[source.variant_sources]]``
    answers, and it has the opposite answer. A rule cannot narrow a file-list
    mount in either reader — a ``files`` mount's entries bypass pattern
    matching entirely — but dropping a whole bundle touches neither ``include``
    nor ``exclude``, so it is mode-blind by construction here and in ubCode.
    Reading "file-list mounts are now gateable" as "rules reach them now" is
    the confusion this test exists to keep separate.
    """
    confdir, _ = make_project(
        tmp_path, toml=FILE_MOUNT_TOML.replace("EDITION", edition)
    )
    app = _build(make_app, confdir)
    present = {"loose/alpha", "loose/beta"} <= app.env.found_docs
    assert present is (edition == "pro")


def test_a_gated_off_mount_wires_nothing_into_the_host_toctree(make_app, tmp_path):
    """``attach_to`` is a no-op for a bundle that produced no documents.

    Silent because the mount produced nothing, not because anything
    special-cases it: ``_wired_entries`` already gates on what ``discover()``
    returned, and a gated mount returns an empty list.
    """
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "basic"))
    app = _build(make_app, confdir)
    assert app.env.toctree_includes.get("index", []) == []
    assert app._warning.getvalue().strip() == ""


def test_a_gated_off_mount_does_not_report_a_missing_attach_to(make_app, tmp_path):
    """A typo in ``attach_to`` is not this variant's problem.

    The mount wires nothing here, so ``mounts.attach_to_missing`` would be a
    warning about work that was never attempted — and ``-W`` would fail a
    correctly gated build over it. The same typo is still reported in every
    variant where the mount is live, which the second half asserts.
    """
    toml = DIR_MOUNT_TOML.replace('attach_to = "index"', 'attach_to = "nosuchdoc"')
    confdir, _ = make_project(tmp_path, toml=toml.replace("EDITION", "basic"))
    app = _build(make_app, confdir)
    assert "attach_to_missing" not in app._warning.getvalue()

    confdir_live, _ = make_project(
        tmp_path / "live", toml=toml.replace("EDITION", "pro")
    )
    app_live = _build(make_app, confdir_live)
    assert "attach_to_missing" in app_live._warning.getvalue()


# ---------------------------------------------------------------------------
# The record: a gated bundle is a large, silent absence without it
# ---------------------------------------------------------------------------


def test_a_gated_off_mount_is_recorded_even_when_nothing_references_it(
    make_app, tmp_path
):
    """The whole mitigation for this key's nastiest failure shape.

    Nothing in the host project mentions the bundle, so no toctree warning,
    no downgrade and no missing-page symptom can point at it. Without this
    record, "where did my 400 pages go" is answerable only by re-reading
    ``ubproject.toml``.
    """
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "basic"))
    app = _build(make_app, confdir)
    status = app._status.getvalue()
    assert MOUNT_GATED_CODE in status
    assert "var.edition == 'pro'" in status
    assert "[[source.mounts]][0]" in status


def test_the_record_is_info_rather_than_a_warning(make_app, tmp_path):
    """Gating is what the author asked for, so it must not fail ``-W``."""
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "basic"))
    app = _build(make_app, confdir)
    assert MOUNT_GATED_CODE not in app._warning.getvalue()


def test_a_live_mount_is_not_recorded_as_gated(make_app, tmp_path):
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "pro"))
    app = _build(make_app, confdir)
    assert MOUNT_GATED_CODE not in app._status.getvalue()


# ---------------------------------------------------------------------------
# A project that gates mounts and declares no rules
# ---------------------------------------------------------------------------


def test_a_mounts_only_project_reaches_the_fold(make_app, tmp_path):
    """No ``[[source.variant_sources]]`` anywhere, and the gate still fires.

    The reader used to short-circuit on five separate rules-only premises
    before it reached any fold. Every one of them is a project that gates
    mounts and declares no rules, which is the ordinary shape for a host
    project that consumes bundles it does not own.
    """
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "basic"))
    assert "variant_sources" not in (confdir / "ubproject.toml").read_text()
    app = _build(make_app, confdir)
    assert "mnt/index" not in app.env.found_docs


def test_a_mounts_only_project_is_not_refused_by_the_layout_guard(make_app, tmp_path):
    """A mount ``if`` anchors no glob, so no layout can be wrong for it.

    The layout guard exists because a rule GLOB has to be re-expressible as an
    ``exclude_patterns`` entry anchored at ``srcdir``. Applying it to a project
    that only gates mounts refuses a configuration with nothing wrong with
    it — and the layout it would refuse (``ubproject.toml`` beside ``conf.py``,
    sources one directory down) is entirely ordinary.
    """
    toml = DIR_MOUNT_TOML.replace("EDITION", "basic")
    confdir, _ = make_project(tmp_path, toml=f"[source]\ndir = 'source'\n{toml}")
    # `[source] dir` names a directory that is not Sphinx's srcdir, which is
    # exactly the shape the guard refuses when rules are declared.
    app = _build(make_app, confdir)
    assert "mnt/index" not in app.env.found_docs
    assert app._warning.getvalue().strip() == ""


def test_the_layout_guard_still_fires_for_a_rule_declaring_project(make_app, tmp_path):
    """The other direction, so the scoping is a scoping and not a removal."""
    toml = """
    [source]
    dir = "nowhere"

    [[source.mounts]]
    dir = "{bundle}"
    mount_at = "mnt"
    if = "var.edition == 'pro'"

    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["gated/**"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    with pytest.raises(Exception, match="mounts.variant_layout"):
        _build(make_app, confdir)


# ---------------------------------------------------------------------------
# Failure postures: fail closed on every path
# ---------------------------------------------------------------------------


def test_an_ungrammatical_mount_condition_refuses_the_configuration(make_app, tmp_path):
    """One grammar, one validator — so one posture, the rule key's.

    A bare field is refused for a rule; it has to be refused for a mount too,
    or ``if`` would mean two different things in one file.
    """
    toml = DIR_MOUNT_TOML.replace("\"var.edition == 'pro'\"", '"var.debug"')
    confdir, _ = make_project(tmp_path, toml=toml.replace("EDITION", "basic"))
    with pytest.raises(Exception, match="outside the condition grammar"):
        _build(make_app, confdir)


def test_one_hard_error_lists_offenders_from_both_keys(make_app, tmp_path):
    """Fixing one refused condition only to meet the next is what this avoids.

    Two error paths for one grammar could also disagree about what the grammar
    is, which is why the two keys go through the validator in a single call.
    """
    toml = """
    [[source.mounts]]
    dir = "{bundle}"
    mount_at = "mnt"
    if = "var.debug"

    [[source.variant_sources]]
    if = "edition == 'pro'"
    files = ["gated/**"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(tmp_path, toml=toml)
    with pytest.raises(Exception) as excinfo:
        _build(make_app, confdir)
    message = str(excinfo.value)
    assert "2 variant condition(s)" in message
    assert "[[source.mounts]][0]" in message
    assert "[[source.variant_sources]][0]" in message


def test_a_non_string_condition_is_refused(make_app, tmp_path):
    """A rule's loader already rejects one; a mount table can still carry it."""
    toml = DIR_MOUNT_TOML.replace("if = \"var.edition == 'pro'\"", "if = 3")
    confdir, _ = make_project(tmp_path, toml=toml.replace("EDITION", "basic"))
    with pytest.raises(Exception, match="condition must be a string"):
        _build(make_app, confdir)


def test_an_unevaluable_mount_condition_gates_off_and_warns(make_app, tmp_path):
    """Data-dependent, so warn-and-gate rather than refuse.

    The same posture the ``.. if::`` directive already has, and the safe
    direction for a key whose purpose is keeping content out of the build.
    """
    toml = DIR_MOUNT_TOML.replace(
        "if = \"var.edition == 'pro'\"", "if = \"var.nosuchkey == 'pro'\""
    )
    confdir, _ = make_project(tmp_path, toml=toml.replace("EDITION", "basic"))
    app = _build(make_app, confdir)
    assert "mnt/index" not in app.env.found_docs
    assert "mounts.variant_rule_unevaluable" in app._warning.getvalue()


def test_a_condition_this_reader_never_evaluates_still_gates_off(make_app, tmp_path):
    """``sources_from_toml = None`` switches off everything read from TOML.

    The mounts then come from ``conf.py``, so a condition on one of them
    reaches no evaluator at all. Publishing the bundle would be the one outcome
    a gating key must not have, so it is gated off — and reported, because a
    silent disappearance is exactly what the record exists to prevent.
    """
    confdir, bundle = make_project(
        tmp_path,
        toml="",
        conf_extra=(
            "sources_from_toml = None\n"
            f'mounts = [{{"dir": "{bundle_path(tmp_path)}", "mount_at": "mnt", '
            '"if": "var.edition == \'pro\'"}]'
        ),
    )
    app = _build(make_app, confdir)
    assert "mnt/index" not in app.env.found_docs
    assert "mount_gate_unevaluable" in app._warning.getvalue()


# ---------------------------------------------------------------------------
# The conf.py routes
# ---------------------------------------------------------------------------


def test_a_conf_py_mapping_carries_a_condition(make_app, tmp_path):
    """The limitation is the dataclass's, not the route's.

    A ``conf.py``-declared mount written as a plain mapping is read by the same
    reader as a TOML table, so its ``if`` is evaluated. Only a ``MountConfig``
    *instance* cannot carry one — ``if`` is a Python keyword, so no dataclass
    field can be named for it.
    """
    confdir, _ = make_project(
        tmp_path,
        toml="[needs.variant_data]\nedition = 'basic'\n",
        conf_extra=(
            f'mounts = [{{"dir": "{bundle_path(tmp_path)}", "mount_at": "mnt", '
            '"if": "var.edition == \'pro\'"}]'
        ),
    )
    app = _build(make_app, confdir)
    assert "mnt/index" not in app.env.found_docs


def test_a_conf_py_mountconfig_instance_is_unaffected(make_app, tmp_path):
    """The documented limitation, pinned from the other side.

    An instance cannot carry a condition, so it is never gated — and the TOML
    route in the same project keeps working, which is what makes the
    limitation survivable rather than a hole.
    """
    confdir, _ = make_project(
        tmp_path,
        toml="[needs.variant_data]\nedition = 'basic'\n",
        conf_extra=(
            "from pathlib import Path\n"
            "from sphinx_mounts.config import MountConfig\n"
            f'mounts = [MountConfig(dir=Path("{bundle_path(tmp_path)}"), '
            'mount_at="mnt")]'
        ),
    )
    app = _build(make_app, confdir)
    assert "mnt/index" in app.env.found_docs


# ---------------------------------------------------------------------------
# Convergence: a gating flip is a config change Sphinx already knows
# ---------------------------------------------------------------------------


def test_a_gating_flip_converges_in_both_directions(make_app, tmp_path):
    """Three builds in one output directory, on and off and on again.

    The gate lives in the ``mounts`` config VALUE — the key survives on a
    gated-off table and is stripped from a live one — and that confval is
    ``rebuild="env"``, so Sphinx re-reads every document on the build where
    the flip happened. A reader that gated without touching a config value
    would leave both values byte-identical across the flip and would need an
    invalidation story of its own.
    """
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "pro"))
    builddir = tmp_path / "build"
    toml_path = confdir / "ubproject.toml"

    app = _build(make_app, confdir, builddir=builddir)
    assert "mnt/index" in app.env.found_docs
    assert app.env.toctree_includes["index"] == ["mnt/index"]

    toml_path.write_text(
        toml_path.read_text().replace('edition = "pro"', 'edition = "basic"'),
        encoding="utf-8",
    )
    app = _build(make_app, confdir, builddir=builddir, freshenv=False)
    assert "mnt/index" not in app.env.found_docs
    assert app.env.toctree_includes.get("index", []) == []
    # Named, not merely observed: the flip has to travel as a change to the
    # `mounts` config VALUE. Anything else would leave both builds' values
    # byte-identical and need an invalidation story this reader does not have.
    assert "config changed ('mounts')" in app._status.getvalue()

    toml_path.write_text(
        toml_path.read_text().replace('edition = "basic"', 'edition = "pro"'),
        encoding="utf-8",
    )
    app = _build(make_app, confdir, builddir=builddir, freshenv=False)
    assert "mnt/index" in app.env.found_docs
    assert app.env.toctree_includes["index"] == ["mnt/index"]
    assert "config changed ('mounts')" in app._status.getvalue()


# ---------------------------------------------------------------------------
# Attribution: which references into a gated bundle are downgraded, and why
# the docnames come from the real pipeline rather than a second walk
# ---------------------------------------------------------------------------


def test_a_toctree_entry_into_a_gated_bundle_is_downgraded(make_app, tmp_path):
    """A host index that lists every variant's pages is the normal 150% shape.

    Sphinx is right that the document is missing; what is wrong is calling it a
    problem. The record is reworded to name the gate, downgraded to INFO, and
    ``-W`` passes.
    """
    confdir, _ = make_project(
        tmp_path,
        toml=DIR_MOUNT_TOML.replace("EDITION", "basic"),
        host_entries=("mnt/index",),
    )
    app = _build(make_app, confdir, warningiserror=True)
    status = app._status.getvalue()
    assert mount_warnings.VARIANT_EXCLUDED_CODE in status
    assert "[[source.mounts]][0] (if = \"var.edition == 'pro'\")" in status
    assert "WARNING" not in app._warning.getvalue()
    assert app.statuscode == 0


def test_the_attribution_covers_every_page_of_the_gated_bundle(make_app, tmp_path):
    """Not just the entry doc: the whole bundle left, so all of it is attributed."""
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "basic"))
    attributed: dict[str, str] = {}
    _build(make_app, confdir, attribution=attributed)
    assert set(attributed) == {"mnt/index", "mnt/binternal"}


def test_a_genuine_typo_still_warns_beside_a_gated_mount(make_app, tmp_path):
    """The negative control, and the reason the downgrade must be exact.

    A reference no gate and no rule explains still warns and still fails
    ``-W``, so a typo cannot hide behind a variant.
    """
    confdir, _ = make_project(
        tmp_path,
        toml=DIR_MOUNT_TOML.replace("EDITION", "basic"),
        host_entries=("mnt/index", "nosuchdoc"),
    )
    app = _build(make_app, confdir)
    warning = app._warning.getvalue()
    assert "nosuchdoc" in warning
    assert "mnt/index" not in warning
    assert _fails_under_dash_w(make_app, confdir, tmp_path / "build")


def test_a_glob_entry_matching_only_gated_pages_is_downgraded(make_app, tmp_path):
    """The ``:glob:`` arm reaches a gated bundle the same way it reaches a rule."""
    confdir, _ = make_project(
        tmp_path,
        toml=DIR_MOUNT_TOML.replace("EDITION", "basic"),
        host_glob="mnt/*",
    )
    app = _build(make_app, confdir, warningiserror=True)
    assert mount_warnings.VARIANT_EXCLUDED_CODE in app._status.getvalue()
    assert "WARNING" not in app._warning.getvalue()
    assert app.statuscode == 0


def test_a_file_list_mount_gate_attributes_its_docnames(make_app, tmp_path):
    """File-list mode has no walk to reproduce, and still goes through it."""
    confdir, _ = make_project(
        tmp_path,
        toml=FILE_MOUNT_TOML.replace("EDITION", "basic"),
        host_entries=("loose/alpha",),
    )
    attributed: dict[str, str] = {}
    app = _build(make_app, confdir, attribution=attributed, warningiserror=True)
    assert set(attributed) == {"loose/alpha", "loose/beta"}
    assert mount_warnings.VARIANT_EXCLUDED_CODE in app._status.getvalue()
    assert "WARNING" not in app._warning.getvalue()
    assert app.statuscode == 0


# ---------------------------------------------------------------------------
# The phantom hazard: an attributed docname that IS still walkable would
# silently disable a genuine `-W` failure
# ---------------------------------------------------------------------------


TWO_MOUNTS_TOML = """
[[source.mounts]]
dir = "{bundle}"
mount_at = "mnt"
if = "var.edition == 'pro'"

[[source.mounts]]
dir = "{rival}"
mount_at = "mnt"
if = "var.edition == 'basic'"

[needs.variant_data]
edition = "basic"
"""


def test_a_docname_a_live_mount_still_supplies_is_not_attributed(make_app, tmp_path):
    """Two mounts, one ``mount_at``, mutually exclusive conditions.

    This is the shape the key is *for* — the pro bundle and the basic bundle
    both live at ``guides`` and exactly one of them is built. ``mnt/index``
    exists in this variant, supplied by the mount that is live, so a reference
    to it is an ordinary resolved reference and must not be downgraded.

    Attributing it would be a phantom, and a phantom is not merely a wrong
    message: the filter downgrades every toctree record naming an attributed
    docname, so a **genuine** warning about that name would be silenced and
    ``-W`` would stop failing. The gated pass runs after every live mount has
    registered precisely so that this cannot happen.
    """
    confdir, _ = make_project(
        tmp_path, toml=TWO_MOUNTS_TOML, host_entries=("mnt/index",)
    )
    attributed: dict[str, str] = {}
    app = _build(make_app, confdir, attribution=attributed, warningiserror=True)
    assert "mnt/index" in app.env.found_docs
    assert "mnt/index" not in attributed
    assert "WARNING" not in app._warning.getvalue()
    assert app.statuscode == 0
    # And the gated mount attributes NOTHING, not merely "not `mnt/index`".
    # The contested docname triggers the same whole-mount skip the live path
    # applies, so the reduction reaches its sibling `mnt/binternal` too. That
    # is deliberate: whether the gated mount would have supplied that page in
    # the variant where it is live depends on which mounts are live THERE,
    # which this build cannot know. Under-attributing costs a genuine warning
    # on a reference nobody writes; over-attributing costs a phantom, and a
    # phantom silences a real one.
    assert attributed == {}


def test_a_docname_the_host_supplies_is_not_attributed(make_app, tmp_path):
    """Host precedence is one of the reductions ``discover`` applies.

    The host's own ``mnt/index.rst`` wins over any mount, so the docname is
    alive in both variants and a reference to it is never variant-excluded.
    """
    confdir, _ = make_project(
        tmp_path,
        toml=DIR_MOUNT_TOML.replace("EDITION", "basic"),
        host_entries=("mnt/index",),
        host_files={
            "mnt/index.rst": "Host mnt\n========\n\nHOST_MNT_MARKER\n",
        },
    )
    attributed: dict[str, str] = {}
    app = _build(make_app, confdir, attribution=attributed, warningiserror=True)
    assert "mnt/index" in app.env.found_docs
    assert "mnt/index" not in attributed
    assert "WARNING" not in app._warning.getvalue()
    assert app.statuscode == 0


def test_a_gated_mount_with_an_absent_root_attributes_nothing_and_says_nothing(
    make_app, tmp_path
):
    """An absent bundle root is not a problem for a mount that is gated off.

    ``mounts.missing_path`` is a warning, so reporting it would fail ``-W`` on
    a project that gated a bundle its CI has not checked out — which is one of
    the reasons to gate a bundle in the first place. The whole-mount skip still
    happens, so nothing is attributed either.
    """
    toml = DIR_MOUNT_TOML.replace('dir = "{bundle}"', 'dir = "{bundle}-gone"')
    confdir, _ = make_project(tmp_path, toml=toml.replace("EDITION", "basic"))
    attributed: dict[str, str] = {}
    app = _build(make_app, confdir, attribution=attributed)
    assert "missing_path" not in app._warning.getvalue()
    assert attributed == {}


def test_gated_docnames_never_reach_the_wiring_dictionary(make_app, tmp_path):
    """The separate dictionary is load-bearing, not tidiness.

    ``_wired_entries`` reads ``_mount_entry_docnames`` as "what this mount
    produced" and wires ``attach_to`` from it. Publishing a gated mount's
    docnames there would wire a toctree entry no document backs — an
    un-suppressible ``toc.not_readable``, i.e. the mount modifying the host
    project while not being in the build at all.
    """
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "basic"))
    app = _build(make_app, confdir)
    project = app.env.project
    assert project._mount_entry_docnames == {0: []}
    assert project._gated_entry_docnames == {0: ["mnt/binternal", "mnt/index"]}


def test_the_gated_docnames_stay_out_of_the_pickled_environment(make_app, tmp_path):
    """``__getstate__`` clears the new fields like the three beside them.

    Nothing reads them back — ``discover()`` rebuilds them every build — so
    pickling them would be cache weight plus a version coupling, and the mount
    state this extension deliberately keeps out of every user's ``.doctrees``
    would be back.

    All **five** owned fields are asserted, and through a real
    ``environment.pickle`` as well as through the method, because the docstring
    makes its promise about the file rather than about the call. The project
    contests a docname so that the skip dictionary is genuinely non-empty —
    otherwise deleting its clear would be an equivalent mutant rather than a
    fenced one.
    """
    confdir, _ = make_project(
        tmp_path, toml=TWO_MOUNTS_TOML, host_entries=("mnt/index",)
    )
    app = _build(make_app, confdir)
    project = app.env.project
    assert project._gated_skips, "the mutant has to be reachable to be fenced"
    state = project.__getstate__()
    for field in (
        "_mounts",
        "_doc_roots",
        "_mount_entry_docnames",
        "_gated_entry_docnames",
        "_gated_skips",
    ):
        assert not state[field], field
    env = pickle.loads(  # noqa: S301
        (Path(app.doctreedir) / "environment.pickle").read_bytes()
    )
    assert getattr(env.project, "_gated_skips", {}) == {}
    assert getattr(env.project, "_gated_entry_docnames", {}) == {}
    assert getattr(env.project, "_mounts", ()) == ()


@pytest.mark.parametrize("edition", ["pro", "basic"])
@pytest.mark.parametrize("jobs", [1, 2])
def test_dash_w_passes_in_both_variants_serially_and_in_parallel(
    make_app, tmp_path, edition, jobs
):
    """The four-cell matrix a variant CI actually runs.

    The downgrade is installed on process-global loggers at
    ``env-before-read-docs``; ``sphinx-build -j`` reads documents in worker
    processes and sends their records back, which is a different path through
    the same filter. Both verdicts have to be clean in both.
    """
    confdir, _ = make_project(
        tmp_path,
        toml=DIR_MOUNT_TOML.replace("EDITION", edition),
        host_entries=("mnt/index",),
    )
    assert not _fails_under_dash_w_parallel(make_app, confdir, tmp_path / "build", jobs)


def _fails_under_dash_w_parallel(make_app, confdir: Path, builddir: Path, jobs: int):
    try:
        app = _build(
            make_app,
            confdir,
            warningiserror=True,
            builddir=builddir,
            parallel=jobs,
        )
    except Exception:
        return True
    return app.statuscode != 0


def test_the_attribution_is_recomputed_for_a_second_build_of_one_application(
    make_app, tmp_path
):
    """Per BUILD, not per construction.

    ``Sphinx.build()`` may be called more than once on one application, and the
    filter comes off at ``build-finished``. A second build that ran unfiltered
    would emit the variant-excluded record un-downgraded and fail ``-W`` on a
    correctly gated project.
    """
    confdir, _ = make_project(
        tmp_path,
        toml=DIR_MOUNT_TOML.replace("EDITION", "basic"),
        host_entries=("mnt/index",),
    )
    first: dict[str, str] = {}
    second: dict[str, str] = {}
    app = _build(make_app, confdir, attribution=first)
    assert set(first) == {"mnt/index", "mnt/binternal"}
    app.connect("build-finished", lambda *_: second.update(_attribution()), priority=1)
    app.build()
    assert set(second) == {"mnt/index", "mnt/binternal"}


def _inject_into_the_filter(app, docname: str, label: str) -> None:
    """Add ``docname`` to whatever downgrade filter this build installed.

    Connected at ``env-before-read-docs`` with a priority above the
    extension's own, so it runs after the filter exists and before any
    document — and therefore any toctree warning — is read.
    """

    def _hook(*_args):
        for name in mount_warnings.FALLBACK_LOGGER_NAMES:
            for installed in stdlib_logging.getLogger(name).filters:
                if isinstance(installed, mount_warnings.DowngradeFilter):
                    installed._excluded[docname] = label
                    installed._docnames = sorted(installed._excluded)

    app.connect("env-before-read-docs", _hook, priority=900)


def test_a_phantom_in_the_attributed_set_silences_a_genuine_warning(make_app, tmp_path):
    """The hazard, constructed — so the invariant below reads as load-bearing.

    This does not test product behaviour. It INJECTS a docname the project
    never had into the installed filter and shows what follows: a reference to
    ``nosuchdoc`` is a genuine, un-attributable typo, and with the phantom in
    place it is reworded as "this variant excludes it", downgraded to INFO, and
    ``sphinx-build -W`` passes.

    That is the whole reason a gated mount's docnames come from the real
    per-mount pipeline rather than a cheaper second walk. There is no diff to
    cancel a mistake here: any reduction the attribution failed to reproduce
    would put a name like this one into the set, and nothing downstream would
    ever say so.
    """
    confdir, _ = make_project(
        tmp_path,
        toml=DIR_MOUNT_TOML.replace("EDITION", "basic"),
        host_entries=("nosuchdoc",),
    )
    app = make_app(srcdir=confdir, freshenv=True, warningiserror=True)
    _inject_into_the_filter(app, "nosuchdoc", "[[source.mounts]][0] (if = 'x')")
    app.build()
    assert mount_warnings.VARIANT_EXCLUDED_CODE in app._status.getvalue()
    assert "nosuchdoc" not in app._warning.getvalue()
    assert app.statuscode == 0


BOTH_KEYS_TOML = """
[[source.mounts]]
dir = "{bundle}"
mount_at = "mnt"
if = "var.edition == 'pro'"

[[source.mounts]]
dir = "{rival}"
mount_at = "mnt"
if = "var.edition == 'basic'"

[[source.mounts]]
files = ["{alpha}", "{beta}"]
mount_at = "loose"
if = "var.edition == 'pro'"

[[source.variant_sources]]
if = "var.edition == 'pro'"
files = ["hostgated.rst"]

[needs.variant_data]
edition = "basic"
"""


def test_nothing_in_the_attributed_set_is_in_the_build(make_app, tmp_path):
    """The invariant every phantom violates, asserted directly.

    Over a project that exercises all four attribution paths at once: a host
    file removed by a rule, a directory mount gated off, a file-list mount
    gated off, and a live mount contesting the gated one's ``mount_at``.

    A name in this set is a name the downgrade filter will silence a warning
    about, so a name that is also in ``found_docs`` is a live document whose
    every future warning is pre-silenced. Nothing today emits such a warning,
    which is exactly why it has to be fenced here rather than left to a build
    outcome: the defect would be latent, not visible.
    """
    confdir, _ = make_project(
        tmp_path,
        toml=BOTH_KEYS_TOML,
        host_entries=("hostkeep",),
        host_files={
            "hostgated.rst": "Host gated\n==========\n\nHOSTGATED_MARKER\n",
            "hostkeep.rst": "Host keep\n=========\n\nHOSTKEEP_MARKER\n",
        },
    )
    attributed: dict[str, str] = {}
    app = _build(make_app, confdir, attribution=attributed)
    assert attributed, "the project really does exclude something"
    assert set(attributed) & app.env.found_docs == set()


def test_the_two_keys_attribute_side_by_side(make_app, tmp_path):
    """A rule label and a gate label in one build, each naming its own key.

    Before this key existed the message hard-coded one table name. Two
    exclusions from two keys in one project is where a single hard-coded
    subject would name the table the user did not write.
    """
    confdir, _ = make_project(
        tmp_path,
        toml=BOTH_KEYS_TOML,
        host_entries=("hostkeep",),
        host_files={
            "hostgated.rst": "Host gated\n==========\n\nHOSTGATED_MARKER\n",
            "hostkeep.rst": "Host keep\n=========\n\nHOSTKEEP_MARKER\n",
        },
    )
    attributed: dict[str, str] = {}
    _build(make_app, confdir, attribution=attributed)
    assert attributed["hostgated"].startswith("[[source.variant_sources]][0]")
    assert attributed["loose/alpha"].startswith("[[source.mounts]][2]")


# ---------------------------------------------------------------------------
# Fix round 1: every route that gates is a route that reports
# ---------------------------------------------------------------------------


LATE_HANDLER_CONF = """
def setup(app):
    def _install_late(app, config):
        config["mounts"] = [
            {{"dir": "{bundle}", "mount_at": "mnt", "if": "var.edition == 'basic'"}}
        ]

    # 460 is inside the (450, 500) window: after the variant reader has run and
    # before the parser turns the tables into MountConfigs.
    app.connect("config-inited", _install_late, priority=460)
"""


def test_a_mount_installed_after_the_reader_is_gated_and_reported(make_app, tmp_path):
    """The (450, 500) window: a gate nothing decided must not be a silent one.

    A sibling extension or a monorepo ``conf.py`` that computes mounts at
    ``config-inited`` is not exotic, and anything landing between the variant
    reader at 450 and the parser at 500 produces a mount whose ``if`` the
    reader never saw. The parser's fail-closed reading still gates it — note
    the condition here is **true**, and the bundle goes anyway — so the only
    question is whether the user is told.

    Without the report this is exactly the "where did my 400 pages go" hazard
    the ``mounts.mount_gated`` record exists to prevent, reachable through the
    one door the reporter does not stand in front of.
    """
    confdir, _ = make_project(
        tmp_path,
        toml="[needs.variant_data]\nedition = 'basic'\n",
        conf_extra=LATE_HANDLER_CONF.format(bundle=bundle_path(tmp_path)),
    )
    app = _build(make_app, confdir)
    warning = app._warning.getvalue()
    assert "mnt/index" not in app.env.found_docs, "fail closed"
    assert "mount_gate_unevaluable" in warning, warning
    assert "between 450 and 500" in warning, warning


def test_a_mountconfig_instance_carrying_a_gate_is_reported(make_app, tmp_path):
    """``gated_by`` is an internal field, and a ``conf.py`` author can still set it.

    ``_INTERNAL_MOUNT_FIELDS`` keeps it out of TOML, but the dataclass
    constructor is public enough to read, and ``_mount_conditions`` skips
    instances — so the condition is never evaluated and the bundle vanishes.
    Fail-closed, and (before this) completely silent: no record, no warning.

    The condition here is **true** for the variant, so a silent gate is
    unambiguously a surprise rather than a variant.
    """
    confdir, _ = make_project(
        tmp_path,
        toml="[needs.variant_data]\nedition = 'pro'\n",
        conf_extra=(
            "from pathlib import Path\n"
            "from sphinx_mounts.config import MountConfig\n"
            f'mounts = [MountConfig(dir=Path("{bundle_path(tmp_path)}"), '
            'mount_at="mnt", gated_by="var.edition == \'pro\'")]'
        ),
    )
    app = _build(make_app, confdir)
    warning = app._warning.getvalue()
    assert "mnt/index" not in app.env.found_docs, "fail closed"
    assert "mount_gate_unevaluable" in warning, warning
    assert "`gated_by` set directly" in warning, warning


def test_a_reader_decided_gate_is_not_reported_as_unevaluable(make_app, tmp_path):
    """The other direction: the ordinary route must stay quiet.

    The parse seam reports a gate the reader did not decide, so it has to be
    able to tell the two apart. A false positive here would fail ``-W`` on
    every correctly gated build there is.
    """
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "basic"))
    app = _build(make_app, confdir)
    assert "mount_gate_unevaluable" not in app._warning.getvalue()


# ---------------------------------------------------------------------------
# Fix round 1: the three stand-down paths, each with its own reason AND remedy
# ---------------------------------------------------------------------------


def test_the_missing_toml_stand_down_gates_off_with_its_own_remedy(make_app, tmp_path):
    """Path 2 of three: the file this extension reads is not there.

    The mount came from ``conf.py`` — a TOML-declared mount cannot be in
    ``config.mounts`` without the file the loader at 400 read it from — so
    "declare the mount in the TOML file this extension reads" would be an
    instruction to write into a file that does not exist. The remedy has to be
    to create it, or to stop declaring a condition this reader cannot evaluate.
    """
    confdir, _ = make_project(
        tmp_path,
        toml="",
        conf_extra=(
            'sources_from_toml = "nowhere.toml"\n'
            f'mounts = [{{"dir": "{bundle_path(tmp_path)}", "mount_at": "mnt", '
            '"if": "var.edition == \'pro\'"}]'
        ),
    )
    (confdir / "ubproject.toml").unlink()
    app = _build(make_app, confdir)
    warning = app._warning.getvalue()
    assert "mnt/index" not in app.env.found_docs, "fail closed"
    assert "mount_gate_unevaluable" in warning, warning
    assert "nowhere.toml" in warning, warning
    assert "does not exist" in warning, warning
    assert "Create that file" in warning, warning


def test_the_unreadable_data_stand_down_gates_off_with_its_own_remedy(
    make_app, tmp_path
):
    """Path 3 of three, and the one that could be made to fail OPEN unnoticed.

    ``_on_load_variants`` hands the gates to the fold on this path precisely so
    that a bundle whose condition could not be evaluated keeps its marker.
    Passing ``()`` instead — the exact shape of a careless refactor — publishes
    every gated bundle, and before this test nothing anywhere went red.

    The remedy differs from the other two paths again: the mount IS declared in
    the file this extension reads, so nothing about the mount has to change.
    """
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "basic"))
    _stub_conf(
        confdir, "needs_stub_gate_unreadable", inline="{}", file_ref='"nope.json"'
    )
    app = _build(make_app, confdir)
    warning = app._warning.getvalue()
    assert "mnt/index" not in app.env.found_docs, "fail closed"
    assert "mount_gate_unevaluable" in warning, warning
    assert "the variant data could not be read" in warning, warning
    assert "nothing about the mount has to change" in warning, warning


def test_the_unreadable_data_stand_down_still_strips_a_live_mount(make_app, tmp_path):
    """The other half of path 3: a mount with no ``if`` must stay unblemished.

    The fold runs on this path for the strip as much as for the gate, so a
    sibling mount that declares no condition must neither disappear nor collect
    a ``mounts.unknown_key``.
    """
    toml = (
        DIR_MOUNT_TOML.replace("EDITION", "basic")
        + '\n[[source.mounts]]\ndir = "{rival}"\nmount_at = "riv"\n'
    )
    confdir, _ = make_project(tmp_path, toml=toml)
    _stub_conf(
        confdir, "needs_stub_gate_unreadable2", inline="{}", file_ref='"nope.json"'
    )
    app = _build(make_app, confdir)
    assert "mounts.unknown_key" not in app._warning.getvalue()
    assert "riv/index" in app.env.found_docs
    assert "mnt/index" not in app.env.found_docs


def test_the_switched_off_toml_stand_down_names_its_own_remedy(make_app, tmp_path):
    """Path 1 of three: ``sources_from_toml = None``.

    TOML reading is switched off *entirely*, so telling the author to declare
    the mount in the TOML file this extension reads is an instruction that
    changes nothing. Decision 7 claimed three paths and three remedies; before
    this assertion only the reason was ever a parameter.
    """
    confdir, _ = make_project(
        tmp_path,
        toml="",
        conf_extra=(
            "sources_from_toml = None\n"
            f'mounts = [{{"dir": "{bundle_path(tmp_path)}", "mount_at": "mnt", '
            '"if": "var.edition == \'pro\'"}]'
        ),
    )
    app = _build(make_app, confdir)
    warning = app._warning.getvalue()
    assert "mnt/index" not in app.env.found_docs, "fail closed"
    assert "`sources_from_toml` is set to None" in warning, warning
    assert "Stop setting `sources_from_toml` to None" in warning, warning


def test_the_gate_report_prints_its_code_once(make_app, tmp_path):
    """One code per record, like every other ``log_warning`` in the module.

    ``log_warning`` already appends the subtype on Sphinx < 8 and lets Sphinx
    print the type on >= 8; a literal in the message body doubles it. The five
    places that do carry a literal are all *raised*, where Sphinx adds nothing.
    """
    confdir, _ = make_project(
        tmp_path,
        toml="",
        conf_extra=(
            "sources_from_toml = None\n"
            f'mounts = [{{"dir": "{bundle_path(tmp_path)}", "mount_at": "mnt", '
            '"if": "var.edition == \'pro\'"}]'
        ),
    )
    app = _build(make_app, confdir)
    assert app._warning.getvalue().count("mount_gate_unevaluable") == 1


# ---------------------------------------------------------------------------
# Fix round 1: a hard refusal must not name a table the user never wrote
# ---------------------------------------------------------------------------


MISPOINTED_MOUNTS_ONLY_TOML = """
[[source.mounts]]
dir = "{bundle}"
mount_at = "mnt"
if = "var.edition == 'pro'"

[needs.variant_data]
edition = "basic"
"""


def test_the_mispointed_needs_refusal_names_the_keys_actually_declared(
    make_app, tmp_path
):
    """A mounts-only project can now reach a guard that was rules-only.

    Before the restructure ``_resolve_variant_map`` sat behind a
    ``not spec.rules`` guard, so this refusal could only fire for a project
    that had written ``[[source.variant_sources]]``. It is now reachable by a
    project that declares no rules at all — and a hard error with no ``-W``
    escape must not describe a table the author never wrote, nor consequences
    ("every rule would exclude its files") that cannot happen.
    """
    confdir, _ = make_project(tmp_path, toml=MISPOINTED_MOUNTS_ONLY_TOML)
    _stub_conf(
        confdir,
        "needs_stub_mispointed_mounts_only",
        inline="{}",
        file_ref="None",
        from_toml='"other.toml"',
    )
    with pytest.raises(Exception) as excinfo:
        _build(make_app, confdir)
    message = str(excinfo.value)
    assert "variant_data_unreadable" in message
    assert "[[source.variant_sources]]" not in message, message
    assert "`if` on `[[source.mounts]]`" in message, message
    assert "gate its whole bundle off" in message, message


# ---------------------------------------------------------------------------
# Fix round 1: two gated mounts contesting one mount_at, and the contest note
# ---------------------------------------------------------------------------


TWO_GATED_TOML = """
[[source.mounts]]
dir = "{bundle}"
mount_at = "mnt"
if = "var.edition == 'pro'"

[[source.mounts]]
dir = "{rival}"
mount_at = "mnt"
if = "var.edition == 'enterprise'"

[needs.variant_data]
edition = "basic"
"""


def test_two_gated_mounts_at_one_mount_at_take_the_lower_index_label(
    make_app, tmp_path
):
    """Neither registers, so both would supply ``mnt/index``. Who owns the label?

    ``_gated_mount_docnames`` uses ``setdefault`` so the lower-numbered gate
    owns a contested attribution. The page is absent either way, so only the
    label is at stake — but an arbitrary label would make the message depend on
    dictionary iteration order, and nothing would ever say so.
    """
    confdir, _ = make_project(
        tmp_path, toml=TWO_GATED_TOML, host_entries=("mnt/index",)
    )
    attributed: dict[str, str] = {}
    app = _build(make_app, confdir, attribution=attributed, warningiserror=True)
    assert attributed["mnt/index"].startswith("[[source.mounts]][0]")
    assert attributed["mnt/binternal"].startswith("[[source.mounts]][0]")
    assert app.statuscode == 0, "a correctly gated build must pass -W"


def test_a_contested_gated_mount_says_why_its_attribution_is_empty(make_app, tmp_path):
    """The user's only bridge from a bare ``toc.not_readable`` back to the gate.

    When a live mount or the host claims a docname the gated bundle would have
    supplied, the gated pass takes the same whole-mount skip the live path
    takes, and attributes nothing — so a reference to the bundle's *other*
    pages is an ordinary warning. That is the documented conservative
    direction, but without this sentence the build log connects none of it to
    the gate the author wrote.
    """
    confdir, _ = make_project(
        tmp_path, toml=TWO_MOUNTS_TOML, host_entries=("mnt/index",)
    )
    app = _build(make_app, confdir)
    status = app._status.getvalue()
    assert MOUNT_GATED_CODE in status
    assert "Attribution suppressed" in status, status
    assert "mnt/index" in status


def test_an_uncontested_gated_mount_carries_no_contest_note(make_app, tmp_path):
    """The negative control, so the note means something when it appears."""
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "basic"))
    app = _build(make_app, confdir)
    status = app._status.getvalue()
    assert MOUNT_GATED_CODE in status
    assert "Attribution suppressed" not in status


# ---------------------------------------------------------------------------
# Fix round 2: the gate pairing must not depend on a mount's POSITION
# ---------------------------------------------------------------------------


PREPENDING_HANDLER_CONF = """
def _prepend(app, config):
    config["mounts"] = [
        {{"dir": "{rival}", "mount_at": "riv"}},
        *config["mounts"],
    ]


def setup(app):
    # 460 is inside the (450, 500) window, and this handler is deterministic:
    # the resulting `mounts` value is byte-identical on every build.
    app.connect("config-inited", _prepend, priority=460)
"""


def test_a_prepending_handler_does_not_over_report_a_decided_gate(make_app, tmp_path):
    """A mount the reader DID decide must not be reported as one it did not.

    The gate here comes from ``ubproject.toml`` and was evaluated at priority
    450. A handler at 460 then prepends a computed mount, which shifts the
    gated mount from index 0 to index 1 — and nothing about the configuration
    is broken by that: the `mounts` value is byte-identical across builds, so
    the index-keying `_wiring_signature` relies on is perfectly stable.

    Pairing the reader's verdict to a POSITION made this a guaranteed spurious
    warning on every build, carrying a reason ("the mount reached the parser
    after that reader ran") that is false for this mount.
    """
    confdir, _ = make_project(
        tmp_path,
        toml=DIR_MOUNT_TOML.replace("EDITION", "basic"),
        conf_extra=PREPENDING_HANDLER_CONF.format(
            rival=(tmp_path / "rival").as_posix()
        ),
    )
    app = _build(make_app, confdir)
    warning = app._warning.getvalue()
    assert "mnt/index" not in app.env.found_docs, "still gated"
    assert "riv/index" in app.env.found_docs, "the prepended mount is live"
    assert "mount_gate_unevaluable" not in warning, warning


def test_a_prepending_handler_keeps_the_gates_attribution(make_app, tmp_path):
    """The same shift must not lose the attribution across the 450/500 seam.

    The gate label and the discovery dict have to name the same mount. Keying
    one on the reader's view of the list and the other on the parser's meant a
    prepend silently attributed nothing — a second spurious ``-W`` red on the
    same working project, this time with no message explaining it at all.
    """
    confdir, _ = make_project(
        tmp_path,
        toml=DIR_MOUNT_TOML.replace("EDITION", "basic"),
        conf_extra=PREPENDING_HANDLER_CONF.format(
            rival=(tmp_path / "rival").as_posix()
        ),
        host_entries=("mnt/index", "riv/index"),
    )
    attributed: dict[str, str] = {}
    app = _build(make_app, confdir, attribution=attributed, warningiserror=True)
    assert "mnt/index" in attributed, attributed
    assert attributed["mnt/index"].startswith("[[source.mounts]][1]"), attributed
    assert "WARNING" not in app._warning.getvalue()
    assert app.statuscode == 0


@pytest.mark.parametrize("written", ['""', '"   "', "3", "True"])
def test_a_degenerate_condition_is_reported_exactly_once(make_app, tmp_path, written):
    """One mount, one gate, one record — whatever the ``if`` value looks like.

    The reader recorded the condition it saw; the parser stored the same value
    through a ``repr`` fallback for anything that is not a usable condition
    string. The two never agreed, so a mount the reader had already reported
    was reported a SECOND time by the parser, under a different label and with
    a reason that was false. The log read as two mounts.
    """
    confdir, _ = make_project(
        tmp_path,
        toml="",
        conf_extra=(
            "sources_from_toml = None\n"
            f'mounts = [{{"dir": "{bundle_path(tmp_path)}", "mount_at": "mnt", '
            f'"if": {written}}}]'
        ),
    )
    app = _build(make_app, confdir)
    warning = app._warning.getvalue()
    assert "mnt/index" not in app.env.found_docs, "fail closed"
    assert warning.count("mount_gate_unevaluable") == 1, warning


def test_a_mount_replaced_inside_the_window_is_still_reported(make_app, tmp_path):
    """The catch the pairing exists for, kept across the redesign.

    Constructed so that position alone cannot answer it. The reader gates the
    TOML mount OFF, so its condition really is in the decided multiset and
    there really is one decided gate at index 0. A handler at 470 then swaps in
    a mount carrying a DIFFERENT condition at that same index.

    Nothing evaluated the new condition, so the bundle must be gated off and
    said so. A mechanism that matched on position — "index 0, and one gate was
    decided" — would consume the entry and stay quiet, which is why the
    matching is on the condition string.
    """
    swapped = "var.edition == 'enterprise'"
    confdir, _ = make_project(
        tmp_path,
        toml=DIR_MOUNT_TOML.replace("EDITION", "basic"),
        conf_extra=(
            "def _swap(app, config):\n"
            "    config['mounts'] = [\n"
            f'        {{"dir": "{bundle_path(tmp_path)}", "mount_at": "mnt", '
            f'"if": "{swapped}"}}\n'
            "    ]\n"
            "\n"
            "def setup(app):\n"
            "    app.connect('config-inited', _swap, priority=470)\n"
        ),
    )
    app = _build(make_app, confdir)
    warning = app._warning.getvalue()
    assert "mnt/index" not in app.env.found_docs, "fail closed"
    assert "mount_gate_unevaluable" in warning, warning
    assert swapped in warning, warning


# ---------------------------------------------------------------------------
# Fix round 2: the record must not promise a downgrade it did not perform
# ---------------------------------------------------------------------------


def test_a_strict_mount_at_skip_says_why_the_attribution_is_empty(make_app, tmp_path):
    """``strict_mount_at`` empties a gated mount's attribution too.

    The contest is not the only whole-mount skip the gated pass takes, and the
    record's closing clause — "toctree references to its pages are downgraded"
    — is false for every one of them. A user gets a bare ``toc.not_readable``
    under a log line telling them it was downgraded.
    """
    toml = DIR_MOUNT_TOML.replace(
        'mount_at = "mnt"', 'mount_at = "mnt"\nstrict_mount_at = true'
    )
    confdir, _ = make_project(
        tmp_path,
        toml=toml.replace("EDITION", "basic"),
        host_entries=("mnt/placeholder",),
        host_files={"mnt/placeholder.rst": "Placeholder\n===========\n"},
    )
    app = _build(make_app, confdir)
    status = app._status.getvalue()
    assert MOUNT_GATED_CODE in status
    assert "Attribution suppressed" in status, status
    assert "directory at the mount point" in status, status
    assert "Toctree references to its pages are downgraded." not in status, status


def test_an_absent_root_skip_says_why_the_attribution_is_empty(make_app, tmp_path):
    """The shape the suppression of ``missing_path`` exists for, said out loud.

    "A bundle its CI has not checked out" is the headline reason a gated
    mount's absent root goes unreported — so gate-a-bundle-you-do-not-have,
    reference it from a 150% index, and the build was red under a log line
    claiming the reference had been downgraded.
    """
    toml = DIR_MOUNT_TOML.replace('dir = "{bundle}"', 'dir = "{bundle}-gone"')
    confdir, _ = make_project(tmp_path, toml=toml.replace("EDITION", "basic"))
    app = _build(make_app, confdir)
    status = app._status.getvalue()
    assert MOUNT_GATED_CODE in status
    assert "Attribution suppressed" in status, status
    assert "not on disk" in status, status


def test_a_gated_mount_that_attributes_its_pages_still_promises_the_downgrade(
    make_app, tmp_path
):
    """The positive control: the clause is conditional, not deleted."""
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "basic"))
    app = _build(make_app, confdir)
    status = app._status.getvalue()
    assert "are downgraded" in status, status
    assert "Attribution suppressed" not in status


def test_a_live_gates_condition_does_not_shelter_an_unevaluated_twin(
    make_app, tmp_path
):
    """Only the gated-OFF gates go into the decided multiset, and here is why.

    The reader evaluates ``var.edition == 'pro'`` to TRUE and strips the key,
    so that mount reaches the parser carrying no gate at all and matches
    nothing. A handler at 460 then appends a mount whose ``if`` is the *same
    string*. Nothing evaluated that one, so it must be gated off and said so.

    Recording every gate the reader saw — rather than only the ones it gated —
    leaves a spare entry in the multiset with no mount to claim it, and the
    interloper consumes it instead. The bundle then disappears in silence,
    which is the single way an unevaluated gate could still slip past the seam
    that exists to catch it.
    """
    confdir, _ = make_project(
        tmp_path,
        toml=DIR_MOUNT_TOML.replace("EDITION", "pro"),
        conf_extra=(
            "def _append(app, config):\n"
            "    config['mounts'] = [\n"
            "        *config['mounts'],\n"
            f'        {{"dir": "{(tmp_path / "rival").as_posix()}", "mount_at": "riv", '
            '"if": "var.edition == \'pro\'"},\n'
            "    ]\n"
            "\n"
            "def setup(app):\n"
            "    app.connect('config-inited', _append, priority=460)\n"
        ),
    )
    app = _build(make_app, confdir)
    warning = app._warning.getvalue()
    assert "mnt/index" in app.env.found_docs, "the reader's own mount is live"
    assert "riv/index" not in app.env.found_docs, "the interloper is gated"
    assert "mount_gate_unevaluable" in warning, warning
    assert "[[source.mounts]][1]" in warning, warning


# ---------------------------------------------------------------------------
# Fix round 3: "do not record twice" and "do not attribute" are different
# questions, and one exclusion was answering both
# ---------------------------------------------------------------------------


def test_an_undecided_gate_still_gets_its_toctree_downgrade(make_app, tmp_path):
    """De-duplicating the RECORD must not withhold the ATTRIBUTION.

    A genuinely gated TOML mount, plus a handler at 460 appending a second
    gated mount with a different condition. The appended one is undecided, so
    it is reported once as ``mount_gate_unevaluable`` and — correctly — not a
    second time as an ordinary gated mount.

    But its pages are still gone for exactly the reason the downgrade exists
    for, so a toctree entry naming one of them must be downgraded rather than
    arriving as a bare ``toc.not_readable`` with nothing connecting it to any
    gate. One exclusion was answering both questions.
    """
    confdir, _ = make_project(
        tmp_path,
        toml=DIR_MOUNT_TOML.replace("EDITION", "basic"),
        conf_extra=(
            "def _append(app, config):\n"
            "    config['mounts'] = [\n"
            "        *config['mounts'],\n"
            f'        {{"dir": "{(tmp_path / "rival").as_posix()}", "mount_at": "riv", '
            '"if": "var.edition == \'enterprise\'"},\n'
            "    ]\n"
            "\n"
            "def setup(app):\n"
            "    app.connect('config-inited', _append, priority=460)\n"
        ),
        host_entries=("mnt/index", "riv/index"),
    )
    attributed: dict[str, str] = {}
    app = _build(make_app, confdir, attribution=attributed)
    warning = app._warning.getvalue()
    status = app._status.getvalue()
    assert "riv/index" in attributed, attributed
    assert attributed["riv/index"].startswith("[[source.mounts]][1]"), attributed
    assert "toc.not_readable" not in warning, warning
    # Still exactly one diagnostic for the undecided mount, and no ordinary
    # gated record duplicating it.
    assert warning.count("mount_gate_unevaluable") == 1, warning
    assert status.count("[[source.mounts]][1]") == 1, status


def test_a_duplicate_condition_costs_only_the_note(make_app, tmp_path):
    """The residual the code claims, held to its own words.

    A handler at 460 prepends a mount whose ``if`` is character-for-character
    the one the reader already decided. The interloper consumes the multiset
    entry, so the innocent reader-decided mount is the one flagged undecided —
    a mislabel, and the documented cost.

    What must NOT also be lost is that mount's attribution: its pages are
    genuinely gated off, and excluding it from the attribution turned a
    mislabel into a second, unexplained warning. With the two consumers split,
    the residual really is only the note, which is what the docstring says.
    """
    confdir, _ = make_project(
        tmp_path,
        toml=DIR_MOUNT_TOML.replace("EDITION", "basic"),
        conf_extra=(
            "def _prepend(app, config):\n"
            "    config['mounts'] = [\n"
            f'        {{"dir": "{(tmp_path / "rival").as_posix()}", "mount_at": "riv", '
            '"if": "var.edition == \'pro\'"},\n'
            "        *config['mounts'],\n"
            "    ]\n"
            "\n"
            "def setup(app):\n"
            "    app.connect('config-inited', _prepend, priority=460)\n"
        ),
        host_entries=("mnt/index", "riv/index"),
    )
    attributed: dict[str, str] = {}
    app = _build(make_app, confdir, attribution=attributed)
    assert "mnt/index" in attributed, attributed
    assert "riv/index" in attributed, attributed
    assert "toc.not_readable" not in app._warning.getvalue()


def test_the_decided_counter_is_not_drained_on_the_application(make_app, tmp_path):
    """The parse seam must not consume the reader's record as it reads it.

    ``config-inited`` fires once per application today, so draining the stored
    Counter is latent rather than live — but the failure it invites is every
    gated project collecting a spurious ``-W`` warning, and the trigger is
    anything as ordinary as a second consumer of the decided set.
    """
    confdir, _ = make_project(tmp_path, toml=DIR_MOUNT_TOML.replace("EDITION", "basic"))
    app = _build(make_app, confdir)
    decided = getattr(app, _DECIDED_GATES_KEY)
    assert decided["var.edition == 'pro'"] == 1, dict(decided)


def test_the_both_keys_refusal_reads_as_one_sentence(make_app, tmp_path):
    """Two halves joined mid-sentence must not each start with a capital.

    The message names what the file declares and what an empty variant map
    would cost, and both halves are generated. Joined with ``"; "`` and left
    capitalised, the result read as two sentences beginning inside a third.
    """
    toml = """
    [[source.mounts]]
    dir = "{bundle}"
    mount_at = "mnt"
    if = "var.edition == 'pro'"

    [[source.variant_sources]]
    if = "var.edition == 'pro'"
    files = ["hostgated.rst"]

    [needs.variant_data]
    edition = "basic"
    """
    confdir, _ = make_project(
        tmp_path,
        toml=toml,
        host_files={"hostgated.rst": "Gated\n=====\n"},
    )
    _stub_conf(
        confdir,
        "needs_stub_both_keys_sentence",
        inline="{}",
        file_ref="None",
        from_toml='"other.toml"',
    )
    with pytest.raises(Exception) as excinfo:
        _build(make_app, confdir)
    message = str(excinfo.value)
    assert "; Every" not in message, message
    assert "every rule would report" in message, message
    assert "and every mount `if` would report" in message, message
    assert "both `[[source.variant_sources]]` and" in message, message
