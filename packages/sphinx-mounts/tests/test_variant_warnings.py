"""The toctree warning downgrade, at the record level.

The end-to-end behaviour is covered in ``test_variant_sources.py``; this module
pins the two things a build cannot show:

* **where** the filter is attached. The names are a function of Sphinx's module
  layout, and only one attachment point survives all of: both supported Sphinx
  versions, the read phase and the consistency phase, ``-j2`` / ``-j4``, and
  ``--exception-on-warning``. A structural assertion is what notices a move to
  a seam that merely looks equivalent.
* the **resolve-time** arm. ``sphinx.sphinx.environment.adapters.toctree``
  emits the same two subtypes when documents leave without any referring
  document being re-read. Folding the verdict into config values makes that
  path rare — every document is re-read on a flip — so it is exercised here
  with synthetic records rather than left untested because it is hard to
  provoke.
"""

from __future__ import annotations

import logging as stdlib_logging
from typing import Any

import pytest

from sphinx_mounts.warnings import (
    FALLBACK_LOGGER_NAMES,
    VARIANT_EXCLUDED_CODE,
    DowngradeFilter,
    install_downgrade_filter,
    remove_downgrade_filters,
    resolve_toctree_logger_names,
)

EXCLUDED = {
    "hostgated": "[[source.variant_sources]][0] (if = \"var.edition == 'pro'\")",
    "mnt/binternal": "[[source.variant_sources]][0] (if = \"var.edition == 'pro'\")",
    "gated/a": "[[source.variant_sources]][1] (if = 'var.debug == True')",
}


class _FakeToctree(dict):
    """The bit of ``addnodes.toctree`` the filter reads: its ``parent`` key."""


def _record(
    name: str,
    args: tuple[Any, ...],
    *,
    warning_type: str | None = None,
    subtype: str | None = None,
    location: Any = None,
    level: int = stdlib_logging.WARNING,
) -> stdlib_logging.LogRecord:
    record = stdlib_logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=1,
        msg="toctree contains reference to excluded document %r",
        args=args,
        exc_info=None,
    )
    record.type = warning_type  # type: ignore[attr-defined]
    record.subtype = subtype  # type: ignore[attr-defined]
    record.location = location  # type: ignore[attr-defined]
    return record


#: The names the filter is actually installed on, resolved from Sphinx's own
#: modules. Record-level tests build their records with THESE, not with
#: :data:`FALLBACK_LOGGER_NAMES` — pinning the fallback constant would keep the
#: suite green through exactly the resolved/fallback divergence the indirection
#: exists to survive.
RESOLVED_NAMES, _DEGRADED = resolve_toctree_logger_names()


class _Owner:
    """Stands in for the ``Sphinx`` application that owns a filter."""


@pytest.fixture
def downgrade() -> DowngradeFilter:
    return DowngradeFilter(EXCLUDED, RESOLVED_NAMES, _Owner())


@pytest.fixture(autouse=True)
def _detach():
    yield
    remove_downgrade_filters()


# ---------------------------------------------------------------------------
# Attachment
# ---------------------------------------------------------------------------


def test_the_filter_is_attached_to_both_emitting_child_loggers() -> None:
    """Both loggers, and the *loggers* rather than the root or the handlers.

    A filter on ``logging.getLogger("sphinx")`` is never applied to a record
    emitted by a child logger — ``Logger.callHandlers`` walks ancestors'
    **handlers**, never their **filters**. It appears to work for read-phase
    warnings only because Sphinx replays those through
    ``MemoryHandler.flushTo(logger)`` on the ``sphinx`` logger itself, which is
    an accident of the buffering path: consistency-phase warnings are not
    replayed and are missed.

    A filter on the handlers fails differently and worse: under ``-j`` it runs
    in the parent, after ``convert_serializable`` has cleared ``record.args``,
    so the attribution silently stops matching.
    """
    owner = _Owner()
    install_downgrade_filter(EXCLUDED, owner)
    names, _ = resolve_toctree_logger_names()
    assert set(names) == set(FALLBACK_LOGGER_NAMES)
    assert names == RESOLVED_NAMES
    for name in names:
        logger = stdlib_logging.getLogger(name)
        assert any(isinstance(f, DowngradeFilter) for f in logger.filters), name
    root = stdlib_logging.getLogger("sphinx")
    assert not any(isinstance(f, DowngradeFilter) for f in root.filters)
    assert not any(
        isinstance(f, DowngradeFilter)
        for handler in root.handlers
        for f in handler.filters
    )


