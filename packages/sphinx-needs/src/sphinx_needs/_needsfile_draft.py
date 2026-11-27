"""The draft needs.json format ``"2a2"``: its writer (**experimental**).

A project opts in with ``needs_json_format_version = "2a2"``; the ``needs`` builder,
``needs_build_json`` and the per-id builder then write a draft document where they wrote
a v1 one. ``"2a2"`` replaces the draft ``"2a1"``, which is neither written nor read any
more. :class:`~sphinx_needs.needsfile.NeedsList`, the v1 writer, is not changed: the
bytes it writes (which the ``hash`` derive kind reads) stay what they were.

A document is ``{format_version, project: {name, version}, creator: {program, version},
created?, needs: [record, ...]}``, and has no ``versions``: a reader that takes a
``versions`` envelope for v1 would read a draft file that kept one as v1, silently. A
record is ``{id, type, fields, links, content, parts?, source}``:

- ``fields``: the authored core fields and every field the need's type declares whose
  value is not ``null``, a default and a typed empty (``[]``, ``""``) included: the
  reading project's default may differ, and a draft file carries no schema to restore an
  omitted value from. A field whose value is ``null`` is left out, which a reader reads
  as unset (its own default applies, as to a ``null``); a field another need type
  declares alone is left out too;
- ``links``: each link type the need's type declares, a list of a bare id, or of
  ``{id, part?, condition?}`` where a part or a condition is given; no back links;
- ``content``: ``{text, doctype}``;
- ``parts``: where the need has parts, a list of ``{id, text}``, in the order the need
  holds them (the parts its content marks in the order written, then the parts it
  states -- its record's, or those it was given -- in the order given): the record's,
  not the content's, so excluding ``content`` keeps it;
- ``source``: the need's hops, innermost first -- those it was read with from another
  project's draft file (its ``upstream``, their origins filled), then this build's -- each
  as :class:`~sphinx_needs._need_source.NeedSourceHop` holds it, with ``None`` left out
  (an absent ``origin`` is the writing project).

The keys are written in that order and the records in the order of their ids (as v1's
``sort_keys`` orders them), compact as v1 is. The draft contract is the
ub-needs-exchange package's ``design/v2a2-draft.md``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import datetime
from typing import Any, Final, Literal

from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.environment import BuildEnvironment

from sphinx_needs._need_source import NeedSourceHop
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields, SphinxNeedsData
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedItemSource, NeedLink

LOGGER = get_logger(__name__)

FORMAT_DRAFT: Final = "2a2"
"""The draft's ``format_version``."""

REPLACED_DRAFT: Final = "2a1"
"""The draft :data:`FORMAT_DRAFT` replaces. As a value of ``needs_json_format_version``
it is an unknown one, whose warning names its successor."""

READ_DRAFTS: Final = (FORMAT_DRAFT,)
"""The drafts ``needimport`` and external needs read (``select_version``'s ``drafts``),
whatever ``needs_json_format_version`` says: reading one is harmless, writing one is the
option's."""

_RENDERING: Final = frozenset({"template", "pre_template", "post_template"})
"""Authored core fields that are rendering instructions: the written text is already
rendered, so a draft record leaves them out."""

AUTHORED_CORE: Final = tuple(
    name
    for name, params in NeedsCoreFields.items()
    if params.get("add_to_field_schema") and name not in _RENDERING
)
"""The core fields a draft record carries in ``fields``: the ones a need's author sets."""

LEGACY_LOCATION_KEYS: Final = (
    "docname",
    "lineno",
    "sections",
    "section_name",
    "signature",
    "external_url",
    "is_import",
    "is_external",
)
"""The v1 keys whose values the hops carry in the draft, so that excluding one of them
leaves nothing out of a draft file (``source`` does)."""


def _configured(needs_config: NeedsSphinxConfig) -> object:
    """``needs_json_format_version`` as both readers below take it: the text ``"1"``
    is format ``1`` (a ``-D`` value is always text), anything else is as it was set."""
    value = needs_config.json_format_version
    return 1 if isinstance(value, str) and value == "1" else value


def json_format_version(needs_config: NeedsSphinxConfig) -> Literal[1, "2a2"]:
    """The format the needs builders write: ``"2a2"`` where the project asks for it,
    else 1 (an unknown value is reported at ``config-inited``,
    :func:`check_json_format_config`)."""
    value = _configured(needs_config)
    return FORMAT_DRAFT if isinstance(value, str) and value == FORMAT_DRAFT else 1


