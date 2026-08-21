"""Sphinx extension entry point for sphinx-mounts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docutils import nodes
from sphinx import addnodes
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.errors import ExtensionError
from sphinx.util import logging

from sphinx_mounts import __version__
from sphinx_mounts.config import (
    MountConfig,
    load_mounts_from_toml,
    mount_label,
    parse_mounts,
)
from sphinx_mounts.logging import log_warning
from sphinx_mounts.mounter import (
    DocRoot,
    _is_within_any,
    _MountAwareProject,
    install_mount_aware_project,
)

logger = logging.getLogger(__name__)

_CACHED_KEY = "_sphinx_mounts_parsed"

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
    toml_setting = getattr(config, "mounts_from_toml", None)
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


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the extension with Sphinx."""
    app.add_config_value("mounts", default=[], rebuild="env", types=(list,))
    app.add_config_value(
        "mounts_from_toml",
        default=DEFAULT_TOML_FILENAME,
        rebuild="env",
        types=(str, type(None)),
    )
    # Priority is "lower = earlier"; the TOML loader must run before the
    # validator so that the TOML-derived list is what gets validated.
    app.connect("config-inited", _on_load_toml, priority=400)
    app.connect("config-inited", _on_config_inited, priority=500)
    app.connect("builder-inited", _on_builder_inited)
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
        "env_version": 1,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
