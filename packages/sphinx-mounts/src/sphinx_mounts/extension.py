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
from sphinx_mounts.config import MountConfig, load_mounts_from_toml, parse_mounts
from sphinx_mounts.mounter import _MountAwareProject, install_mount_aware_project

logger = logging.getLogger(__name__)

_CACHED_KEY = "_sphinx_mounts_parsed"

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
    ``mounts_from_toml`` resolves to an existing file, its top-level
    ``[[mounts]]`` array replaces any value of ``mounts`` set in
    ``conf.py``. If the file does not exist, ``config.mounts`` is left
    untouched and any legacy conf.py-style value is used instead.
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
    and append ``{mount_at}/{entry_doc}`` to it. If the host doc contains
    no toctree at all, a new one is added beneath the first section. If
    ``toctree_index`` exceeds the number of toctrees in the doc, raise
    :class:`ExtensionError` — silent misconfiguration would leave the
    mount unreferenced.
    """
    parsed: tuple[MountConfig, ...] = getattr(app, _CACHED_KEY, ())
    if not parsed:
        return
    docname = app.env.docname
    targets = [m for m in parsed if m.attach_to == docname]
    if not targets:
        return

    toctrees: list[addnodes.toctree] = list(doctree.findall(addnodes.toctree))

    for mount in targets:
        entry_docname = (
            mount.entry_doc
            if mount.mount_at is None
            else f"{mount.mount_at}/{mount.entry_doc}"
        )

        if not toctrees:
            new_node = _build_toctree_node(docname, entry_docname)
            _attach_to_first_section(doctree, new_node)
            toctrees.append(new_node)
            logger.info(
                "sphinx-mounts: added toctree to %r referencing %r",
                docname,
                entry_docname,
            )
            continue

        if mount.toctree_index >= len(toctrees):
            mount_label = "<root>" if mount.mount_at is None else repr(mount.mount_at)
            msg = (
                f"sphinx-mounts: mount {mount_label} requested "
                f"toctree_index={mount.toctree_index} in host doc "
                f"{docname!r}, but only {len(toctrees)} toctree(s) exist."
            )
            raise ExtensionError(msg)

        target = toctrees[mount.toctree_index]
        if entry_docname in target["includefiles"]:
            # Already referenced (e.g. the host author wrote the entry by
            # hand). Skip silently so attach_to is idempotent next to a
            # static toctree.
            continue
        target["entries"].append((None, entry_docname))
        target["includefiles"].append(entry_docname)
        logger.info(
            "sphinx-mounts: extended toctree #%d in %r with %r",
            mount.toctree_index,
            docname,
            entry_docname,
        )


def _on_check_consistency(app: Sphinx, env: Any) -> None:
    """Warn when ``attach_to`` targets a docname that does not exist."""
    parsed: tuple[MountConfig, ...] = getattr(app, _CACHED_KEY, ())
    if not parsed:
        return
    found = set(env.found_docs)
    for mount in parsed:
        if mount.attach_to is None:
            continue
        if mount.attach_to not in found:
            mount_label = "<root>" if mount.mount_at is None else repr(mount.mount_at)
            logger.warning(
                "sphinx-mounts: mount %s has attach_to=%r, but that "
                "docname does not exist in the project — nothing was "
                "extended.",
                mount_label,
                mount.attach_to,
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
    # ``doctree-read`` priority 400 (< 500) places our toctree
    # mutation *before* Sphinx's TocTreeCollector.process_doc, so the
    # collector's pass sees the injected entries and includes them in
    # ``env.included`` — without that, Sphinx's ``toc.not_included``
    # consistency check would flag every mounted entry doc.
    app.connect("doctree-read", _on_doctree_read, priority=400)
    app.connect("env-check-consistency", _on_check_consistency)

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
