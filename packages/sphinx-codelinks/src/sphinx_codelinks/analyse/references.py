"""The references of ``@need-ids:`` markers as plain, JSON-serialisable records.

A :class:`NeedIdRef` is one reference from a located piece of source code to one need id.
It is the exchange seam between finding references and attaching them: the ``src-trace``
directive produces records from its analysis today, and a pre-analysed input file may
produce the same records later -- whatever consumes them (the build's attach, see
``sphinx_extension/need_id_refs.py``) never needs to know which.

So a record holds data only: no tree-sitter node, no absolute path, nothing that does not
survive ``json.dumps``. Its path is relative to the project's git root when there is one,
else to the project's source directory, and always POSIX.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from sphinx_codelinks.analyse.models import NeedIdRefs


@dataclass(frozen=True, kw_only=True)
class NeedIdRef:
    """One ``@need-ids:`` reference: a located marker naming one need id."""

    need_id: str
    """The referenced id, exactly as written after the marker."""
    project: str
    """The codelinks project the source file belongs to."""
    marker: str
    """The marker that introduced the reference, e.g. ``@need-ids:``."""
    path: str
    """The source file, POSIX, relative to the project's git root (else its source dir)."""
    lineno: int
    """The 1-based line of the marker."""
    start_column: int
    """The 0-based column where the ids after the marker start."""
    end_column: int
    """The 0-based column where the ids after the marker end."""
    scope: str | None = None
    """The text of the code scope the marker is attached to, if one was found."""
    scope_rows: tuple[int, int] | None = None
    """The 1-based first and last line of that scope."""
    remote_url: str | None = None
    """The project's ``remote_url_pattern`` filled in for this line, if remote URLs are on."""
    local_url: str | None = None
    """The copied source under the build output (``<src dir name>/<path>#L<line>``), if
    local URLs are on; a document links to it relative to its own location."""

    def to_dict(self) -> dict[str, Any]:
        """The record as JSON-serialisable data (``scope_rows`` becomes a list)."""
        data = {item.name: getattr(self, item.name) for item in fields(self)}
        if self.scope_rows is not None:
            data["scope_rows"] = list(self.scope_rows)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NeedIdRef:
        """Read a record written by :meth:`to_dict`.

        :raises ValueError: if ``data`` carries a key that is not a field.
        :raises TypeError: if a required field is missing.
        """
        known = {item.name for item in fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"Unknown keys in a need id reference: {unknown}")
        values = dict(data)
        scope_rows = values.get("scope_rows")
        if scope_rows is not None:
            first, last = scope_rows
            values["scope_rows"] = (int(first), int(last))
        return cls(**values)


def _relative_posix(filepath: Path, root: Path) -> str:
    """``filepath`` relative to ``root``, POSIX; never absolute."""
    for candidate, base in (
        (filepath.absolute(), root.absolute()),
        (filepath.resolve(), root.resolve()),
    ):
        try:
            return candidate.relative_to(base).as_posix()
        except ValueError:
            continue
    # a file reached through a symlink out of the root: still relative, never absolute
    return Path(os.path.relpath(filepath.resolve(), root.resolve())).as_posix()


def need_id_ref_records(
    need_id_refs: Iterable[NeedIdRefs],
    *,
    project: str,
    root: Path,
    remote_url: Callable[[Path, int], str | None] | None = None,
    local_url: Callable[[Path, int], str | None] | None = None,
) -> list[NeedIdRef]:
    """One :class:`NeedIdRef` per id of each analysed ``@need-ids:`` marker.

    :param need_id_refs: The analysis' per-marker records.
    :param project: The codelinks project they belong to.
    :param root: What ``path`` is relative to: the git root, else the source directory.
    :param remote_url: Gives the remote URL for an (absolute) source file and line.
    :param local_url: Gives the local URL for an (absolute) source file and line.
    """
    records: list[NeedIdRef] = []
    for ref in need_id_refs:
        filepath = Path(ref.filepath)
        lineno = ref.source_map["start"]["row"] + 1
        scope: str | None = None
        scope_rows: tuple[int, int] | None = None
        node = ref.tagged_scope
        if node is not None:
            if node.text:
                scope = node.text.decode("utf-8")
            scope_rows = (node.start_point.row + 1, node.end_point.row + 1)
        template = NeedIdRef(
            need_id="",
            project=project,
            marker=ref.marker,
            path=_relative_posix(filepath, root),
            lineno=lineno,
            start_column=ref.source_map["start"]["column"],
            end_column=ref.source_map["end"]["column"],
            scope=scope,
            scope_rows=scope_rows,
            remote_url=remote_url(filepath, lineno) if remote_url else None,
            local_url=local_url(filepath, lineno) if local_url else None,
        )
        records.extend(replace(template, need_id=need_id) for need_id in ref.need_ids)
    return records
