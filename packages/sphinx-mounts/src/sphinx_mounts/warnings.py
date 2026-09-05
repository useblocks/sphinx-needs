"""Reclassify the toctree warnings a variant rule causes.

A rule that removes a document leaves every toctree entry naming it dangling,
and Sphinx warns — correctly, from its point of view: the document really is
missing. In a 150% model a shared index listing every edition's pages is the
normal shape, so those warnings fire on configurations that are perfectly
right, and ``sphinx-build -W`` fails a build that has nothing wrong with it.

Three warnings are involved, all measured on Sphinx 7.4 and 8.2/9.x:

============================================ ================================
Case                                         Record
============================================ ================================
explicit entry, ``exclude_patterns``-removed ``type='toc'``, ``subtype='excluded'``
explicit entry, never existed (a mount)      ``type='toc'``, ``subtype='not_readable'``
``:glob:`` entry matching nothing            **no type**; ``subtype='empty_glob'`` on 8+, nothing on 7.4
============================================ ================================

The third row is why ``suppress_warnings`` cannot be the mechanism: with no
``type``, ``WarningSuppressor``'s ``f'{type}.{subtype}'`` key can never match
it, so ``suppress_warnings = ["toc.empty_glob"]`` does not work upstream
either. Suppression is also the wrong verb — it would hide a genuinely broken
reference just as readily.

**What this module does instead: downgrade to INFO and reword, never drop.**
:meth:`DowngradeFilter.filter` always returns ``True``. A record it does not
recognise passes through untouched; a record it does recognise is mutated in
place to an INFO record naming the rule that removed the document, and is still
printed.

Where the filter is attached is the load-bearing part
--------------------------------------------------------

It goes on the **exact emitting child loggers**, resolved from the emitting
modules' own logger objects rather than from a hand-written string. Not on
"the sphinx logger", and not on its handlers. Three measured reasons:

* ``logging.Logger.callHandlers`` walks ancestor loggers' **handlers** but
  never applies ancestor loggers' **filters**, so a filter on ``sphinx``
  never sees a record emitted by ``sphinx.sphinx.directives.other``. (It
  appears to work for read-phase warnings only because Sphinx buffers those
  through ``pending_warnings()`` and replays them with
  ``MemoryHandler.flushTo(logger)`` on the ``sphinx`` logger itself, which
  does run that logger's filters. That is an accident of the buffering path,
  not a contract: consistency-phase warnings are not replayed and are missed.)
* A **handler**-level filter runs in the parent process under
  ``sphinx-build -j``, *after* ``convert_serializable`` has done
  ``r.msg = r.getMessage()`` and ``r.args = ()``
  (``sphinx/util/logging.py``). The docname this filter attributes on lives in
  ``record.args[0]``, so a handler-level filter silently stops matching under
  parallel reads — a hazard invisible to any serial test.
* ``Logger.handle`` applies the emitting logger's own filters **before**
  ``callHandlers``, so the mutation happens before ``WarningSuppressor``
  increments ``app._warncount``, before ``WarningIsErrorFilter`` (7.4) and
  before ``_RaiseOnWarningFilter`` (``--exception-on-warning``) can raise.
  Every one of those is a *handler* filter, so a *logger* filter is upstream
  of all of them on every supported version.

The second logger, ``sphinx.sphinx.environment.adapters.toctree``, is not
padding: it is where the same two subtypes are emitted at **resolve** time,
which is the path a build takes when documents leave without any referring
document being re-read.
"""

from __future__ import annotations

import logging as stdlib_logging
import posixpath
import weakref
from typing import TYPE_CHECKING

import sphinx.directives.other
import sphinx.environment.adapters.toctree
from sphinx.util.matching import patfilter

if TYPE_CHECKING:
    from collections.abc import Mapping

#: Fallback names for the emitting loggers, used only if the modules stop
#: exposing a module-level ``logger``. Sphinx's own
#: ``sphinx.util.logging.getLogger`` prefixes ``sphinx.``, hence the doubled
#: segment. Resolution prefers the live objects (see
#: :func:`resolve_toctree_logger_names`) so that an upstream module move is a
#: loud self-check failure rather than a filter that quietly stops firing.
FALLBACK_LOGGER_NAMES = (
    "sphinx.sphinx.directives.other",
    "sphinx.sphinx.environment.adapters.toctree",
)

#: The code the reworded INFO record carries.
#:
#: In the ``mounts.*`` namespace even though the record originates inside
#: Sphinx: it is sphinx-mounts that reclassified it, and putting it here is
#: what makes "quiet this extension" a coherent idea. The mirror of ubCode's
#: ``toctree.variant_excluded``.
VARIANT_EXCLUDED_CODE = "mounts.variant_excluded_reference"

