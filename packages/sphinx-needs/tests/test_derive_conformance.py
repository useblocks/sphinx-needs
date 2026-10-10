"""Declared derived fields, held to the shared conformance corpus.

``tests/fixtures/derive_conformance.toml`` is the executable half of the "Derived fields"
documentation. This repository is its repository of record and ubCode vendors it, so
every case is a statement both tools are held to. Each case is one project, built with
the ``needs`` builder, and three things are asserted:

* every case's outcome -- the pinned values, as ``needs.json`` writes them (type
  included), the fields pinned as unset, and the findings of the derived-field contract,
  as a multiset;
* the number of cases, so that a trimmed corpus is a red test rather than quietly reduced
  coverage;
* the shape of every case, so that a case without a complete expectation cannot pass by
  saying nothing.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from sphinx_needs_testkit import build_warnings

CORPUS_PATH = Path(__file__).parent / "fixtures" / "derive_conformance.toml"

#: The number of ``[[case]]`` rows the corpus carries.
#:
#: Raising it is the normal consequence of adding a case; lowering it needs a reason in
#: the commit message, and ubCode's vendored copy has to follow either way.
EXPECTED_CASE_COUNT = 24

#: The codes of the derived-field contract, compared as bare subcodes; every other
#: finding (a dead link, a deprecated option) is each tool's own.
SHARED_CODES = frozenset(
    {
        "derive_invalid",
        "derive_authored",
        "derive_unique",
        "derive_cycle",
        "derive_scope",
        "dynamic_function",
        "derive_sphinx_minimum",
    }
)

#: The configuration the runner gives every case besides its ``ubproject.toml``.
CONF_PY = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True
"""

#: The title the runner puts above every case's ``source``.
TITLE = "Case\n====\n\n"

_WARNING = re.compile(
    r"^(?:<srcdir>/(?P<doc>[^:]+)\.rst:(?P<line>\d+): )?(?:WARNING|ERROR): "
    r"(?P<message>.*) \[(?P<family>[a-z_]+)\.(?P<code>[a-z_]+)\]$",
    re.DOTALL,
)
_FIELD = re.compile(r"(?:[Ff]ield|option|[Ll]ink type) '([^']+)'")


def _corpus() -> list[dict[str, Any]]:
    with CORPUS_PATH.open("rb") as handle:
        return tomllib.load(handle)["case"]


CASES = _corpus()


def test_the_corpus_still_has_every_case() -> None:
    assert len(CASES) == EXPECTED_CASE_COUNT, (
        f"{CORPUS_PATH.name} carries {len(CASES)} cases, expected "
        f"{EXPECTED_CASE_COUNT}. Adding a case means raising EXPECTED_CASE_COUNT; "
        "anything else means cases were lost."
    )


def test_every_case_name_is_unique() -> None:
    names = Counter(case["name"] for case in CASES)
    assert [name for name, count in names.items() if count > 1] == []


def test_every_case_has_a_complete_expectation() -> None:
    """Every case says why, what it builds, the findings (``[]`` for none), and at least
    one pinned value; it runs in at least one tool."""
    for case in CASES:
        name = case["name"]
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), name
        assert set(case) <= {
            "name",
            "why",
            "config",
            "source",
            "files",
            "python_only",
            "ubcode_only",
            "expect",
        }, name
        assert case["why"] and case["config"] and case["source"], name
        assert not (case.get("python_only") and case.get("ubcode_only")), name
        expect = case["expect"]
        assert "findings" in expect, name
        assert set(expect) <= {"needs", "nulls", "findings"}, name
        assert expect.get("needs") or expect.get("nulls"), name
        for finding in expect["findings"]:
            assert set(finding) <= {"code", "need", "field"}, name
            assert finding["code"] in SHARED_CODES, name


def test_the_corpus_header_records_where_it_is_canonical() -> None:
    """ubCode's copy names this path; the header must keep saying this one is canonical."""
    header = CORPUS_PATH.read_text(encoding="utf-8")
    assert "packages/sphinx-needs/tests/fixtures/derive_conformance.toml" in header
    assert "THIS copy is CANONICAL" in header