def _known(value: object) -> bool:
    return (type(value) is int and value == 1) or (
        isinstance(value, str) and value == FORMAT_DRAFT
    )


def check_json_format_config(needs_config: NeedsSphinxConfig) -> None:
    """Report an unknown ``needs_json_format_version`` (written as 1), at
    ``config-inited``: the draft :data:`FORMAT_DRAFT` replaced too, naming its
    successor. What the experimental draft does is reported where a draft file is
    written (:func:`warn_on_write`), so that a build that writes none is not warned."""
    value = needs_config.json_format_version
    if not _known(configured := _configured(needs_config)):
        replaced = isinstance(configured, str) and configured == REPLACED_DRAFT
        log_warning(
            LOGGER,
            f"needs_json_format_version must be 1 or {FORMAT_DRAFT!r}, not {value!r}"
            + (
                f': the draft "{REPLACED_DRAFT}" is replaced by "{FORMAT_DRAFT}", '
                "which this release writes"
                if replaced
                else ""
            )
            + "; writing format version 1",
            "config",
            None,
        )


_WARNED: Final = "_sphinx_needs_draft_warned"
"""The attribute of the ``Sphinx`` application that says its build has said what a draft
file is (never of the environment, which is pickled)."""


def warn_on_write(app: Sphinx, env: BuildEnvironment) -> None:
    """Say, once per build (per application), what writing a draft file means: that the
    format is experimental, and each v1 option it does not obey. Called by each writer
    of a draft file, the ``needs`` and the per-id builder alike."""
    if getattr(app, _WARNED, False):
        return
    setattr(app, _WARNED, True)
    needs_config = NeedsSphinxConfig(env.config)
    log_warning(
        LOGGER,
        f'needs.json format "{FORMAT_DRAFT}" is experimental: a file written in it may '
        "not be readable by the next release of sphinx-needs",
        "beta",
        None,
    )
    under = f'under needs_json_format_version "{FORMAT_DRAFT}"'
    if needs_config.json_remove_defaults:
        log_warning(
            LOGGER,
            f"needs_json_remove_defaults is ignored {under}: a {FORMAT_DRAFT} file "
            "writes every default, and carries no schema to restore one from",
            "config",
            None,
        )
    if needs_config.file:
        log_warning(
            LOGGER,
            f"needs_file is ignored {under}: a {FORMAT_DRAFT} file has no versions "
            "to accumulate",
            "config",
            None,
        )
    excluded = set(needs_config.json_exclude_fields)
    if legacy := [name for name in LEGACY_LOCATION_KEYS if name in excluded]:
        names = ", ".join(repr(name) for name in legacy)
        log_warning(
            LOGGER,
            f"needs_json_exclude_fields names {names}, which have no key {under}: "
            "they are read from the need's source; exclude 'source' to leave the "
            "source out",
            "config",
            None,
        )
    if "source" in excluded and (
        SphinxNeedsData(env).get_schema().get_any_field("source") is not None
    ):
        log_warning(
            LOGGER,
            "needs_json_exclude_fields names 'source', which is both a field of the "
            f"project and, {under}, the need's source: both are left out",
            "config",
            None,
        )


def _project_name_placeholder() -> str | None:
    """Sphinx's default of ``project``, which names no project."""
    option = Config.config_values.get("project")
    default = getattr(option, "default", None)
    if default is None and isinstance(option, tuple):
        # Sphinx 7: a plain tuple, the default first
        default = option[0]
    return default if isinstance(default, str) else None


def hop_to_json(hop: NeedSourceHop, /) -> dict[str, Any]:
    """A hop as a draft record writes it: its fields in their order, ``None`` left out,
    a semantic entry's ``extras`` an object (left out where it has none)."""
    out: dict[str, Any] = {"kind": hop.kind}
    if hop.origin is not None:
        out["origin"] = hop.origin
    if (physical := hop.physical) is not None:
        out["physical"] = {
            key: value
            for key, value in (
                ("root", physical.root),
                ("path", physical.path),
                ("url", physical.url),
                ("start_line", physical.start_line),
                ("end_line", physical.end_line),
            )
            if value is not None
        }
    if hop.semantic is not None:
        out["semantic"] = [
            {
                "kind": entry.kind,
                "name": entry.name,
                **({"extras": dict(entry.extras)} if entry.extras else {}),
            }
            for entry in hop.semantic
        ]
    if hop.document is not None:
        out["document"] = hop.document
    if hop.language is not None:
        out["language"] = hop.language
    return out