#: Warning subtypes carrying an explicit docname in ``record.args[0]``.
_ATTRIBUTED_SUBTYPES = frozenset({"excluded", "not_readable", "not_included"})

#: Characters that make a toctree entry a glob rather than a docname.
_GLOB_CHARS = "*?["


def resolve_toctree_logger_names() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(resolved names, names that had to fall back)``.

    Each name is read off the emitting module's own ``logger`` object —
    ``sphinx.directives.other.logger.logger.name`` — rather than hard-coded,
    because the string is derived from Sphinx's module layout and a module move
    upstream would otherwise un-hook the filter in silence. When the attribute
    is gone the hard-coded name is used *and reported*, so the failure mode is
    a message naming the exact seam rather than warnings that quietly come
    back.
    """
    modules = (sphinx.directives.other, sphinx.environment.adapters.toctree)
    names: list[str] = []
    degraded: list[str] = []
    for module, fallback in zip(modules, FALLBACK_LOGGER_NAMES, strict=True):
        adapter = getattr(module, "logger", None)
        inner = getattr(adapter, "logger", None)
        name = getattr(inner, "name", None)
        if isinstance(name, str) and name:
            names.append(name)
        else:
            names.append(fallback)
            degraded.append(fallback)
    return tuple(names), tuple(degraded)


def _docname_join(base: str, target: str) -> str:
    """Resolve a toctree entry against the referring docname.

    The same computation ``sphinx.util.docname_join`` performs, inlined so this
    module does not depend on which of Sphinx's re-exports survives a release.
    """
    return posixpath.normpath(posixpath.join("/" + base, "..", target))[1:]


class DowngradeFilter(stdlib_logging.Filter):
    """Turn variant-caused toctree warnings into attributed INFO records.

    :param excluded: Docname -> the label of the rule that removed it.
    """

    def __init__(
        self,
        excluded: Mapping[str, str],
        logger_names: tuple[str, ...],
        owner: object,
    ) -> None:
        super().__init__()
        self._excluded = dict(excluded)
        self._docnames = sorted(self._excluded)
        #: The names this instance was actually installed on. Matched against
        #: ``record.name`` for the type-less 7.4 glob arm rather than the
        #: fallback constant — hard-coding the string there would defeat the
        #: very indirection :func:`resolve_toctree_logger_names` exists for,
        #: and would be correct only for as long as resolved == fallback.
        self._logger_names = tuple(logger_names)
        #: Which application installed this filter. The loggers are
        #: process-global and a ``Sphinx`` application is not, so removal has
        #: to be able to say "mine" — otherwise a rule-less application strips
        #: a live one's filter on its way past.
        self.owner_id = id(owner)
        self._owner = weakref.ref(owner)

    def owned_by(self, owner: object) -> bool:
        """Whether ``owner`` is the application that installed this filter."""
        return self.owner_id == id(owner)

    def orphaned(self) -> bool:
        """Whether the installing application has been collected.

        Kept for diagnostics only. It is NOT a lifecycle signal: a ``Sphinx``
        application stays reachable from process-global state, so this is
        essentially always ``False`` even after the caller drops its reference
        — which is why the lifecycle is "remove all, then install mine".
        """
        return self._owner() is None

    def filter(self, record: stdlib_logging.LogRecord) -> bool:
        """Always ``True``. Recognised records are mutated, never dropped.

        Returning ``False`` would make a variant-excluded reference invisible,
        which is the opposite of what is wanted: the reference is the *only*
        place left where a rule that removed more than the author meant is
        still visible, because the file itself is gone from search,
        ``objects.inv``, cross-references and the page tree.
        """
        if record.levelno < stdlib_logging.WARNING or not record.args:
            return True
        target = record.args[0] if isinstance(record.args, tuple) else None
        if not isinstance(target, str):
            return True
        subtype = getattr(record, "subtype", None)
        warning_type = getattr(record, "type", None)
        if warning_type == "toc" and subtype in _ATTRIBUTED_SUBTYPES:
            rule = self._excluded.get(target)
            if rule is not None:
                _downgrade(record, target, rule, glob=False)
            return True
        if self._is_empty_glob(record, subtype, warning_type, target):
            pattern = self._joined_pattern(record, target)
            matched = patfilter(self._docnames, pattern)
            if matched:
                _downgrade(record, target, self._excluded[matched[0]], glob=True)
        return True

    def _is_empty_glob(
        self,
        record: stdlib_logging.LogRecord,
        subtype: object,
        warning_type: object,
        target: str,
    ) -> bool:
        """Recognise the type-less "glob matched nothing" warning.

        Sphinx 8+ gives it ``subtype='empty_glob'``; 7.4 gives it neither a
        type nor a subtype, so there the discriminators are the emitting logger,
        the absence of both, and an argument that looks like a glob. The
        attribution itself is what makes a false positive harmless: the record
        is only touched when the pattern matches a docname a rule removed.
        """
        if subtype == "empty_glob":
            return True
        return (
            warning_type is None
            and subtype is None
            and record.name in self._logger_names
            and any(char in target for char in _GLOB_CHARS)
        )

    def _joined_pattern(self, record: stdlib_logging.LogRecord, target: str) -> str:
        """Absolutise a ``:glob:`` entry against the document that wrote it.

        ``record.args[0]`` is the entry exactly as authored, so a pattern in a
        sub-directory's index is relative. The referring docname is on the
        ``addnodes.toctree`` node Sphinx passes as ``location`` (its ``parent``
        key), which at this seam is still the live node rather than a rendered
        string.
        """
        location = getattr(record, "location", None)
        parent = None
        with_get = getattr(location, "get", None)
        if callable(with_get):
            parent = with_get("parent")
        if isinstance(parent, str) and parent:
            return _docname_join(parent, target)
        return target


def _downgrade(
    record: stdlib_logging.LogRecord, target: str, rule: str, *, glob: bool
) -> None:
    """Rewrite ``record`` in place as an attributed INFO record."""
    record.levelno = stdlib_logging.INFO
    record.levelname = "INFO"
    what = (
        f"toctree glob pattern {target!r} matched only documents this variant excludes"
        if glob
        else f"toctree entry {target!r} names a document this variant excludes"
    )
    record.msg = (
        f"sphinx-mounts: {what}, per {rule}. "
        f"The reference is left unresolved on purpose — in a 150% model an "
        f"index listing every variant's pages is the normal shape. "
        f"[{VARIANT_EXCLUDED_CODE}]"
    )
    record.args = ()


def install_downgrade_filter(
    excluded: Mapping[str, str],
    owner: object,
) -> tuple[DowngradeFilter, tuple[str, ...], tuple[str, ...]]:
    """Attach a fresh :class:`DowngradeFilter` for ``owner``.

    ``owner`` is the ``Sphinx`` application the attribution belongs to; it is
    recorded on the filter so a diagnostic can say whose it is.

    **Every** existing filter is removed first, not only this owner's. The
    loggers are process-global and the alternative was measured to leak: an
    application that is CONSTRUCTED and never BUILT never reaches
    ``build-finished``, so its filter has no other way off — and per-owner
    keying left it attached to silence the next project's genuine warnings.
    A liveness sweep by ``weakref`` does not help either, because a ``Sphinx``
    application stays reachable from process-global state and is never
    collected.

    See :func:`remove_downgrade_filters` for what this does and does not
    promise about concurrency.

    :return: ``(filter, logger names, names that fell back)``.
    """
    names, degraded = resolve_toctree_logger_names()
    installed = DowngradeFilter(excluded, names, owner)
    remove_downgrade_filters()
    for name in names:
        stdlib_logging.getLogger(name).addFilter(installed)
    return installed, names, degraded


def remove_downgrade_filters(owner: object | None = None) -> None:
    """Detach every :class:`DowngradeFilter` from the emitting loggers.

    The loggers are **process-global** while a ``Sphinx`` application is not,
    and that gap is a real one rather than a tidiness concern. Two things go
    wrong without it, and both were measured in review:

    * a build that leaves its filter attached silences the NEXT build's
      genuine warnings and attributes them to a rule in a **different
      project** — with ``_warncount`` one lower, so a ``-W`` build that should
      fail passes. Anyone driving Sphinx as a library meets this:
      ``sphinx-autobuild``, a multi-project script, a test harness;
    * a rule-less application calling this on its way past used to strip a
      filter that a *live* application had installed.

    ``owner`` is accepted for call-site clarity and is deliberately **not** used
    to narrow what is removed. Per-owner removal was tried and leaked: an
    application constructed but never built never reaches ``build-finished``,
    so nothing ever took its filter off.

    **Genuinely interleaved applications in one process are out of contract.**
    Two `Sphinx` applications building at the same time share these
    process-global loggers, and no keying inside a `logging.Filter` can
    separate their records — the record carries no application. Sphinx is
    single-threaded per build, so the reachable shapes are sequential ones, and
    those are what this handles: whoever starts a build owns the loggers until
    it finishes.
    """
    names, _ = resolve_toctree_logger_names()
    for name in dict.fromkeys((*names, *FALLBACK_LOGGER_NAMES)):
        logger = stdlib_logging.getLogger(name)
        for existing in list(logger.filters):
            if isinstance(existing, DowngradeFilter):
                logger.removeFilter(existing)