def _inside(relative: str) -> Path:
    """The case-directory path for *relative*, refusing one that would land outside it.

    The header's rule for every runner: a case writes only inside its own directory, so a
    typo such as ``../x.json`` is a broken case, not a file written somewhere else.
    """
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts or ":" in relative:
        msg = f"{relative!r} is outside the case directory"
        raise AssertionError(msg)
    return Path(*posix.parts)


def _files(case: dict[str, Any]) -> list[tuple[Path, str]]:
    """The case's project: its configuration, its document, and its other files."""
    return [
        (Path("conf.py"), CONF_PY),
        (Path("ubproject.toml"), case["config"]),
        (Path("index.rst"), TITLE + case["source"]),
        *((_inside(rel), text) for rel, text in case.get("files", {}).items()),
    ]


@pytest.mark.parametrize(
    "relative", ["../x.json", "/x.json", "a/../../x.json", "C:/x.json"]
)
def test_a_case_cannot_write_outside_its_directory(relative: str) -> None:
    with pytest.raises(AssertionError, match="outside the case directory"):
        _files({"config": "", "source": "", "files": {relative: "{}"}})


def _findings(app: Any, needs: dict[str, dict[str, Any]]) -> Counter[tuple]:
    """The build's findings of the shared codes, as ``(code, need, field)``.

    ``need`` is the need whose directive the finding is reported at (none for a finding
    of the configuration, or one at a ``needextend``); ``field`` the first field, option
    or link type the message names.
    """
    at_line = {
        (need["docname"], need["lineno"]): need_id
        for need_id, need in needs.items()
        if need.get("lineno") is not None
    }
    found: Counter[tuple] = Counter()
    for warning in build_warnings(app):
        match = _WARNING.match(warning)
        if match is None or match["code"] not in SHARED_CODES:
            continue
        need = None
        if match["line"] is not None:
            need = at_line.get((match["doc"], int(match["line"])))
        field = _FIELD.search(match["message"])
        found[(match["code"], need, field[1] if field else None)] += 1
    return found


def _match(found: Counter[tuple], expected: list[dict[str, str]]) -> list[str]:
    """Match the expected findings against the found ones, a key left out matching any
    value; return what is left over on either side."""
    left = list(found.elements())
    missing = []
    # the most specific first, so a wildcard does not take a finding a full one needs
    for finding in sorted(expected, key=lambda f: -len(f)):
        for index, (code, need, field) in enumerate(left):
            if (
                code == finding["code"]
                and finding.get("need", need) == need
                and finding.get("field", field) == field
            ):
                del left[index]
                break
        else:
            missing.append(f"missing {finding}")
    return missing + [f"unexpected {item}" for item in left]


def _same(actual: Any, expected: Any) -> bool:
    """Equal, and of the same type for a number (``7.0`` is not ``7``)."""
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_same(a, e) for a, e in zip(actual, expected, strict=True))
        )
    if isinstance(expected, bool) or isinstance(actual, bool):
        return actual is expected
    if isinstance(expected, int | float):
        return type(actual) is type(expected) and actual == expected
    return actual == expected


def _params() -> list[Any]:
    params = []
    for case in CASES:
        marks = (
            [pytest.mark.skip(reason="ubcode_only: a case only ubCode runs")]
            if case.get("ubcode_only")
            else []
        )
        params.append(
            pytest.param(
                {"buildername": "needs", "files": _files(case)},
                case,
                id=case["name"],
                marks=marks,
            )
        )
    return params


@pytest.mark.parametrize("test_app,case", _params(), indirect=["test_app"])
def test_case(test_app: Any, case: dict[str, Any]) -> None:
    app = test_app
    app.build()
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = data["versions"][data["current_version"]]["needs"]
    expect = case["expect"]
    problems = []
    for need_id, fields in expect.get("needs", {}).items():
        if need_id not in needs:
            problems.append(f"{need_id}: no such need")
            continue
        for name, value in fields.items():
            actual = needs[need_id].get(name)
            if not _same(actual, value):
                problems.append(f"{need_id}.{name}: {actual!r}, expected {value!r}")
    for need_id, names in expect.get("nulls", {}).items():
        for name in names:
            if (actual := needs.get(need_id, {}).get(name)) is not None:
                problems.append(f"{need_id}.{name}: {actual!r}, expected null")
    problems += _match(_findings(app, needs), expect["findings"])
    assert problems == [], case["why"]