def test_reinstalling_replaces_rather_than_stacks() -> None:
    """One application rebuilding must not leave a stale attribution behind."""
    owner = _Owner()
    install_downgrade_filter(EXCLUDED, owner)
    install_downgrade_filter({"other": "rule"}, owner)
    for name in RESOLVED_NAMES:
        logger = stdlib_logging.getLogger(name)
        installed = [f for f in logger.filters if isinstance(f, DowngradeFilter)]
        assert len(installed) == 1, name
        assert installed[0]._excluded == {"other": "rule"}


def test_installing_removes_every_earlier_filter() -> None:
    """Installation is "remove all, then install mine", deliberately.

    Per-owner removal was tried first and leaked. An application that is
    CONSTRUCTED and never BUILT never reaches ``build-finished``, so its filter
    has no other way off, and a ``weakref`` liveness sweep does not help: a
    ``Sphinx`` application stays reachable from process-global state and is
    never collected. So the next application to install evicts whatever is
    there.

    Genuinely interleaved applications are **out of contract** — two builds
    running at once share these loggers and a record carries no application, so
    nothing inside a ``logging.Filter`` could separate them. Sphinx is
    single-threaded per build; the reachable shapes are sequential, and those
    are what this covers.
    """
    first, second = _Owner(), _Owner()
    install_downgrade_filter(EXCLUDED, first)
    install_downgrade_filter({"other": "rule"}, second)
    logger = stdlib_logging.getLogger(RESOLVED_NAMES[0])
    installed = [f for f in logger.filters if isinstance(f, DowngradeFilter)]
    assert len(installed) == 1, "the earlier filter is evicted, not stacked"
    assert installed[0].owned_by(second)
    assert installed[0]._excluded == {"other": "rule"}


def test_removal_takes_every_filter_off_whoever_installed_it() -> None:
    """Stand-down is unconditional for the same reason installation is."""
    install_downgrade_filter(EXCLUDED, _Owner())
    remove_downgrade_filters(_Owner())
    for name in RESOLVED_NAMES:
        logger = stdlib_logging.getLogger(name)
        assert not any(isinstance(f, DowngradeFilter) for f in logger.filters)


def test_removal_detaches_from_every_logger() -> None:
    install_downgrade_filter(EXCLUDED, _Owner())
    remove_downgrade_filters()
    for name in RESOLVED_NAMES:
        logger = stdlib_logging.getLogger(name)
        assert not any(isinstance(f, DowngradeFilter) for f in logger.filters)


# ---------------------------------------------------------------------------
# What is downgraded, and what is not
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("subtype", ["excluded", "not_readable", "not_included"])
@pytest.mark.parametrize("name", RESOLVED_NAMES, ids=["read", "resolve"])
def test_an_attributed_docname_is_downgraded(
    downgrade: DowngradeFilter, name: str, subtype: str
) -> None:
    """Both emitting loggers, all three attributable subtypes.

    ``not_included`` is on the list because the resolve-time site emits it for
    the same cause, and a variant-excluded document is exactly a document that
    is no longer included in anything.
    """
    record = _record(name, ("hostgated",), warning_type="toc", subtype=subtype)
    assert downgrade.filter(record) is True
    assert record.levelno == stdlib_logging.INFO
    assert record.levelname == "INFO"
    assert VARIANT_EXCLUDED_CODE in record.getMessage()
    assert "var.edition == 'pro'" in record.getMessage()


def test_an_unattributed_docname_passes_through_untouched(
    downgrade: DowngradeFilter,
) -> None:
    """The negative control, at the record level.

    A downgrade that fired on any missing document would be a way to hide
    typos — which is precisely what makes ``suppress_warnings`` the wrong tool
    for this job.
    """
    record = _record(
        RESOLVED_NAMES[0], ("nosuchdoc",), warning_type="toc", subtype="excluded"
    )
    before = record.getMessage()
    assert downgrade.filter(record) is True
    assert record.levelno == stdlib_logging.WARNING
    assert record.getMessage() == before


