"""The runner half of the case-per-project conformance corpora.

A corpus of this shape (sphinx-needs' ``derive_conformance.toml`` and
``field_declaration_conformance.toml``) is a TOML file of ``[[case]]`` rows, each one
project: a ``config`` that is its ``ubproject.toml``, a ``source`` that is the body of its
one document, optional ``files``, and an ``expect`` table of values (as ``needs.json``
writes them), unset fields, absent fields, needs not created, fields a record leaves
out, field schemas, and findings. The rules every runner follows
are in each corpus's header; this module is the part of sphinx-needs' runners that does
not depend on which corpus it runs. Each runner keeps what does: its path, its case
count, its codes, its ``conf.py``, its title, its shape test, and the readers a finding
of its own contract needs.

Plain functions with explicit parameters, deliberately: no corpus's constants live here,
so one runner changing its codes or its readers cannot change another's outcome.

The module is imported by path (``from sphinx_needs_testkit.conformance import ...``)
and is not re-exported by the package, so a suite that runs no corpus never loads it.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from ._warnings import build_warnings

__all__ = [
    "Finding",
    "Reader",
    "case_files",
    "check_schema",
    "check_values",
    "inside",
    "match_findings",
    "name_field",
    "params",
    "read_findings",
    "same",
    "schema_defaults",
]

#: A found finding: its code, the need it is reported at, then what the runner's
#: ``describe`` reads from the message (the field; the field and the need type).
Finding = tuple[str | None, ...]

#: A reader of one code's findings from somewhere other than the warning stream, called
#: with the built app and the needs of its ``needs.json``.
Reader = Callable[[Any, Mapping[str, Mapping[str, Any]]], Iterable[Finding]]

#: One record of the warning stream as :func:`build_warnings` gives it: an optional
#: ``<srcdir>/<doc>.rst:<line>:`` location, the severity, the message, and the
#: ``[family.code]`` that ends it. The code is compared BARE.
_WARNING = re.compile(
    r"^(?:<srcdir>/(?P<doc>[^:]+)\.rst:(?P<line>\d+): )?(?:WARNING|ERROR): "
    r"(?P<message>.*) \[(?P<family>[a-z_]+)\.(?P<code>[a-z_]+)\]$",
    re.DOTALL,
)
#: a ``[family.code]`` anywhere in a record, to catch a record ``_WARNING`` cannot read
_MENTION = re.compile(r"\[[a-z_]+\.([a-z_]+)\]")
#: the first field, option or link type a message names
_FIELD = re.compile(r"(?:[Ff]ield|option|[Ll]ink type) '([^']+)'")


def inside(relative: str) -> Path:
    """The case-directory path for *relative*, refusing one that would land outside it.

    The rule of every corpus's header: a case writes only inside its own directory, so a
    typo such as ``../x.json`` is a broken case, not a file written somewhere else.

    :raises AssertionError: If *relative* is absolute, climbs out, or names a drive.
    """
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts or ":" in relative:
        msg = f"{relative!r} is outside the case directory"
        raise AssertionError(msg)
    return Path(*posix.parts)


def case_files(
    case: Mapping[str, Any], *, conf_py: str, title: str
) -> list[tuple[Path, str]]:
    """The case's project: the runner's *conf_py*, the case's ``config`` as its
    ``ubproject.toml``, its ``source`` under *title* as ``index.rst``, and its other
    ``files``, each refused if it would land outside the case directory."""
    return [
        (Path("conf.py"), conf_py),
        (Path("ubproject.toml"), case["config"]),
        (Path("index.rst"), title + case["source"]),
        *((inside(rel), text) for rel, text in case.get("files", {}).items()),
    ]


def name_field(code: str, message: str) -> tuple[str | None]:
    """The field a message is about: the first field, option or link type it names."""
    field = _FIELD.search(message)
    return (field[1] if field else None,)


def read_findings(
    app: Any,
    needs: Mapping[str, Mapping[str, Any]],
    *,
    shared: frozenset[str],
    ubcode_only: frozenset[str],
    describe: Callable[[str, str], tuple[str | None, ...]] = name_field,
    readers: Mapping[str, Reader] | None = None,
) -> tuple[Counter[Finding], list[str]]:
    """The build's findings of the *shared* codes, and the records that name one but
    cannot be read as one.

    A finding is ``(code, need, *describe(code, message))``. ``need`` is the need whose
    directive the record is reported at (none for a finding of the configuration, or one
    at a ``needextend``). A code in *ubcode_only* is dropped: these runners skip every
    case only ubCode runs. A code in *readers* is not read from the warning stream at
    all -- its reader, called with the app and the needs, gives its findings instead, so a
    finding is counted once. A record this function cannot read is returned rather than
    skipped: a finding of the contract it fails to see would otherwise pass unnoticed.
    """
    at_line = {
        (need["docname"], need["lineno"]): need_id
        for need_id, need in needs.items()
        if need.get("lineno") is not None
    }
    readers = readers or {}
    named = shared - set(readers)
    from_records = named - ubcode_only
    found: Counter[Finding] = Counter()
    unread: list[str] = []
    for warning in build_warnings(app):
        match = _WARNING.match(warning)
        if match is None:
            if any(code in named for code in _MENTION.findall(warning)):
                unread.append(warning)
            continue
        if match["code"] not in from_records:
            continue
        need = None
        if match["line"] is not None:
            need = at_line.get((match["doc"], int(match["line"])))
        found[(match["code"], need, *describe(match["code"], match["message"]))] += 1
    for reader in readers.values():
        found.update(reader(app, needs))
    return found, unread


def match_findings(
    found: Counter[Finding],
    expected: Iterable[Mapping[str, str]],
    *,
    keys: tuple[str, ...] = ("code", "need", "field"),
) -> list[str]:
    """Match the *expected* findings against the *found* ones, a key left out matching
    any value; return what is left over on either side.

    *keys* names the positions of a found finding, ``code`` and ``need`` first.
    """
    left = list(found.elements())
    missing = []
    # the most specific first, so a wildcard does not take a finding a full one needs
    for finding in sorted(expected, key=lambda f: -len(f)):
        for index, item in enumerate(left):
            if all(
                finding.get(key, value) == value
                for key, value in zip(keys, item, strict=True)
            ):
                del left[index]
                break
        else:
            missing.append(f"missing {dict(finding)}")
    return missing + [f"unexpected {item}" for item in left]


def same(actual: Any, expected: Any) -> bool:
    """Equal, and of the same type for a number (``7.0`` is not ``7``)."""
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(same(a, e) for a, e in zip(actual, expected, strict=True))
        )
    if isinstance(expected, bool) or isinstance(actual, bool):
        return actual is expected
    if isinstance(expected, int | float):
        return type(actual) is type(expected) and actual == expected
    return actual == expected


def schema_defaults(properties: Mapping[str, Any]) -> dict[str, Any]:
    """The ``default`` of each property of a version's ``needs_schema`` *properties*
    that has one: what a reader of ``needs.json`` merges under each record."""
    return {
        name: spec["default"]
        for name, spec in properties.items()
        if isinstance(spec, Mapping) and "default" in spec
    }


def check_values(
    written: Mapping[str, Mapping[str, Any]],
    expect: Mapping[str, Any],
    *,
    defaults: Mapping[str, Any] | None = None,
) -> list[str]:
    """The problems with a case's pinned values: ``needs`` (values, type-strict),
    ``nulls`` (present and null), ``absent`` (the need present, the field not in its
    record), ``missing`` (the need not created) and ``omitted`` (the need present, the
    field no key of its *written* record, and a key once *defaults* are merged under
    it); an empty list when every pin holds.

    Every pin but ``omitted`` is compared against each record with *defaults* (the
    version's :func:`schema_defaults`) merged under it, as a reader merges them: a
    default fills a key the record lacks, a stated value wins. Without *defaults*, or
    for a record that leaves nothing out, the records are compared as written.
    """
    merge = dict(defaults or {})
    needs = {need_id: {**merge, **record} for need_id, record in written.items()}
    problems = []
    for need_id, fields in expect.get("needs", {}).items():
        if need_id not in needs:
            problems.append(f"{need_id}: no such need")
            continue
        for name, value in fields.items():
            actual = needs[need_id].get(name)
            if not same(actual, value):
                problems.append(f"{need_id}.{name}: {actual!r}, expected {value!r}")
    for need_id, names in expect.get("nulls", {}).items():
        # needs.json writes every declared field on every need, null included, so a
        # null pin names a need of the case and a field that need carries
        if need_id not in needs:
            problems.append(f"{need_id}: no such need")
            continue
        for name in names:
            if name not in needs[need_id]:
                problems.append(f"{need_id}.{name}: no such field")
            elif (actual := needs[need_id][name]) is not None:
                problems.append(f"{need_id}.{name}: {actual!r}, expected null")
    for need_id, names in expect.get("absent", {}).items():
        # a field that does not exist is no key at all, which is not a null
        if need_id not in needs:
            problems.append(f"{need_id}: no such need")
            continue
        for name in names:
            if name in needs[need_id]:
                problems.append(
                    f"{need_id}.{name}: {needs[need_id][name]!r}, expected no such field"
                )
    for need_id in expect.get("missing", []):
        # a need the source gives that is not created is no key of the needs at all
        if need_id in needs:
            problems.append(f"{need_id}: created, expected no such need")
    for need_id, names in expect.get("omitted", {}).items():
        # a value left out under json_remove_defaults: no key of the record as written,
        # and restored by a schema default, so the merged record has it
        if need_id not in written:
            problems.append(f"{need_id}: no such need")
            continue
        for name in names:
            if name in written[need_id]:
                problems.append(
                    f"{need_id}.{name}: written as {written[need_id][name]!r}, "
                    "expected left out"
                )
            elif name not in needs[need_id]:
                problems.append(
                    f"{need_id}.{name}: left out, and no default restores it"
                )
    return problems


def check_schema(
    properties: Mapping[str, Mapping[str, Any]], expect: Mapping[str, Any]
) -> list[str]:
    """The problems with a case's pinned field schemas: each key a ``schema.<field>``
    table gives, compared type-strict with the field's entry in the ``needs_schema``
    *properties* of ``needs.json``; a key it leaves out is not compared."""
    problems = []
    for name, keys in expect.get("schema", {}).items():
        if name not in properties:
            problems.append(f"schema.{name}: no such field")
            continue
        for key, value in keys.items():
            if key not in properties[name]:
                problems.append(f"schema.{name}.{key}: no such key")
            elif not same(actual := properties[name][key], value):
                problems.append(f"schema.{name}.{key}: {actual!r}, expected {value!r}")
    return problems


def params(
    cases: Iterable[Mapping[str, Any]],
    *,
    files: Callable[[Mapping[str, Any]], list[tuple[Path, str]]],
) -> list[Any]:
    """One ``pytest.param`` per case for an indirect ``test_app``: a ``needs`` build of
    ``files(case)``, the case itself, the case's name as the id, and a skip for a case
    only ubCode runs."""
    built = []
    for case in cases:
        marks = (
            [pytest.mark.skip(reason="ubcode_only: a case only ubCode runs")]
            if case.get("ubcode_only")
            else []
        )
        built.append(
            pytest.param(
                {"buildername": "needs", "files": files(case)},
                case,
                id=case["name"],
                marks=marks,
            )
        )
    return built