def _link_to_json(link: NeedLink, /, *, conditions: bool) -> str | dict[str, str]:
    """A link: its bare id, or ``{id, part?, condition?}`` -- the empty part, which no
    need can have, kept as the dead link it is (``{"id": "B", "part": ""}``)."""
    condition = link.condition if conditions else None
    if link.part is None and condition is None:
        return link.id
    out = {"id": link.id}
    if link.part is not None:
        out["part"] = link.part
    if condition is not None:
        out["condition"] = condition
    return out


def source_hops(need: NeedItem, /) -> tuple[NeedSourceHop, ...]:
    """The hops a draft record writes for ``need``, innermost first: the ``upstream`` hops
    it was read with, as it holds them (their origins filled on read), then this
    build's; none for a source that is not a
    :class:`~sphinx_needs.need_item.NeedItemSource` (a third party's, which obeys
    :class:`~sphinx_needs.need_item.NeedItemSourceProtocol` alone: its record has no
    placement, so a reader gets no ``docname`` for it)."""
    source = need.source
    if not isinstance(source, NeedItemSource):
        return ()
    return (*source.upstream, *source.hops)


class NeedsFileDraft:
    """The records and the envelope of a draft document, for one build's configuration."""

    def __init__(self, env: BuildEnvironment) -> None:
        self._config = env.config
        self._needs_config = NeedsSphinxConfig(env.config)
        self._schema = SphinxNeedsData(env).get_schema()
        self._exclude = frozenset(self._needs_config.json_exclude_fields)
        self._conditions = self._needs_config.json_include_link_conditions

    def record(self, need: NeedItem, /) -> dict[str, Any]:
        """The draft record of ``need``."""
        exclude = self._exclude
        declared = self._schema.for_type(need["type"])
        # a null value is left out: a reader reads a missing field as unset
        fields: dict[str, Any] = {
            name: value
            for name in AUTHORED_CORE
            if name not in exclude and (value := need[name]) is not None
        }
        fields.update(
            (name, value)
            for name, value in need.iter_extra_items()
            if name not in exclude and declared.declares(name) and value is not None
        )
        links = {
            name: [_link_to_json(link, conditions=self._conditions) for link in items]
            for name, items in need.iter_links_items(as_str=False)
            if name not in exclude and declared.declares(name)
        }
        record: dict[str, Any] = {
            "id": need["id"],
            "type": need["type"],
            "fields": fields,
            "links": links,
        }
        if "content" not in exclude:
            content: dict[str, Any] = {"text": need["content"]}
            if "doctype" not in exclude:
                content["doctype"] = need["doctype"]
            record["content"] = content
        # the record's, not the content's: in the order the need holds them, unsorted
        if "parts" not in exclude and (parts := list(need.parts)):
            record["parts"] = [{"id": part.id, "text": part.content} for part in parts]
        if "source" not in exclude:
            record["source"] = [hop_to_json(hop) for hop in source_hops(need)]
        return record

    def document(self, needs: Iterable[NeedItem], /) -> dict[str, Any]:
        """The draft document of ``needs``, its records in the order of their ids."""
        from sphinx_needs import __version__

        # a project left unnamed writes no name: Sphinx's placeholder would name every
        # such project alike, where a reader names the file instead
        name = self._config.project
        project = (
            {"version": self._config.version}
            if not isinstance(name, str) or name == _project_name_placeholder()
            else {"name": name, "version": self._config.version}
        )
        document: dict[str, Any] = {
            "format_version": FORMAT_DRAFT,
            "project": project,
            "creator": {"program": "sphinx_needs", "version": __version__},
        }
        if not self._needs_config.reproducible_json:
            document["created"] = datetime.now().isoformat()
        document["needs"] = [
            self.record(need) for need in sorted(needs, key=lambda need: need["id"])
        ]
        return document

    def write(self, needs: Iterable[NeedItem], path: str | os.PathLike[str], /) -> None:
        """Write the draft document of ``needs`` to ``path``."""
        with open(path, "w") as file:
            json.dump(self.document(needs), file)