def test_an_unrelated_warning_from_the_same_logger_is_untouched(
    downgrade: DowngradeFilter,
) -> None:
    """``mounts.missing_path`` and friends are about a *misconfiguration*.

    The filter keys on the toctree subtypes, never on "anything mentioning a
    document a rule removed".
    """
    record = _record(
        RESOLVED_NAMES[0],
        ("hostgated",),
        warning_type="toc",
        subtype="duplicate_entry",
    )
    assert downgrade.filter(record) is True
    assert record.levelno == stdlib_logging.WARNING


def test_the_empty_glob_arm_is_downgraded_on_sphinx_8_plus(
    downgrade: DowngradeFilter,
) -> None:
    """``subtype='empty_glob'`` and — measured — **no** ``type``.

    Because ``WarningSuppressor`` builds its key as ``f'{type}.{subtype}'``,
    that missing type is why ``suppress_warnings = ["toc.empty_glob"]`` cannot
    reach this warning upstream either.
    """
    record = _record(
        RESOLVED_NAMES[0],
        ("gated/*",),
        subtype="empty_glob",
        location=_FakeToctree(parent="index"),
    )
    assert downgrade.filter(record) is True
    assert record.levelno == stdlib_logging.INFO
    assert "gated/*" in record.getMessage()


def test_the_empty_glob_arm_is_downgraded_on_sphinx_7_4(
    downgrade: DowngradeFilter,
) -> None:
    """On 7.4 the same warning carries neither a type nor a subtype.

    So there the discriminators are the emitting logger, the absence of both,
    and an argument that looks like a glob — and the attribution itself is what
    makes a false positive harmless.
    """
    record = _record(
        RESOLVED_NAMES[0],
        ("gated/*",),
        location=_FakeToctree(parent="index"),
    )
    assert downgrade.filter(record) is True
    assert record.levelno == stdlib_logging.INFO


def test_a_glob_is_resolved_against_the_referring_document(
    downgrade: DowngradeFilter,
) -> None:
    """``record.args[0]`` is the entry as authored, so it may be relative.

    The referring docname is on the ``addnodes.toctree`` node Sphinx passes as
    ``location``, which at this seam is still the live node rather than a
    rendered path string.
    """
    record = _record(
        RESOLVED_NAMES[0],
        ("binternal",),
        subtype="empty_glob",
        location=_FakeToctree(parent="mnt/index"),
    )
    assert downgrade.filter(record) is True
    assert record.levelno == stdlib_logging.INFO, "'binternal' joined to 'mnt/'"


def test_a_glob_matching_nothing_excluded_is_untouched(
    downgrade: DowngradeFilter,
) -> None:
    record = _record(
        RESOLVED_NAMES[0],
        ("elsewhere/*",),
        subtype="empty_glob",
        location=_FakeToctree(parent="index"),
    )
    assert downgrade.filter(record) is True
    assert record.levelno == stdlib_logging.WARNING


def test_a_record_with_cleared_args_is_untouched(downgrade: DowngradeFilter) -> None:
    """What a handler-level attachment would see under ``-j``.

    ``convert_serializable`` bakes the formatting into ``record.msg`` and sets
    ``record.args = ()`` before shipping a worker's records to the parent. This
    asserts the shape of that hazard rather than only describing it: a filter
    reached at that point cannot attribute anything, which is why the
    attachment is on the emitting logger instead.
    """
    record = _record(RESOLVED_NAMES[0], (), warning_type="toc", subtype="excluded")
    record.msg = "toctree contains reference to excluded document 'hostgated'"
    assert downgrade.filter(record) is True
    assert record.levelno == stdlib_logging.WARNING


def test_the_filter_never_returns_false(downgrade: DowngradeFilter) -> None:
    """Every path, including the ones that change nothing."""
    records = [
        _record(
            RESOLVED_NAMES[0],
            ("hostgated",),
            warning_type="toc",
            subtype="excluded",
        ),
        _record(
            RESOLVED_NAMES[0],
            ("nosuchdoc",),
            warning_type="toc",
            subtype="excluded",
        ),
        _record(
            RESOLVED_NAMES[1],
            ("mnt/binternal",),
            warning_type="toc",
            subtype="not_readable",
        ),
        _record(RESOLVED_NAMES[0], (), subtype="empty_glob"),
        _record(RESOLVED_NAMES[0], ("x",), level=stdlib_logging.INFO),
    ]
    assert all(downgrade.filter(record) is True for record in records)
