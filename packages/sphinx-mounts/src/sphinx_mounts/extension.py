"""Sphinx extension entry point for sphinx-mounts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
import os
from pathlib import Path
from typing import Any
import unicodedata

from docutils import nodes
from sphinx import addnodes
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.errors import ExtensionError
from sphinx.project import EXCLUDE_PATHS
from sphinx.util import logging
from sphinx.util.matching import get_matching_files, patmatch

from sphinx_mounts import __version__, dialect
from sphinx_mounts import warnings as mount_warnings
from sphinx_mounts.config import (
    MountConfig,
    TomlConfigError,
    VariantRule,
    VariantRuleError,
    VariantSourcesConfig,
    load_mounts_from_toml,
    load_variant_sources_from_toml,
    mount_label,
    parse_mounts,
)
from sphinx_mounts.logging import log_warning
from sphinx_mounts.mounter import (
    DocRoot,
    _build_walker,
    _is_within_any,
    _join_mount,
    _match_suffix,
    _MountAwareProject,
    install_mount_aware_project,
)
from sphinx_mounts.variants import (
    VariantConditionError,
    VariantDataError,
    VariantEvalError,
    interpret,
    resolve_variant_data,
    validate,
)

logger = logging.getLogger(__name__)

_CACHED_KEY = "_sphinx_mounts_parsed"

#: Application attribute holding what the variant reader decided, for the
#: ``builder-inited`` half to act on. See :class:`_VariantState`.
_VARIANT_STATE_KEY = "_sphinx_mounts_variant_state"

#: Application attribute caching the resolved TOML path setting, so the
#: deprecation warning for ``mounts_from_toml`` fires once rather than once per
#: reader.
_TOML_SETTING_KEY = "_sphinx_mounts_toml_setting"

#: Application attribute holding ``(state, attribution)`` so a second build of
#: the same application reuses the walk rather than repeating it. Keyed on the
#: state object's identity — see :func:`_on_install_variant_filter`.
_VARIANT_ATTRIBUTION_KEY = "_sphinx_mounts_variant_attribution"

#: Name of the :class:`~sphinx.environment.BuildEnvironment` attribute holding
#: the previous build's toctree-wiring signature.
#:
#: ``env-get-outdated`` compares the wiring the current build *would* produce
#: against this value, so an ``attach_to`` host doc is re-read exactly when a
#: mount's contribution to its toctree changed. The attribute travels inside
#: ``environment.pickle`` — ``BuildEnvironment.__getstate__`` clears only its
#: own unpickleable fields and keeps everything else — which is what lets the
#: comparison span two builds.
_WIRING_SIGNATURE_ATTR = "sphinx_mounts_wiring_signature"

#: Default file name for the declarative TOML configuration. The file is
#: resolved relative to Sphinx's ``confdir``. ``ubproject.toml`` is the
#: convention shared with other useblocks tooling (sphinx-needs,
#: sphinx-codelinks) so that a single declarative file can describe a
#: project's documentation setup to *every* downstream consumer — Sphinx,
#: IDE extensions, language servers, build-system integrations — without
#: any of them having to execute ``conf.py``.
DEFAULT_TOML_FILENAME = "ubproject.toml"


def _on_load_toml(app: Sphinx, config: Config) -> None:
    """Load mount entries from the TOML config file, if present.

    Runs on ``config-inited`` *before* :func:`_on_config_inited`. If
    ``mounts_from_toml`` resolves to an existing file, the mounts array it
    declares — ``[[source.mounts]]`` or top-level ``[[mounts]]``, see
    :func:`~sphinx_mounts.config.load_mounts_from_toml` for the two spellings
    and the rule against declaring both — replaces any value of ``mounts``
    set in ``conf.py``. If the file does not exist, or declares no mounts
    array at all, ``config.mounts`` is left untouched and any legacy
    conf.py-style value is used instead.
    """
    toml_setting = _resolve_toml_setting(app, config)
    if not toml_setting:
        return
    toml_path = (Path(app.confdir) / toml_setting).resolve()
    raw = load_mounts_from_toml(toml_path)
    if raw is None:
        logger.debug(
            "sphinx-mounts: no mounts loaded from TOML (path=%s, exists=%s).",
            toml_path,
            toml_path.is_file(),
        )
        return
    config["mounts"] = raw
    logger.info(
        "sphinx-mounts: loaded %d mount(s) from %s",
        len(raw),
        toml_path,
    )


def _on_config_inited(app: Sphinx, config: Config) -> None:
    """Validate the ``mounts`` config and cache the parsed result.

    ``config-inited`` fires *before* ``app.project`` is constructed
    (see :mod:`sphinx.application`), so the actual project replacement is
    deferred to ``builder-inited``. We still parse here to surface
    configuration errors as early as possible.
    """
    parsed = parse_mounts(getattr(config, "mounts", None), Path(app.confdir))
    setattr(app, _CACHED_KEY, parsed)


def _on_builder_inited(app: Sphinx) -> None:
    """Replace ``app.project`` with a mount-aware project.

    By the time ``builder-inited`` fires, ``app.project`` exists and the
    build environment has been bound to it. We swap both so that the
    subsequent ``env.find_files`` -> ``project.discover()`` call goes
    through our subclass.
    """
    parsed: tuple[MountConfig, ...] = getattr(app, _CACHED_KEY, ())
    if not parsed:
        return

    if not isinstance(app.project, _MountAwareProject):
        app.project = install_mount_aware_project(app.project, parsed)
        logger.info(
            "sphinx-mounts: installed mount-aware project with %d mount(s)",
            len(parsed),
        )

    if app.env is not None:
        app.env.project = app.project


def _on_doctree_read(app: Sphinx, doctree: nodes.document) -> None:
    """Extend (or create) toctrees in host docs to reference mount entries.

    For every mount whose ``attach_to`` equals the doc currently being
    read, locate the configured toctree (by ``toctree_index``, 0-based)
    and append the mount's entry docname(s) to it. Normally that is the
    single ``{mount_at}/{entry_doc}``; when ``attach_each`` is set on a
    file-list mount, *every* docname the mount produced is appended, in
    ``files`` order. If the host doc contains no toctree at all, a new
    one is added beneath the first section. If ``toctree_index`` exceeds
    the number of toctrees in the doc, a ``mounts.toctree_index`` warning
    is emitted and the mount is left unwired — the host doc is never
    modified against the author's layout.
    """
    parsed: tuple[MountConfig, ...] = getattr(app, _CACHED_KEY, ())
    if not parsed:
        return
    docname = app.env.docname
    targets = [(i, m) for i, m in enumerate(parsed) if m.attach_to == docname]
    if not targets:
        return

    project = getattr(app.env, "project", None)
    mount_docnames: dict[int, list[str]] = getattr(project, "_mount_entry_docnames", {})
    toctrees: list[addnodes.toctree] = list(doctree.findall(addnodes.toctree))

    for index, mount in targets:
        entries = _wired_entries(mount, index, mount_docnames)
        if not entries:
            continue
        target = _select_or_create_toctree(
            doctree, toctrees, docname, mount, index, entries[0]
        )
        if target is None:
            # toctree_index was out of range — the mount is left unwired.
            # Mark its docs as orphans so the build emits exactly one
            # warning (mounts.toctree_index) instead of additionally
            # reporting each of them as not included in any toctree
            # (toc.not_included) — the induced error must leave the host
            # project untouched.
            for entry in entries:
                app.env.metadata[entry]["orphan"] = True
            continue
        added: list[str] = []
        for entry in entries:
            if entry in target["includefiles"]:
                # Already referenced — the host author wrote it by hand, or
                # a freshly created toctree was seeded with the first entry.
                # Skip so attach_to stays idempotent.
                continue
            target["entries"].append((None, entry))
            target["includefiles"].append(entry)
            added.append(entry)
        logger.info(
            "sphinx-mounts: wired %r into toctree of %r",
            added or entries,
            docname,
        )


def _mount_toctree_entries(
    mount: MountConfig, index: int, mount_docnames: dict[int, list[str]]
) -> list[str]:
    """Return the docname(s) ``mount`` should wire into the host toctree.

    Normally the single ``{mount_at}/{entry_doc}`` (or bare ``entry_doc``
    for a root mount). With ``attach_each`` set, every docname the mount
    produced, in discovery order.
    """
    if mount.attach_each:
        return list(mount_docnames.get(index, []))
    if mount.mount_at is None:
        return [mount.entry_doc]
    return [f"{mount.mount_at}/{mount.entry_doc}"]


def _wired_entries(
    mount: MountConfig, index: int, mount_docnames: dict[int, list[str]]
) -> list[str]:
    """Return the entries ``mount`` may actually wire into its host toctree.

    This is :func:`_mount_toctree_entries` gated on what the mount really
    produced during ``discover()``. A mount that was skipped entirely
    (missing bundle, docname conflict, strict ``mount_at`` violation) or
    whose ``entry_doc`` is not among its files must not inject a reference
    into the host toctree — a dangling entry would be an un-suppressible
    ``toc.not_readable`` / ``toc.circular`` warning, i.e. the mount would
    modify the host project despite the problem.

    The same value is what :func:`_wiring_signature` compares across
    builds, so the "would wire" decision is made in exactly one place.
    """
    produced = set(mount_docnames.get(index, []))
    entries = _mount_toctree_entries(mount, index, mount_docnames)
    return [entry for entry in entries if entry in produced]


def _wiring_signature(
    parsed: tuple[MountConfig, ...], mount_docnames: dict[int, list[str]]
) -> dict[int, tuple[str, tuple[str, ...]]]:
    """Summarise the toctree wiring the current mount state implies.

    Maps the config-list index of every ``attach_to``-carrying mount to the
    pair ``(attach_to docname, entries it would inject)``.

    Mounts without ``attach_to`` never touch a host toctree, so they are
    **omitted entirely**. That omission is the only place the distinction is
    made: :func:`_on_env_get_outdated` walks this mapping rather than the
    mount list, so a mount that is not here cannot cause a host doc to be
    re-read. Keeping it as a single filter is deliberate — a second,
    redundant check in the handler would be untestable by construction, since
    nothing could observe its removal.

    Carrying ``attach_to`` in the value rather than looking it up again also
    means a mount that is re-pointed at a *different* host doc registers as a
    change.

    **Coupling worth knowing:** the mapping is keyed on the mount's position
    in the ``mounts`` config list, so inserting or reordering mounts shifts
    every key. That is safe only because ``mounts`` is registered with
    ``rebuild="env"`` (see :func:`setup`), which makes Sphinx re-read every
    document on any change to the config value — including a reorder. The
    signature therefore only has to survive changes to a bundle's *file set*,
    which never shift indices. If ``mounts`` ever loses ``rebuild="env"``, or
    a future mount source stops flowing through a config value, index-keying
    would silently mis-converge; ``test_mounts_confval_rebuilds_the_env``
    pins the setting so that cannot happen quietly. For the same reason
    ``toctree_index`` is not part of the signature.
    """
    return {
        index: (mount.attach_to, tuple(_wired_entries(mount, index, mount_docnames)))
        for index, mount in enumerate(parsed)
        if mount.attach_to is not None
    }


def _on_env_get_outdated(
    app: Sphinx,
    env: Any,
    _added: set[str],
    _changed: set[str],
    _removed: set[str],
) -> list[str]:
    """Report the ``attach_to`` host docs whose mount wiring went stale.

    :func:`_on_doctree_read` can only inject toctree entries into documents
    Sphinx decided to re-read, and a host doc's own mtime never moves when a
    *bundle* gains or loses its entry doc (``rebuild="env"`` does not help
    either — it fires on a change to the ``mounts`` config *value*, not to
    the bundle's file set). Without this handler the wiring goes permanently
    stale in both directions: a bundle that disappears leaves a dead
    ``href`` in the shipped HTML plus a ``toc.not_readable`` warning on every
    subsequent build, and a bundle that appears is never wired in at all —
    rendered, but missing from the navigation. Only ``sphinx-build -E``
    cleared either state.

    So compare the wiring this build would produce against the signature the
    previous build persisted on the env, and report every changed mount's
    ``attach_to`` docname as outdated.

    Reporting the host doc outdated has a second, load-bearing effect on a
    build that only *lost* documents: Sphinx guards both the env pickling
    and ``check_consistency()`` behind ``if updated_docnames:``, so such a
    build used to persist nothing and recompute the same "1 removed" for
    ever. One re-read makes it persist its env and converge. That only works
    when the ``attach_to`` target actually exists — see the ``found_docs``
    filtering below — so a mounted docname referenced solely by a
    hand-written host toctree keeps Sphinx's own removal-only behaviour.

    A missing previous signature means a fresh environment, where every
    document is read regardless, so nothing is reported and nothing is
    logged: the signature is simply recorded for the next build to compare
    against. An environment written by an older version of this extension
    cannot reach this branch, because adding ``env_version`` to
    :func:`setup` already invalidates it.

    The ``added`` / ``changed`` / ``removed`` sets Sphinx passes are not
    consulted — the decision rests entirely on the mount wiring, which is
    derived from ``discover()`` and not from what Sphinx already considers
    outdated — so they are named with a leading underscore.
    """
    parsed: tuple[MountConfig, ...] = getattr(app, _CACHED_KEY, ())
    if not parsed:
        return []
    mount_docnames: dict[int, list[str]] = getattr(
        getattr(env, "project", None), "_mount_entry_docnames", {}
    )
    current = _wiring_signature(parsed, mount_docnames)
    previous = getattr(env, _WIRING_SIGNATURE_ATTR, None)
    setattr(env, _WIRING_SIGNATURE_ATTR, current)
    if previous is None or previous == current:
        return []
    # Walking the signature, not ``parsed``: a mount without ``attach_to`` is
    # not in it and so cannot reach this loop at all.
    outdated: list[str] = []
    for index, entry in current.items():
        if previous.get(index) == entry:
            continue
        attach_to = entry[0]
        if attach_to not in outdated:
            outdated.append(attach_to)
    # Sphinx intersects the returned names with ``env.found_docs`` anyway
    # (``sphinx/builders/__init__.py``: ``changed.update(set(docs) &
    # self.env.found_docs)``), so returning a name it will drop is harmless —
    # but *claiming* to re-read it is not. A mount whose ``attach_to`` is a
    # typo would otherwise announce "re-reading ['nosuchdoc']" on every build
    # for ever, an action it cannot perform. The missing target itself is
    # reported once, by ``_on_check_consistency``.
    found: frozenset[str] = frozenset(getattr(env, "found_docs", ()))
    actionable = [docname for docname in outdated if docname in found]
    if actionable:
        logger.info(
            "sphinx-mounts: mount wiring changed — re-reading %r",
            actionable,
        )
    return actionable


def _select_or_create_toctree(  # noqa: PLR0913
    doctree: nodes.document,
    toctrees: list[addnodes.toctree],
    docname: str,
    mount: MountConfig,
    index: int,
    seed_entry: str,
) -> addnodes.toctree | None:
    """Return the toctree in ``doctree`` that ``mount`` should extend.

    If the doc has no toctree yet, build one (seeded with ``seed_entry``),
    attach it at the end of the first section, and register it in
    ``toctrees`` so later mounts targeting the same doc reuse it. Otherwise
    return the toctree selected by ``mount.toctree_index``. When the index
    is out of range, emit a ``mounts.toctree_index`` warning and return
    ``None`` — the mount is left unwired instead of failing the build.

    :param index: The mount's position in the ``mounts`` config list,
        used in the warning's :func:`mount_label`.
    """
    if not toctrees:
        node = _build_toctree_node(docname, seed_entry)
        _attach_to_first_section(doctree, node)
        toctrees.append(node)
        return node
    if mount.toctree_index >= len(toctrees):
        msg = (
            f"sphinx-mounts: {mount_label(mount, index)} requested "
            f"toctree_index={mount.toctree_index} in host doc "
            f"{docname!r}, but only {len(toctrees)} toctree(s) exist — "
            f"the mount is not wired into any toctree."
        )
        log_warning(logger, msg, "toctree_index", location=docname)
        return None
    return toctrees[mount.toctree_index]


def _on_check_consistency(app: Sphinx, env: Any) -> None:
    """Warn when ``attach_to`` targets a docname that does not exist."""
    parsed: tuple[MountConfig, ...] = getattr(app, _CACHED_KEY, ())
    if not parsed:
        return
    found = set(env.found_docs)
    for index, mount in enumerate(parsed):
        if mount.attach_to is None:
            continue
        if mount.attach_to not in found:
            msg = (
                f"sphinx-mounts: {mount_label(mount, index)} has "
                f"attach_to={mount.attach_to!r}, but that docname does "
                f"not exist in the project — nothing was extended."
            )
            log_warning(logger, msg, "attach_to_missing")


def _on_check_path_confinement(app: Sphinx, env: Any) -> None:  # noqa: ARG001
    """Fail (or warn) when a mounted doc references a file outside its
    bundle root.

    Every file a doc references — via Sphinx ``relfn2path`` directives
    (literalinclude, image, graphviz, uml, mermaid, …) or docutils-native
    ones (include, ``raw :file:``, ``csv-table :file:``) — is recorded in
    ``env.dependencies[docname]``. Resolving each dependency and requiring
    it to live under the mount's bundle root catches escaping references
    uniformly, regardless of directive. An escape would otherwise drag an
    outside file into the host build (and, for asset directives, copy it
    into the host's ``_images``/``_downloads`` output, risking collisions
    with host files). ``path_check`` selects the reaction per mount.
    """
    doc_roots: dict[str, DocRoot] = getattr(
        getattr(env, "project", None), "_doc_roots", {}
    )
    if not doc_roots:
        return
    srcdir = Path(env.srcdir)
    for docname, doc_root in doc_roots.items():
        if doc_root.path_check == "off":
            continue
        for dep in env.dependencies.get(docname, ()):
            abs_dep = (srcdir / dep).resolve()
            if _is_within_any(doc_root.roots, abs_dep):
                continue
            msg = _path_escape_message(
                docname, dep, abs_dep, doc_root.roots, doc_root.label
            )
            if doc_root.path_check == "error":
                # Log the actionable line FIRST. On Sphinx >= 8.2 every
                # ``SphinxError`` is rendered by
                # ``sphinx/_cli/util/errors.py:handle_exception``, which
                # unconditionally prints Versions / Last Messages / Loaded
                # Extensions / Traceback blocks and an invitation to open an
                # issue against Sphinx. Without this line the one sentence the
                # bundle author needs is buried inside a crash report about
                # someone else's project.
                logger.error(msg)
                # ``modname`` is what makes the header read "Extension error
                # (sphinx_mounts)" rather than a bare "Extension error", so the
                # report at least names the extension that objected. Matches
                # what ``TomlConfigError`` / ``MountConfigError`` pass.
                raise ExtensionError(msg, modname="sphinx_mounts")
            log_warning(logger, msg, "path_escape", location=docname)


def _path_escape_message(
    docname: str, dep: Any, abs_dep: Path, roots: tuple[Path, ...], label: str
) -> str:
    """Compose the ``path_check`` message for one escaping dependency.

    Both the recorded dependency and its resolved form are printed. They can
    differ in two ways that change what the author has to fix, and printing
    only the resolved path made the advice misleading in each:

    * Sphinx records the dependency as ``srcdir / rel_fn`` with the ``..``
      segments still in it, so the resolved path alone hides which directive
      argument produced it.
    * A symlink inside the bundle that points outside it is an escape even
      though the path written in the directive is plainly bundle-relative.
      Telling that author to avoid a leading ``/`` or ``..`` describes
      something they never wrote.

    ``label`` names the *mount* whose ``path_check`` fired. "The bundle root"
    on its own is ambiguous in a project with several mounts, and it is the
    mount's config block that has to change.

    A file-list mount has one root per listed file's directory, so every one
    of them is printed: the author needs to see the whole set they could move
    the file into, not just one arbitrary member of it.
    """
    if len(roots) == 1:
        where = f"which is not under {roots[0]}"
    else:
        listed = ", ".join(str(root) for root in roots)
        where = f"which is not under any of this mount's roots ({listed})"
    return (
        f"sphinx-mounts: mounted doc {docname!r} references a file outside its "
        f"bundle root, which belongs to {label}: the recorded dependency {dep} "
        f"resolves to {abs_dep}, {where}. Mounted "
        f"bundles must be self-contained — use a path relative to the bundle "
        f"root (no leading '/', and no '..' climbing above the bundle). A "
        f"symlink pointing out of the bundle counts as an escape too, even "
        f"when the path written in the directive is plainly bundle-relative. "
        f'Set path_check = "warn" or "off" on the mount to relax this check.'
    )


def _build_toctree_node(parent: str, entry: str) -> addnodes.toctree:
    """Construct a fresh ``toctree`` node with sane defaults."""
    node = addnodes.toctree()
    node["parent"] = parent
    node["entries"] = [(None, entry)]
    node["includefiles"] = [entry]
    node["maxdepth"] = -1
    node["caption"] = None
    node["glob"] = False
    node["hidden"] = False
    node["includehidden"] = False
    node["numbered"] = 0
    node["titlesonly"] = False
    return node


def _attach_to_first_section(
    doctree: nodes.document, toctree_node: addnodes.toctree
) -> None:
    """Append ``toctree_node`` at the **end** of the first top-level section.

    Position matters: the host author owns the document's content and
    ordering. Any prose, directives, or subsections they wrote come
    first; the auto-injected mount entry is placed strictly below them
    so the host doc remains self-contained and the injected references
    are always at the bottom.

    The append happens after *all* existing children of the section,
    including nested subsections. Falls back to appending directly to
    the document if it has no top-level section (e.g. a doc with only a
    paragraph at the document root).
    """
    for child in doctree.children:
        if isinstance(child, nodes.section):
            # ``Element.append`` is ``self.children.append`` — i.e. end
            # of the list, so the toctree ends up after every existing
            # child of the section.
            child.append(toctree_node)
            return
    doctree.append(toctree_node)


# ---------------------------------------------------------------------------
# `[[source.variant_sources]]` — the reader, the fold, and the attribution
# ---------------------------------------------------------------------------


def _resolve_toml_setting(app: Sphinx, config: Config) -> str | None:
    """Decide which TOML file this extension reads, honouring both confvals.

    ``sources_from_toml`` is the current name. ``mounts_from_toml`` is
    deprecated-but-honoured, following the same warn-while-honouring pattern
    the ``[[mounts]]`` -> ``[[source.mounts]]`` migration used
    (``mapping-contract.md`` §1 rule 1a): a reader that honoured only the new
    name would describe a different project from one that honoured only the
    old, and warning while still reading the old spelling is what keeps them
    agreeing during the migration.

    The rename exists because the old name became a lie the moment this file
    stopped being only about mounts — and because a project with **no mounts**
    can now install sphinx-mounts purely for variant narrowing, which should
    not require setting a confval called *mounts*``_from_toml``.

    Setting both to different values is a hard error rather than a precedence
    puzzle. Setting either to ``None`` disables **everything** this extension
    reads from TOML — mounts and variant rules alike, so the coupling is named
    rather than discovered.

    "Set" means WRITTEN, not "different from the default" — see
    :func:`_is_explicit`. Inferring it from the value produced three wrong
    answers, the worst of which read the wrong file: with
    ``sources_from_toml = "ubproject.toml"`` (the current spelling, named
    explicitly) beside ``mounts_from_toml = "other.toml"``, the deprecated key
    silently won, because writing the default value is indistinguishable from
    not writing the key. That is reachable during exactly the migration this
    pair exists for — someone adds the new key and forgets to delete the old
    line. The other two were missing warnings: both keys set to the same
    non-default value, and the old key set to the default.

    The decision is cached on the application, so the deprecation warning fires
    once per build rather than once per reader.
    """
    # Boxed in a 1-tuple so that "computed, and the answer was None" is
    # distinguishable from "not computed yet" without a sentinel type.
    cached: tuple[str | None] | None = getattr(app, _TOML_SETTING_KEY, None)
    if cached is not None:
        return cached[0]
    new_value = getattr(config, "sources_from_toml", DEFAULT_TOML_FILENAME)
    old_value = getattr(config, "mounts_from_toml", DEFAULT_TOML_FILENAME)
    new_explicit = _is_explicit(config, "sources_from_toml")
    old_explicit = _is_explicit(config, "mounts_from_toml")
    if new_explicit and old_explicit and new_value != old_value:
        msg = (
            f"sphinx-mounts: `sources_from_toml` is set to {new_value!r} and "
            f"the deprecated `mounts_from_toml` to {old_value!r}. Keep exactly "
            f"one — picking a winner would make the file this extension reads "
            f"depend on a precedence rule nobody reading conf.py can see. "
            f"`sources_from_toml` is the current spelling."
        )
        raise TomlConfigError(msg)
    setting = old_value if old_explicit and not new_explicit else new_value
    if old_explicit:
        # Fires whenever the old key is WRITTEN, including when it is written
        # beside the new one or set to the default value — those are the two
        # states the migration actually passes through, and they are exactly
        # where the nudge to delete the line is worth having.
        msg = (
            "sphinx-mounts: `mounts_from_toml` is deprecated; rename it to "
            "`sources_from_toml`. Nothing else changes — the same file is "
            "read, for the same keys. The name was renamed because this "
            "extension now also reads `[[source.variant_sources]]` out of it, "
            "and a project with no mounts at all can use that. Note that "
            "setting it to None disables everything read from the TOML file, "
            "variant rules included. Suppress with suppress_warnings = "
            '["mounts.deprecated_confval"] if you cannot migrate yet.'
        )
        log_warning(logger, msg, "deprecated_confval")
    setattr(app, _TOML_SETTING_KEY, (setting,))
    return setting


def _is_explicit(config: Config, name: str) -> bool:
    """Whether ``name`` was WRITTEN, in ``conf.py`` or on the command line.

    Sphinx carries both halves: ``config._raw_config`` is the namespace
    ``conf.py`` produced, and ``config.overrides`` is what ``-D`` supplied.
    Their union is the real question, and it is the only one that separates
    "the author named the default" from "the author said nothing" — a
    distinction the value cannot express and which decides which file is read.

    Both attributes exist across the supported range (verified on 7.4.7 and
    9.1.0). If a future Sphinx drops either, the fallback is the old
    value-based inference, which is wrong only in the corners named in
    :func:`_resolve_toml_setting` and never crashes.
    """
    raw = getattr(config, "_raw_config", None)
    overrides = getattr(config, "overrides", None)
    if raw is None and overrides is None:  # pragma: no cover - not on 7.4-9.x
        return getattr(config, name, DEFAULT_TOML_FILENAME) != DEFAULT_TOML_FILENAME
    return name in (raw or {}) or name in (overrides or {})


@dataclass(frozen=True, slots=True)
class _GatedMount:
    """A mount whose file set a variant rule narrowed, and how.

    Kept so ``builder-inited`` can walk the mount **as it would have been**
    and diff, which is the only way to learn which docnames a rule removed: an
    excluded file is pruned at the walk, so nothing downstream can tell it from
    a file that was never written. That is the property the feature wants, and
    also why the attribution has to be computed rather than inferred.
    """

    index: int
    mount_at: str | None
    dir: Path | None
    include: tuple[str, ...]
    gitignore: bool
    excludes_before: tuple[str, ...]
    excludes_after: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _VariantState:
    """What the config-time reader decided, for the build-time half to use."""

    #: ``(rule label, translated exclude_patterns)`` for every FALSE rule.
    host_patterns: tuple[tuple[str, tuple[str, ...]], ...]
    #: ``config.exclude_patterns`` as it was *before* the fold.
    base_exclude_patterns: tuple[str, ...]
    #: Every mount a rule narrowed.
    gated_mounts: tuple[_GatedMount, ...]
    #: ``(rule label, authored globs)`` for every FALSE rule, for attributing a
    #: removed mounted file back to the pattern the author can edit.
    false_rules: tuple[tuple[str, tuple[str, ...]], ...]


def _on_load_variants(app: Sphinx, config: Config) -> None:
    """Read ``[[source.variant_sources]]`` and fold its verdict into config VALUES.

    Runs at ``config-inited`` priority **450**, the only slot that satisfies
    all three constraints, every one of them measured:

    * **> 11** — sphinx-needs loads its TOML at priority 10 and (from the
      release after 8.3.1) resolves the variant map at 11, so the merged map is
      available, or provably absent and the fallback runs;
    * **> 400** — :func:`_on_load_toml` has put the raw mount tables into
      ``config.mounts``, so there is something to fold into;
    * **< 500** — :func:`_on_config_inited` has not yet parsed them into
      :class:`~sphinx_mounts.config.MountConfig` s, so the fold is invisible to
      everything downstream.

    **The verdict is folded into config VALUES, not applied later.** Host-arm
    patterns are appended to ``config.exclude_patterns``; mount-arm patterns are
    appended to each raw mount table's ``exclude`` (or filter its ``files``),
    and ``config["mounts"]`` is reassigned so the value really changes. Both
    confvals are ``rebuild="env"``, so a gating flip is a config change Sphinx
    already knows how to converge — it re-reads every document, in both
    directions, on the build where the flip happened. A reader that gated
    without touching a config value leaves both values byte-identical across a
    flip and needs an invalidation story of its own.

    Order matters and is the same order ubCode uses:

    1. the glob-dialect refusals and the layout guard, which are
       variant-**independent** — a pattern this key cannot interpret, or a
       layout no pattern can be anchored in, is unusable in every variant;
    2. the variant map;
    3. condition validation (hard) and evaluation (warn-and-exclude);
    4. the root-document guard, which is variant-**dependent** — a rule
       matching the root document is perfectly legal while its condition holds;
    5. the two folds.
    """
    setattr(app, _VARIANT_STATE_KEY, None)
    setting = _resolve_toml_setting(app, config)
    if not setting:
        return
    toml_path = (Path(app.confdir) / setting).resolve()
    spec = load_variant_sources_from_toml(toml_path)
    if spec is None or not spec.rules:
        return

    rules = _usable_rules(spec)
    if not rules:
        return
    _refuse_glob_dialects(rules, toml_path)
    _guard_layout(app, config, spec, rules)

    variant_data = _resolve_variant_map(app, config, spec)
    if variant_data is None:
        # sphinx-needs owns the failure and will report it; see
        # `_resolve_variant_map`.
        return

    excluding = _excluding_rules(rules, variant_data)
    if not excluding:
        logger.info(
            "sphinx-mounts: every `variant_sources` rule holds for this "
            "variant; the document set is unchanged."
        )
        return

    host_patterns = tuple(
        (rule.label, tuple(_translated_host_patterns(rule))) for rule in excluding
    )
    _guard_root_doc(app, config, host_patterns)

    base_exclude = tuple(config.exclude_patterns)
    appended = [pattern for _, patterns in host_patterns for pattern in patterns]
    config.exclude_patterns = [*config.exclude_patterns, *appended]
    gated = _fold_into_mounts(app, config, excluding)

    setattr(
        app,
        _VARIANT_STATE_KEY,
        _VariantState(
            host_patterns=host_patterns,
            base_exclude_patterns=base_exclude,
            gated_mounts=gated,
            false_rules=tuple((rule.label, rule.files) for rule in excluding),
        ),
    )
    logger.info(
        "sphinx-mounts: %d of %d `variant_sources` rule(s) exclude for this "
        "variant; %d exclude_patterns entr(ies) added, %d mount(s) narrowed.",
        len(excluding),
        len(rules),
        len(appended),
        len(gated),
    )


def _usable_rules(spec: VariantSourcesConfig) -> tuple[VariantRule, ...]:
    """Drop the rules that name no files, reporting each.

    An empty ``files`` list is the **one** safe drop, and the reason it is safe
    is the reason no other drop is: a rule that named nothing has nothing to
    leak, so dropping it leaves the document set unchanged rather than putting
    files back into the build.
    """
    usable: list[VariantRule] = []
    for rule in spec.rules:
        if not rule.files:
            msg = (
                f"sphinx-mounts: {rule.label} lists no files, so it gates "
                f"nothing; the rule is dropped. Give it at least one glob, or "
                f"remove it."
            )
            log_warning(logger, msg, "variant_rule_dropped")
            continue
        usable.append(rule)
    return tuple(usable)


def _refuse_glob_dialects(rules: tuple[VariantRule, ...], toml_path: Path) -> None:
    """Refuse the whole configuration if any glob has no faithful translation.

    Every offender is listed at once. Fixing one refused pattern only to meet
    the next on the following build is exactly the experience this avoids, and
    it is cheap to avoid because the check is a pure function of the text.
    """
    offenders: list[str] = []
    for rule in rules:
        for pattern in rule.files:
            reason = dialect.refuse(pattern)
            if reason is not None:
                offenders.append(f"  {rule.label}: {pattern!r} — {reason}")
    if not offenders:
        return
    listed = "\n".join(offenders)
    msg = (
        f"sphinx-mounts: {len(offenders)} `variant_sources` glob(s) in "
        f"{toml_path} cannot be interpreted the same way by every tool that "
        f"reads this file, so the configuration is refused:\n{listed}\n"
        f"This is deliberately not a warning that skips the rule: skipping a "
        f"rule leaves every file it names in the build, including the files "
        f"its other patterns name, which is the one outcome a gating key must "
        f"not have. [mounts.variant_glob_dialect]"
    )
    raise VariantRuleError(msg)


def _guard_layout(
    app: Sphinx,
    config: Config,
    spec: VariantSourcesConfig,
    rules: tuple[VariantRule, ...],
) -> None:
    """Require the rules' anchor to be Sphinx's ``srcdir``.

    A rule glob is anchored at the project's source root; an
    ``exclude_patterns`` entry is anchored at ``srcdir``. When the two coincide
    the mapping is the identity and a rule means one thing. When they do not, a
    prefix-shifted rewrite is *mechanically* possible for a path-naming pattern
    and has no correct form at all for a basename-matching one — and silently
    gating a root that happens to coincide is the failure this whole feature
    exists to prevent. So it is refused, naming both directories and both fixes.

    A source root that is also a **mount** root is not a layout problem: that
    is the mount arm's business, and it reaches it by handing the mount's own
    walker the translated pattern.

    Variant-independent, so it runs before any condition is evaluated: a layout
    no pattern can be anchored in is wrong in every variant.
    """
    srcdir = Path(app.srcdir).resolve()
    if spec.source_root == srcdir:
        return
    if spec.source_root in _raw_mount_dirs(app, config):
        return
    named = "\n".join(f"  {rule.label}" for rule in rules)
    relative = _relative_hint(srcdir, spec.toml_path.parent)
    msg = (
        f"sphinx-mounts: `{spec.toml_path}` declares "
        f"`[[source.variant_sources]]`, but the source root its globs are "
        f"anchored at ({spec.source_root}) is not Sphinx's source directory "
        f"({srcdir}), so no rule glob can be expressed as an "
        f"`exclude_patterns` entry:\n{named}\n"
        f"Two ways out. Either move `ubproject.toml` beside the source "
        f"directory, or declare that directory as the source root in the file "
        f"you already have — `[source] dir = {relative!r}` (a string, not an "
        f"array). Note that `[source] dir` is also the DISCOVERY root for the "
        f"sibling tools reading this file, so choose a value that is right for "
        f"them too: widening it to the repository root would make them index "
        f"the whole repository. Gating only a root that happens to coincide "
        f"would publish files a rule excludes, which is the failure this key "
        f"exists to prevent. [mounts.variant_layout]"
    )
    raise VariantRuleError(msg)


def _relative_hint(srcdir: Path, toml_dir: Path) -> str:
    """Render ``srcdir`` relative to the TOML's directory, for the fix advice."""
    try:
        return srcdir.relative_to(toml_dir).as_posix()
    except ValueError:
        return srcdir.as_posix()


def _raw_mount_dirs(app: Sphinx, config: Config) -> set[Path]:
    """Resolved ``dir`` of every mount currently configured.

    Anchored at ``confdir``, exactly as ``parse_mounts`` will at priority 500.
    A TOML-declared ``dir`` is already absolute by the time it gets here (the
    loader anchors it at the TOML's directory at 400), so only a
    ``conf.py``-declared relative path reaches the join — and resolving that
    one against the process's working directory instead was a live defect: it
    made the mount's attribution silently vanish while the fold still gated its
    files, so every variant build of such a project failed under ``-W``.
    """
    confdir = Path(app.confdir)
    dirs: set[Path] = set()
    for entry in getattr(config, "mounts", None) or ():
        raw = (
            entry.get("dir")
            if isinstance(entry, Mapping)
            else getattr(entry, "dir", None)
        )
        if raw:
            dirs.add(_anchor_at_confdir(raw, confdir))
    return dirs


def _anchor_at_confdir(raw: Any, confdir: Path) -> Path:
    """Absolutise a mount ``dir`` the way ``parse_mounts`` will at 500."""
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.resolve()
    return (confdir / candidate).resolve()


def _resolve_variant_map(
    app: Sphinx, config: Config, spec: VariantSourcesConfig
) -> dict[str, Any] | None:
    """Compute the merged variant map, or ``None`` to stand down.

    The read rule, in one paragraph: take ``needs_variant_data`` and
    ``needs_variant_data_file`` off the config; when the attributes are
    **absent** — sphinx-needs is not installed — fall back to the ``[needs]``
    table of the same TOML file this extension already reads. Then
    *unconditionally* deep-merge the file under the inline values. On a
    sphinx-needs that already resolved, the re-merge is a proven no-op; on
    8.3.1 and earlier it supplies the merge sphinx-needs has not performed yet;
    with sphinx-needs absent it is the whole computation. So there is no
    version gate, no import and no feature detection, and the answer always
    agrees with whatever sphinx-needs computed.

    **Two anchors, not one.** A relative ``variant_data_file`` declared in the
    TOML is absolutised against the TOML's own directory (sphinx-needs' own
    ``toml_convert`` does the same); one declared in ``conf.py`` or with ``-D``
    is absolutised against ``confdir``. Reading only one anchor means reading
    the wrong file for one of the two routes.

    Returns ``None`` when the data is unreadable **and sphinx-needs is
    present**: it will raise its own ``NeedsConfigException`` for the same
    file, so reporting here would be a second message for one problem. The
    build stops on its error, not on a fold this reader skipped.
    """
    present = hasattr(config, "needs_variant_data") or hasattr(
        config, "needs_variant_data_file"
    )
    if present:
        inline = getattr(config, "needs_variant_data", None)
        raw_file = getattr(config, "needs_variant_data_file", None)
        file_ref = _anchor_data_file(raw_file, Path(app.confdir))
    else:
        inline = spec.variant_data
        file_ref = spec.variant_data_file
    try:
        resolved = resolve_variant_data(inline, file_ref)
    except VariantDataError as exc:
        if present:
            logger.info(
                "sphinx-mounts: the variant data could not be read (%s); "
                "sphinx-needs reports this itself, so the `variant_sources` "
                "fold stands down rather than reporting it twice.",
                exc,
            )
            return None
        msg = (
            f"sphinx-mounts: the variant data could not be read, so there is "
            f"no defensible answer to which files this variant contains: "
            f"{exc}. sphinx-needs is not installed, so nothing else will "
            f"report this. [mounts.variant_data_unreadable]"
        )
        raise VariantRuleError(msg) from exc
    _guard_mispointed_needs(app, config, spec, present=present, resolved=resolved)
    return resolved


def _needs_toml_pointer(app: Sphinx, config: Config) -> Path | None:
    """Where sphinx-needs' own ``needs_from_toml`` points, resolved.

    ``None`` when the confval is unset or switched off. Relative values are
    anchored at ``confdir``, which is how sphinx-needs reads it.
    """
    pointer = getattr(config, "needs_from_toml", None)
    if not pointer or not isinstance(pointer, str):
        return None
    candidate = Path(pointer)
    if candidate.is_absolute():
        return candidate.resolve()
    return (Path(app.confdir) / candidate).resolve()


def _guard_mispointed_needs(
    app: Sphinx,
    config: Config,
    spec: VariantSourcesConfig,
    *,
    present: bool,
    resolved: dict[str, Any],
) -> None:
    """Refuse a project whose variant data is declared but never read.

    The conjunction is deliberately narrow, and every conjunct is statically
    knowable at this point: rules are declared, sphinx-needs is **present** (so
    its resolved map is what this reader must agree with), the TOML **declares**
    variant data, that map came out **empty**, and sphinx-needs' own
    ``needs_from_toml`` does **not** point at this file.

    The last conjunct is the one that makes the guard safe to fire. Without it
    the guard read "the map is empty" and refused a correctly wired project
    whose data legitimately *is* empty — an empty ``[needs.variant_data]``
    placeholder, or a base-variant ``variant_data_file`` of ``{}`` — and told
    it to apply a fix its ``conf.py`` already contained. A hard error whose
    message names no remedy is the worst shape a fail-closed refusal can take.

    It used to ride a *suppressible* ``mounts.variant_rule_unevaluable``
    warning per rule. That contradicts this key's own rule, argued in three
    other places here: for a gating key, a failure behind a diagnostic a
    project can silence is not a failure. ``suppress_warnings = ["mounts"]`` is
    itself recommended in these docs as the "quiet this extension" switch, and
    with it set the loss was completely silent.

    A project that legitimately supplies the map from ``conf.py`` or ``-D``
    cannot reach this either: its resolved map is not empty.
    """
    declares = spec.variant_data is not None or spec.variant_data_file is not None
    if not (present and declares and not resolved):
        return
    pointer = _needs_toml_pointer(app, config)
    if pointer == spec.toml_path:
        # Correctly wired, and the data is simply empty. Not this guard's
        # business — the per-rule warn-and-exclude reports it instead.
        return
    where = (
        f"sphinx-needs is reading `{pointer}` instead"
        if pointer is not None
        else "sphinx-needs was never pointed at it"
    )
    msg = (
        f"sphinx-mounts: `{spec.toml_path}` declares `[needs] variant_data` "
        f"and `[[source.variant_sources]]`, but {where}, so it resolved an "
        f"EMPTY variant map. Every rule would report an unknown key and "
        f"exclude its files, and the whole gated document set would silently "
        f"disappear.\n"
        f"Point sphinx-needs at the same file, in conf.py:\n"
        f'    needs_from_toml = "{spec.toml_path.name}"\n'
        f"This reader deliberately takes the map FROM sphinx-needs whenever it "
        f"is installed, so that the two tools cannot disagree about which "
        f"documents exist. [mounts.variant_data_unreadable]"
    )
    raise VariantRuleError(msg)


def _anchor_data_file(raw: Any, confdir: Path) -> Path | None:
    """Absolutise a ``needs_variant_data_file`` value against ``confdir``.

    A TOML-declared path arrives already absolute (sphinx-needs absolutises it
    against the TOML's directory at priority 10), so only the ``conf.py`` /
    ``-D`` route reaches the join — which is exactly the anchor sphinx-needs
    uses for it.
    """
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.resolve()
    return (confdir / candidate).resolve()


def _excluding_rules(
    rules: tuple[VariantRule, ...], variant_data: dict[str, Any]
) -> tuple[VariantRule, ...]:
    """Return the rules that are FALSE, i.e. the ones that exclude their files.

    *Every rule whose condition is false excludes its files; a file no false
    rule matches is unaffected.* Equivalently: a file is in the build unless
    some rule matching it is false, which is an AND over the conditions of all
    rules matching it. Order-independent, and rules only ever narrow.

    Two failure modes, on opposite sides of the line:

    * a condition **outside the grammar** is a hard error, listing every
      offender at once. It is statically knowable, so it is a configuration
      mistake rather than something to evaluate;
    * a condition inside the grammar that cannot be **evaluated** — an unknown
      ``var.*`` key, a type mismatch — is reported and the rule EXCLUDES. That
      is the warn-and-exclude contract the ``.. if::`` directive already has,
      and the safe direction for a key whose purpose is keeping content out.
    """
    offenders: list[str] = []
    validated: list[tuple[VariantRule, Any]] = []
    for rule in rules:
        try:
            validated.append((rule, validate(rule.condition)))
        except VariantConditionError as exc:
            offenders.append(f"  {rule.label}: {exc}")
    if offenders:
        listed = "\n".join(offenders)
        msg = (
            f"sphinx-mounts: {len(offenders)} `variant_sources` condition(s) "
            f"are outside the rule grammar, so the configuration is "
            f"refused:\n{listed}\n"
            f"A rule condition is comparisons, `in` / `not in`, `is None` / "
            f"`is not None`, `.startswith(…)` / `.endswith(…)`, `and` / `or` / "
            f"`not`, parentheses, nested `var.*` access and the literals "
            f"`True` / `False`. It must be boolean-valued and every field "
            f"reference must be rooted at `var`."
        )
        raise VariantRuleError(msg)
    excluding: list[VariantRule] = []
    for rule, tree in validated:
        try:
            holds = interpret(tree, variant_data)
        except VariantEvalError as exc:
            msg = (
                f"sphinx-mounts: {rule.label} could not be evaluated against "
                f"the variant data: {exc}. The rule's files are excluded — the "
                f"safe direction for a rule whose purpose is keeping content "
                f"out of the build."
            )
            log_warning(logger, msg, "variant_rule_unevaluable")
            holds = False
        if not holds:
            excluding.append(rule)
    return tuple(excluding)


def _translated_host_patterns(rule: VariantRule) -> list[str]:
    """Every ``exclude_patterns`` entry one FALSE rule contributes."""
    return [
        pattern
        for authored in rule.files
        for pattern in dialect.to_exclude_patterns(authored)
    ]


def _guard_root_doc(
    app: Sphinx,
    config: Config,
    host_patterns: tuple[tuple[str, tuple[str, ...]], ...],
) -> None:
    """Refuse a FALSE rule that would exclude ``root_doc``.

    Sphinx's own reaction is to abort with *"Sphinx is unable to load the
    master document … The master document must be within the source directory
    or a subdirectory of it"* — which is actively misleading for this cause:
    the document is inside the source directory, and excluded. A user reading
    it spends the next ten minutes checking paths.

    The candidate suffixes are the project's registered ones — the confval
    UNION the extension registry, see :func:`_source_suffixes` — so the
    candidate paths are the real ones, which is stronger than ubCode's guard on
    that axis (it has to infer candidate suffixes from the project's include
    globs and is best-effort in one corner). It is WEAKER on another: a root
    document provided by a *mount* is not covered here and is covered there.

    Variant-**dependent**, unlike the glob-dialect refusal: a rule matching the
    root document is perfectly legal while its condition holds, so
    ``files = ["**"]`` with a true condition is a valid "this whole tree, this
    variant only".
    """
    root_doc = getattr(config, "root_doc", "index")
    candidates = [f"{root_doc}{suffix}" for suffix in _source_suffixes(app, config)]
    for label, patterns in host_patterns:
        for pattern in patterns:
            hit = next((c for c in candidates if patmatch(c, pattern)), None)
            if hit is None:
                continue
            msg = (
                f"sphinx-mounts: {label} is false for this variant and its "
                f"pattern {pattern!r} would exclude the root document "
                f"{hit!r}. The root document is what the navigation tree and "
                f"the document ordering are built from, so a build without it "
                f"is not a smaller site — Sphinx would abort with a message "
                f"blaming the source directory. Narrow the rule's pattern, or "
                f"change `root_doc`. [mounts.variant_root_doc]"
            )
            raise VariantRuleError(msg)


def _source_suffixes(app: Sphinx, config: Config) -> tuple[str, ...]:
    """Every registered source suffix — the confval AND the registry.

    An extension adds a suffix with ``app.add_source_suffix``, which writes
    ``app.registry.source_suffix`` — a different place from the ``source_suffix``
    confval, which such a project never touches. Reading only the confval made
    the root-document guard blind to exactly the mainstream case: a MyST
    project with an ``index.md`` root document. The guard then tested
    ``patmatch('index.rst', 'index.md')``, passed the rule, folded the pattern
    in, and the user met Sphinx's abort — naming ``index.rst``, a file that
    does not exist, which is worse than the misleading message the guard exists
    to prevent.

    The registry is fully populated at ``config-inited``: every extension's
    ``setup()`` has already run.

    Sphinx normalises the confval to a mapping in a ``config-inited`` handler
    at priority **800**, which is after this reader, so the value may still be
    the string or list the user wrote.
    """
    raw = getattr(config, "source_suffix", None)
    if isinstance(raw, str):
        from_confval: tuple[str, ...] = (raw,)
    elif isinstance(raw, Mapping):
        from_confval = tuple(raw)
    elif isinstance(raw, list | tuple):
        from_confval = tuple(str(item) for item in raw)
    else:
        from_confval = (".rst",)
    registered = tuple(getattr(app.registry, "source_suffix", ()) or ())
    return tuple(dict.fromkeys((*from_confval, *registered)))


def _fold_into_mounts(
    app: Sphinx, config: Config, excluding: tuple[VariantRule, ...]
) -> tuple[_GatedMount, ...]:
    """Fold the FALSE rules into the mount tables, then reassign the value.

    Two code paths for two mount modes, as everywhere else in this extension:

    * **directory mode** appends the gitignore translation to the entry's
      ``exclude``. That list is already a last-match-wins override list, and
      every ``include`` is added before every ``exclude``, so an appended
      variant exclude beats any user ``include`` — which is exactly the
      "rules only narrow" semantics wanted.
    * **file-list mode is NOT gated at all**, and that is parity rather than a
      gap. ubCode cannot gate one either: a ``files`` mount's entries are
      pushed straight into its result with no include or exclude consulted, and
      a variant rule reaches its discovery only through ``extend_exclude``, so
      **no rule can remove a file-list mount's document under any spelling
      there** (``rust/ubc_config/src/resolved.rs``). Gating one here — by
      basename, which is what this reader used to do — was a divergence in the
      removes-more-here direction, and it is the one thing this key must never
      be: two readers, two document sets, from one rule string. Use a directory
      mount for a bundle that has to be gateable.

    ``config["mounts"]`` is reassigned at the end even though the entries were
    mutated in place, because it is the config *value* changing that makes a
    gating flip a ``[config changed ('mounts')]`` rebuild.
    """
    raw = getattr(config, "mounts", None)
    if not raw:
        return ()
    confdir = Path(app.confdir)
    gated: list[_GatedMount] = []
    folded: list[Any] = []
    for index, entry in enumerate(raw):
        if isinstance(entry, Mapping):
            new_entry, record = _fold_into_mount_entry(
                dict(entry), index, excluding, confdir
            )
        elif isinstance(entry, MountConfig):
            new_entry, record = _fold_into_mount_config(
                entry, index, excluding, confdir
            )
        else:
            new_entry, record = entry, None
        folded.append(new_entry)
        if record is not None:
            gated.append(record)
    config["mounts"] = folded
    return tuple(gated)


def _fold_into_mount_entry(
    entry: dict[str, Any],
    index: int,
    excluding: tuple[VariantRule, ...],
    confdir: Path,
) -> tuple[dict[str, Any], _GatedMount | None]:
    """Fold into one raw TOML mount table."""
    mount_at = entry.get("mount_at")
    mount_at = mount_at.strip("/") if isinstance(mount_at, str) else None
    if "dir" in entry:
        before = tuple(entry.get("exclude") or ())
        added = [
            dialect.to_gitignore(pattern)
            for rule in excluding
            for pattern in rule.files
        ]
        entry["exclude"] = [*before, *added]
        return entry, _GatedMount(
            index=index,
            mount_at=mount_at,
            dir=(
                _anchor_at_confdir(entry["dir"], confdir)
                if isinstance(entry["dir"], str)
                else None
            ),
            include=tuple(entry.get("include") or ()),
            gitignore=bool(entry.get("gitignore", True)),
            excludes_before=before,
            excludes_after=tuple(entry["exclude"]),
        )
    # A file-list mount is left completely alone; see `_fold_into_mounts`.
    return entry, None


def _fold_into_mount_config(
    mount: MountConfig,
    index: int,
    excluding: tuple[VariantRule, ...],
    confdir: Path,
) -> tuple[MountConfig, _GatedMount | None]:
    """Fold into a ``conf.py``-declared :class:`MountConfig`.

    The legacy path carries dataclass instances rather than tables, so the fold
    replaces the instance instead of mutating a dict. Same two modes, same
    semantics — a variant rule must not mean one thing in TOML and another in
    ``conf.py``.
    """
    if mount.dir is not None:
        added = tuple(
            dialect.to_gitignore(pattern)
            for rule in excluding
            for pattern in rule.files
        )
        updated = replace(mount, exclude=(*mount.exclude, *added))
        return updated, _GatedMount(
            index=index,
            mount_at=mount.mount_at,
            dir=_anchor_at_confdir(mount.dir, confdir),
            include=mount.include,
            gitignore=mount.gitignore,
            excludes_before=mount.exclude,
            excludes_after=updated.exclude,
        )
    # A file-list mount is left completely alone; see `_fold_into_mounts`.
    return mount, None


# ---------------------------------------------------------------------------
# Attribution: which docnames the rules removed, and which rule removed each
# ---------------------------------------------------------------------------


def _on_install_variant_filter(app: Sphinx, _env: Any, _docnames: list[str]) -> None:
    """Work out what the rules removed, and hook the toctree downgrade.

    Runs at ``env-before-read-docs``, which fires **once per build** — after
    ``app.builder`` and ``app.project`` exist (the docname derivation needs the
    builder's asset paths and the project's registered source suffixes) and
    before any document is read, so before any toctree warning can be emitted.

    Per BUILD, not per application, and that distinction is the whole point.
    ``builder-inited`` fires once per *construction*, so an application built
    twice through the public ``Sphinx.build()`` API — which exists precisely
    for that — installed on its first build and ran its second unfiltered: a
    correctly configured variant project emitted its variant-excluded toctree
    warning un-downgraded and failed ``-W`` on rebuild. The module's own rule
    is "whoever starts a build owns the loggers until it finishes"; this is
    where that sentence is implemented.

    **This is the one new IO**, and it is bounded: one extra pass over the
    source directory plus one per narrowed mount, only for a project that
    declares rules *and* has at least one false rule. It is needed because an
    excluded file is pruned at the walk, so nothing downstream can tell it from
    a file that was never written — which is the property the feature wants,
    and also why the downgrade has to be *told* which documents a variant
    removed rather than inferring it.

    The result is **reused** across builds of one application rather than
    recomputed. That is safe because the attribution is a pure function of the
    fold's state, and the fold runs at ``config-inited``: a second
    ``app.build()`` in the same process cannot have re-read ``conf.py`` or the
    TOML, so the state object is identical and so is the answer. A changed
    configuration means a new application, which means a new state object,
    which the identity check below notices.
    """
    state: _VariantState | None = getattr(app, _VARIANT_STATE_KEY, None)
    if state is None:
        mount_warnings.remove_downgrade_filters()
        return
    cached = getattr(app, _VARIANT_ATTRIBUTION_KEY, None)
    if cached is not None and cached[0] is state:
        excluded = cached[1]
    else:
        suffixes = tuple(app.project.source_suffix)
        excluded = _host_excluded_docnames(app, state, suffixes)
        excluded.update(_mount_excluded_docnames(state, suffixes))
        setattr(app, _VARIANT_ATTRIBUTION_KEY, (state, excluded))
    if not excluded:
        mount_warnings.remove_downgrade_filters()
        return
    _, names, degraded = mount_warnings.install_downgrade_filter(excluded, app)
    if degraded:
        msg = (
            f"sphinx-mounts: could not resolve the emitting toctree logger(s) "
            f"from Sphinx's own modules and fell back to the hard-coded "
            f"name(s) {list(degraded)}. Variant-excluded toctree references "
            f"may still be reported as warnings on this Sphinx version. This "
            f"is a compatibility problem in sphinx-mounts, not in your project."
        )
        logger.warning(msg)
    logger.info(
        "sphinx-mounts: %d document(s) excluded by variant rules; toctree "
        "references to them are downgraded on %r.",
        len(excluded),
        list(names),
    )


def _on_remove_variant_filter(_app: Sphinx, _exception: Exception | None) -> None:
    """Detach the downgrade filter when this build ends.

    Every filter comes off, not only this application's — the loggers are
    process-global and a build is what owns them; see
    :func:`sphinx_mounts.warnings.remove_downgrade_filters`.
    """
    mount_warnings.remove_downgrade_filters()


def _host_excluded_docnames(
    app: Sphinx, state: _VariantState, suffixes: tuple[str, ...]
) -> dict[str, str]:
    """Docnames the host arm removed, each mapped to the rule that removed it.

    A diff of two passes over ``get_matching_files`` — the same function
    ``Project.discover`` goes through — with the SAME inputs and the SAME
    post-filters ``discover`` applies. Going through the same function with
    different arguments is not the same thing, and each of the three
    differences below invented docnames that were never documents:

    * ``BuildEnvironment.find_files`` passes
      ``exclude_patterns + templates_path + builder.get_asset_paths()``.
      Omitting the third put every source file under ``html_extra_path`` /
      ``html_static_path`` into the "before" set, so gating one of them made a
      phantom docname — and a phantom is enough to downgrade a **genuine**
      toctree warning and stop ``-W`` from failing. That is the one thing the
      downgrade is not allowed to do.
    * ``discover`` skips a file it cannot read (``os.access(.., R_OK)``), so an
      unreadable gated file was a phantom too.
    * ``discover`` keeps the FIRST file that claims a docname and warns about
      the rest, so a docname is only excluded when NO surviving file still
      provides it. Diffing file names instead meant that gating ``a.md``
      beside a surviving ``a.rst`` marked the live docname ``a`` excluded, and
      every toctree reference to it was silently downgraded — a fail-open in
      the other direction.

    Running at ``builder-inited`` is what makes the first of those available:
    ``app.builder`` does not exist at ``config-inited``.
    """
    srcdir = Path(app.srcdir)
    base = [
        *state.base_exclude_patterns,
        *app.config.templates_path,
        *_asset_paths(app),
        *EXCLUDE_PATHS,
    ]
    variant = [pattern for _, patterns in state.host_patterns for pattern in patterns]
    include = app.config.include_patterns
    before = _docname_providers(srcdir, include, base, suffixes)
    after = _docname_providers(srcdir, include, [*base, *variant], suffixes)
    excluded: dict[str, str] = {}
    for docname, files in sorted(before.items()):
        if after.get(docname):
            # Some other file still provides this docname, so the document is
            # very much alive and a reference to it is not variant-excluded.
            continue
        label = next(
            (
                label
                for label, patterns in state.host_patterns
                for relative in files
                if any(patmatch(relative, pattern) for pattern in patterns)
            ),
            state.host_patterns[0][0],
        )
        excluded[docname] = label
    return excluded


def _asset_paths(app: Sphinx) -> list[str]:
    """The builder's own excluded asset paths, or nothing if it has none."""
    builder = getattr(app, "builder", None)
    get_asset_paths = getattr(builder, "get_asset_paths", None)
    if get_asset_paths is None:  # pragma: no cover - every builder has one
        return []
    return list(get_asset_paths())


def _docname_providers(
    srcdir: Path,
    include: list[str],
    exclude: list[str],
    suffixes: tuple[str, ...],
) -> dict[str, list[str]]:
    """Map each docname to the source files that would provide it.

    Mirrors ``Project.discover``: only readable files count, and a docname may
    have several providers (Sphinx keeps the first and warns about the rest).
    """
    providers: dict[str, list[str]] = {}
    for relative in get_matching_files(srcdir, include, exclude):
        docname = _docname_for(relative, suffixes)
        if docname is None:
            continue
        if not os.access(srcdir / relative, os.R_OK):
            continue
        providers.setdefault(docname, []).append(relative)
    return providers


def _mount_excluded_docnames(
    state: _VariantState, suffixes: tuple[str, ...]
) -> dict[str, str]:
    """Docnames the mount arm removed, each mapped to the rule that removed it.

    Directory mounts only: a file-list mount is never narrowed by a rule (see
    :func:`_fold_into_mounts`), so it has nothing to attribute.
    """
    excluded: dict[str, str] = {}
    for gated in state.gated_mounts:
        if gated.dir is None or not gated.dir.is_dir():
            continue
        before = _walked_relatives(gated, gated.excludes_before)
        after = _walked_relatives(gated, gated.excludes_after)
        for relative in sorted(before - after):
            docname = _docname_for(relative, suffixes)
            if docname is None:
                continue
            label = next(
                (
                    label
                    for label, authored in state.false_rules
                    if any(dialect.matches(p, relative) for p in authored)
                ),
                state.false_rules[0][0],
            )
            excluded[_join_mount(gated.mount_at, docname)] = label
    return excluded


def _walked_relatives(gated: _GatedMount, excludes: tuple[str, ...]) -> set[str]:
    """Mount-relative POSIX paths one walk configuration produces."""
    assert gated.dir is not None  # noqa: S101 - guarded by the caller
    walker = _build_walker(
        gated.dir,
        include=gated.include,
        exclude=excludes,
        gitignore=gated.gitignore,
    )
    return {
        entry.path().relative_to(gated.dir).as_posix()
        for entry in walker
        if entry.path().is_file()
    }


def _docname_for(relative: str, suffixes: tuple[str, ...]) -> str | None:
    """Strip the first matching registered suffix, as Sphinx core does.

    NFC-normalised, because Sphinx's ``found_docs`` is: ``Project.discover``
    runs every docname through ``path_stabilize``. The attribution diff's own
    inputs are NOT reliably NFC — on Linux ``get_matching_files`` yields the
    filename's literal bytes, so an NFD-named file (the form macOS filesystems
    hand out, and what a checkout made there can carry) keys the attribution
    set in NFD while the toctree warning's docname is NFC, and the downgrade
    silently misses. CI on Linux caught exactly that; the macOS measurement
    alone had suggested the normalisation came for free.
    """
    suffix = _match_suffix(relative, suffixes)
    if suffix is None or len(suffix) >= len(relative):
        return None
    return unicodedata.normalize("NFC", relative[: -len(suffix)])


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the extension with Sphinx."""
    app.add_config_value("mounts", default=[], rebuild="env", types=(list,))
    app.add_config_value(
        "sources_from_toml",
        default=DEFAULT_TOML_FILENAME,
        rebuild="env",
        types=(str, type(None)),
    )
    # Deprecated spelling of the value above, still honoured. See
    # ``_resolve_toml_setting`` for the precedence rule and for why the rename
    # happened at all.
    app.add_config_value(
        "mounts_from_toml",
        default=DEFAULT_TOML_FILENAME,
        rebuild="env",
        types=(str, type(None)),
    )
    # Priority is "lower = earlier"; the TOML loader must run before the
    # validator so that the TOML-derived list is what gets validated.
    app.connect("config-inited", _on_load_toml, priority=400)
    # 450 is the only slot that is after sphinx-needs' variant resolution (11),
    # after the mount tables are loaded (400) and before they are parsed (500).
    # See ``_on_load_variants``.
    app.connect("config-inited", _on_load_variants, priority=450)
    app.connect("config-inited", _on_config_inited, priority=500)
    app.connect("builder-inited", _on_builder_inited)
    # After ``_on_builder_inited``, because the docname derivation reads the
    # project's registered source suffixes.
    # Per BUILD, not per construction: `Sphinx.build()` may be called more
    # than once on one application, and each of those builds needs the filter.
    # `env-before-read-docs` fires every build, after the builder exists and
    # before any document is read.
    app.connect("env-before-read-docs", _on_install_variant_filter)
    # The emitting loggers are process-global and this application is not, so
    # the filter comes off when the build ends. Without it, the NEXT build in
    # the same process — sphinx-autobuild, a multi-project script, a test
    # harness — has its own genuine toctree warnings silenced and attributed
    # to a rule in a different project, with `_warncount` one lower.
    app.connect("build-finished", _on_remove_variant_filter)
    # Must run before the read phase: it is what makes an ``attach_to`` host
    # doc be re-read when a mount's set of wired entries changed, which is
    # the only way ``_on_doctree_read`` gets a chance to fix the wiring.
    app.connect("env-get-outdated", _on_env_get_outdated)
    # ``doctree-read`` priority 400 (< 500) places our toctree
    # mutation *before* Sphinx's TocTreeCollector.process_doc, so the
    # collector's pass sees the injected entries and includes them in
    # ``env.included`` — without that, Sphinx's ``toc.not_included``
    # consistency check would flag every mounted entry doc.
    app.connect("doctree-read", _on_doctree_read, priority=400)
    app.connect("env-check-consistency", _on_check_consistency)
    app.connect("env-check-consistency", _on_check_path_confinement)

    return {
        "version": __version__,
        # This extension contributes to the pickled build environment, so it
        # must declare a version Sphinx can fold into ``env.version``:
        #
        # * ``env.project`` is an instance of our own ``_MountAwareProject``
        #   subclass, so the class reference is in ``environment.pickle`` and
        #   restoring the cache imports it by name;
        # * ``env-get-outdated`` persists the toctree-wiring signature as an
        #   env attribute (``_WIRING_SIGNATURE_ATTR``).
        #
        # Sphinx sums every extension's ``env_version`` into the value
        # ``BuildEnvironment.setup`` compares, so bumping this makes stale
        # ``.doctrees`` caches start a fresh env instead of being restored
        # into a shape their writer never produced. Bump it whenever what
        # this extension puts into the env changes — the pickled shape of
        # ``_MountAwareProject`` (see its ``__getstate__``) or the layout of
        # the wiring signature.
        #
        # 1 -> 2: the `[[source.variant_sources]]` reader changes **which
        # docnames the project produces**, so an environment written before it
        # existed describes a document set this version would not have built.
        # A stale `.doctrees` cache must start fresh rather than be restored
        # into a shape its writer never produced, which is why this is a
        # version bump and not just a config change: the config *values* do
        # converge on their own (both are `rebuild="env"`), but only for a
        # cache that already knows about the reader.
        "env_version": 2,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
