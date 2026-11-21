"""Need parts, held to the shared conformance corpus.

``tests/fixtures/parts_conformance.toml`` is the executable half of
``design/parts-contract.md``. This repository is its repository of record and ubCode is
to vendor it, so every case is a statement both tools are held to. Each case is one
project, built with the ``html`` builder (a role outside every need is reported where a
page is written), and four things are asserted:

* every case's outcome: each named need's parts as a set of id and text, each named
  need's dead links, the back links of each named need and part per link type, the
  findings of the contract as a multiset of classes (and nothing else where the case says
  ``clean``), and what each filter selects over needs and parts;
* a case marked ``divergent`` for sphinx-needs FAILS with exactly the problems recorded
  for it, fails as a second deviation with any others, and fails when it passes, so a fix
  cannot leave its marker behind;
* the number of cases, so that a trimmed corpus is a red test rather than quietly reduced
  coverage;
* the shape of every case, its section and its markers, and the classes and codes the
  header lists.

The parts and back links are read from the needs as the build leaves them, through the
``needs-before-sealing`` event, and the findings from the build's warnings before anything
reads the needs again.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs import filter_common
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.filter_common import filter_needs_parts
from sphinx_needs.ubquery import try_build_simple_predicate
from sphinx_needs_testkit import build_warnings
from sphinx_needs_testkit.conformance import case_files, params, uninstalled_extension

CORPUS_PATH = Path(__file__).parent / "fixtures" / "parts_conformance.toml"

#: The number of ``[[case]]`` rows the corpus carries.
#:
#: Raising it is the normal consequence of adding a case; lowering it needs a reason in
#: the commit message, and ubCode's vendored copy has to follow either way.
EXPECTED_CASE_COUNT = 52

#: The sections, in the order the corpus gives them.
SECTIONS = (
    "grammar",
    "placement",
    "duplicates",
    "stated",
    "addressing",
    "links",
    "answers",
    "derived",
)

#: Each class of finding of the contract, by sphinx-needs' code (the bare subcode of
#: ``needs.<code>``). Every other finding is sphinx-needs' own and compared only in a
#: ``clean`` case, where there must be none.
CLASSES = {
    "duplicate_part_id": "duplicate part id",
    "part": "part outside a need",
    "link_outgoing": "dead link",
    "link_target_type": "link target type",
    "link_condition_failed": "link condition",
}

#: The tools a ``divergent`` marker may name; this runner is the first's.
TOOLS = ("sphinx-needs", "ubcode")
THIS_TOOL = "sphinx-needs"

#: Each case marked ``divergent`` for sphinx-needs, with the exact problems it gives
#: today. A marked case is an expected failure for the deviation its marker names and
#: for nothing else: any other list of problems is a second deviation, and fails.
#:
#: This table is the Python runner's alone; the shared corpus keeps its marker shape.
#: A fix of a deviation empties its list, which fails the case until its marker and its
#: row here are removed together.
MARKED_PROBLEMS: dict[str, list[str]] = {
    "placement-a-hidden-need": [
        "REQ_HID: parts {}, expected {'h1': 'a hidden part'}",
        "findings ['dead link'], expected []",
        "TEST_1: dead links ['REQ_HID.h1'], expected []",
        "TEST_1: has_dead_links is True, expected False",
        "REQ_HID.h1: no such part",
    ],
}

#: The configuration the runner gives every case besides its ``ubproject.toml``.
CONF_PY = """\
extensions = {extensions!r}
needs_from_toml = "ubproject.toml"
"""

#: The extensions a case may load besides sphinx-needs, each with the lines of
#: ``conf.py`` pointing it at the case's ``ubproject.toml``.
EXTENSIONS = {
    "myst_parser": "",
    "sphinx_codelinks": 'src_trace_config_from_toml = "ubproject.toml"\n',
    "sphinx_test_reports": 'tr_config_from_toml = "ubproject.toml"\n',
}

#: The ``.git`` a case loading sphinx-codelinks is given, as the header states it.
GIT_FILES = {
    ".git/HEAD": "0123456789abcdef0123456789abcdef01234567\n",
    ".git/config": '[remote "origin"]\n\turl = https://github.com/example/case.git\n',
}

#: The title the runner puts above every case's ``source``.
TITLE = "Case\n====\n\n"

#: The document a filter is evaluated from.
ORIGIN = "index"

_CASE_KEYS = {
    "name",
    "section",
    "why",
    "config",
    "source",
    "files",
    "extensions",
    "clean",
    "divergent",
    "expect",
    "filters",
}
_EXPECT_KEYS = {"findings", "parts", "dead", "back"}
_ENTRY_KEYS = {"filter", "expected", "include_parts", "why"}

#: A record's code: the ``[needs.<code>]`` that ends it.
_CODE = re.compile(r"\[needs\.([a-z_]+)\]$")
#: sphinx-needs' report of a dead link: the need, the address and the link type.
_DEAD = re.compile(
    r"Need '(?P<need>[^']+)' has unknown outgoing link '(?P<address>[^']*)' "
    r"in field '(?P<field>[^']+)'"
)


def _corpus() -> list[dict[str, Any]]:
    return tomllib.loads(CORPUS_PATH.read_text(encoding="utf-8"))["case"]


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


def test_every_case_is_in_a_known_section_in_order() -> None:
    """Every case names a section of the header's list, and the cases of a section are
    together, the sections in the header's order."""
    seen = [case["section"] for case in CASES]
    assert set(seen) <= set(SECTIONS), sorted(set(seen) - set(SECTIONS))
    order = [section for i, section in enumerate(seen) if section not in seen[:i]]
    assert order == [s for s in SECTIONS if s in seen]
    assert seen == sorted(seen, key=SECTIONS.index)


def test_every_case_has_a_complete_expectation() -> None:
    """Every case says why and what it builds, its findings (``[]`` for none), and at
    least one more pin; every key is one the header defines, each of its own shape."""
    for case in CASES:
        name = case["name"]
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), name
        assert set(case) <= _CASE_KEYS, name
        assert case["why"] and isinstance(case["config"], str) and case["source"], name
        assert "\n" not in case["why"], name
        assert case.get("clean", True) is True, name
        extensions = case.get("extensions", [])
        assert isinstance(extensions, list) and set(extensions) <= set(EXTENSIONS), name
        expect = case["expect"]
        assert set(expect) <= _EXPECT_KEYS, name
        assert isinstance(expect["findings"], list), name
        for finding in expect["findings"]:
            assert set(finding) == {"class"}, name
            assert finding["class"] in CLASSES.values(), name
        assert any(expect.get(key) for key in ("parts", "dead", "back")) or case.get(
            "filters"
        ), name
        for need_id, parts in expect.get("parts", {}).items():
            assert isinstance(parts, dict), (name, need_id)
            assert all(isinstance(text, str) for text in parts.values()), name
        for need_id, dead in expect.get("dead", {}).items():
            assert dead == sorted(set(dead)), (name, need_id)
        # a back-link pin names a link type the case has: `links`, or one its
        # `ubproject.toml` declares (a misspelt one would read as no back links)
        link_types = {"links", *tomllib.loads(case["config"])["needs"].get("links", {})}
        for address, by_type in expect.get("back", {}).items():
            assert set(by_type) <= link_types, (name, address, sorted(by_type))
            for ids in by_type.values():
                assert ids == sorted(set(ids)), (name, address)
        for entry in case.get("filters", []):
            where = f"{name}: {entry.get('filter')!r}"
            assert set(entry) <= _ENTRY_KEYS, where
            assert entry["include_parts"] is True, where
            assert isinstance(entry["filter"], str) and entry["filter"], where
            assert entry["expected"] == sorted(set(entry["expected"])), where


def test_every_marker_names_a_known_tool() -> None:
    """A ``divergent`` marker names one or more tools, each with what it answers
    instead; a marker for sphinx-needs names the issue tracking it, or says it is not
    filed yet, and a marker for another tool names no issue, as the header says."""
    for case in CASES:
        if "divergent" not in case:
            continue
        marker = case["divergent"]
        assert marker and set(marker) <= set(TOOLS), case["name"]
        assert all(isinstance(v, str) and v for v in marker.values()), case["name"]
        if THIS_TOOL in marker:
            assert re.search(r"\(#\d+\)|\(not filed yet\)", marker[THIS_TOOL]), case[
                "name"
            ]
        for tool, text in marker.items():
            if tool != THIS_TOOL:
                assert not re.search(r"#\d+|not filed yet", text), case["name"]
    marked = {case["name"] for case in CASES if THIS_TOOL in case.get("divergent", {})}
    assert marked == set(MARKED_PROBLEMS), (
        "every case marked for sphinx-needs, and no other, has its problems recorded"
    )


def test_every_filter_is_in_the_portable_language() -> None:
    """Every filter string is answered by the portable tier, never by ``eval``: the
    parsed tier compiles it, as ``tests/test_filter_conformance.py`` asks it."""
    for case in CASES:
        for entry in case.get("filters", []):
            where = f"{case['name']}: {entry['filter']!r}"
            tier, reason = filter_common._filter_tier(entry["filter"])
            assert tier in ("index", "fast"), f"{where} falls to eval ({reason})"
            assert try_build_simple_predicate(entry["filter"]) is not None, where


def test_the_header_lists_every_class_and_section() -> None:
    """The header's table of classes and codes is the runner's, row for row, and its list
    of sections is the runner's, in order."""
    header = CORPUS_PATH.read_text(encoding="utf-8").split("\n[[case]]", 1)[0]
    rows = re.findall(r"^#\s{9}([a-z ]+?)\s{2,}needs\.([a-z_]+)$", header, re.M)
    assert {code: cls for cls, code in rows} == CLASSES
    assert len(rows) == len(CLASSES)
    prose = " ".join(line.removeprefix("#").strip() for line in header.splitlines())
    assert f"Sections, in this order: {', '.join(SECTIONS)}." in prose
    for tool in TOOLS:
        assert f"`{tool}`" in prose


def test_the_corpus_header_records_where_it_is_canonical() -> None:
    """ubCode's copy names this path; the header must keep saying this one is canonical."""
    header = CORPUS_PATH.read_text(encoding="utf-8")
    assert "packages/sphinx-needs/tests/fixtures/parts_conformance.toml" in header
    assert "THIS copy is CANONICAL" in header


def test_the_header_states_the_git_files_the_runner_writes() -> None:
    """A second runner writes the two ``.git`` files from the header alone."""
    header = CORPUS_PATH.read_text(encoding="utf-8").split("\n[[case]]", 1)[0]
    prose = " ".join(line.removeprefix("#").strip() for line in header.splitlines())
    head = GIT_FILES[".git/HEAD"]
    assert f"`.git/HEAD` is `{head[:-1]}` and a newline" in prose
    section, url = GIT_FILES[".git/config"].split("\n\t", 1)
    assert (
        f"`.git/config` is `{section}`, a newline, a tab, `{url[:-1]}` and a newline"
        in prose
    )


def _files(case: Mapping[str, Any]) -> list[tuple[Path, str]]:
    """The case's project: its configuration, its document, its other files, and a
    ``.git`` where it loads sphinx-codelinks."""
    loaded = case.get("extensions", [])
    template = CONF_PY + "".join(EXTENSIONS[name] for name in loaded)
    files = case_files(case, conf_py=template, title=TITLE, extensions=EXTENSIONS)
    if "sphinx_codelinks" in loaded:
        files += [(Path(path), text) for path, text in GIT_FILES.items()]
    return files


@pytest.mark.parametrize(
    "relative", ["../x.json", "/x.json", "a/../../x.json", "C:/x.json"]
)
def test_a_case_cannot_write_outside_its_directory(relative: str) -> None:
    with pytest.raises(AssertionError, match="outside the case directory"):
        _files({"config": "", "source": "", "files": {relative: "{}"}})


def _html(param: Any) -> Any:
    """The helper's parameter, built with the ``html`` builder."""
    build, case = param.values
    return pytest.param(
        {**build, "buildername": "html"}, case, id=param.id, marks=param.marks
    )


def _snapshot(store: dict[str, dict[str, Any]]) -> Any:
    """A ``needs-before-sealing`` listener keeping each need's parts, its back links and
    whether it has dead links, as the build leaves them."""

    def listener(_app: Any, needs: Mapping[str, Any]) -> None:
        for need_id, need in needs.items():
            store[need_id] = json.loads(
                json.dumps(
                    {
                        key: value
                        for key, value in need.items()
                        if key in ("parts", "has_dead_links") or key.endswith("_back")
                    }
                )
            )

    return listener


def _address(address: str) -> tuple[str, str | None]:
    """A need id and a part id, the address split at its first ``.``."""
    need_id, dot, part = address.partition(".")
    return need_id, (part if dot else None)


def _check(
    case: Mapping[str, Any],
    needs: Mapping[str, Mapping[str, Any]],
    warnings: list[str],
) -> list[str]:
    """The problems with a case's ``expect``; an empty list when every pin holds."""
    expect = case["expect"]
    problems: list[str] = []

    # the parts, as a set of id and text
    for need_id, parts in expect.get("parts", {}).items():
        if need_id not in needs:
            problems.append(f"{need_id}: no such need")
            continue
        stored = {pid: part["content"] for pid, part in needs[need_id]["parts"].items()}
        if stored != parts:
            problems.append(f"{need_id}: parts {stored!r}, expected {parts!r}")

    # the findings, a multiset of classes; and, in a clean case, nothing else
    codes = [m[1] if (m := _CODE.search(w)) else None for w in warnings]
    found = Counter(CLASSES[code] for code in codes if code in CLASSES)
    wanted = Counter(finding["class"] for finding in expect["findings"])
    if found != wanted:
        problems.append(
            f"findings {sorted(found.elements())}, expected {sorted(wanted.elements())}"
        )
    if case.get("clean"):
        others = [
            w for w, code in zip(warnings, codes, strict=True) if code not in CLASSES
        ]
        if others:
            problems.append(f"reports {others}, expected nothing but its findings")

    # the dead links, read from the tool's own report, and its flag on the need. The
    # flag, ``has_dead_links``, is a cross-check of this runner alone: the corpus
    # defines ``dead`` as the links a tool reports, and says nothing of the flag
    dead: dict[str, set[str]] = {}
    for warning in warnings:
        if (match := _DEAD.search(warning)) is not None:
            dead.setdefault(match["need"], set()).add(match["address"])
    for need_id, addresses in expect.get("dead", {}).items():
        if need_id not in needs:
            problems.append(f"{need_id}: no such need")
            continue
        reported = sorted(dead.get(need_id, set()))
        if reported != addresses:
            problems.append(f"{need_id}: dead links {reported}, expected {addresses}")
        if needs[need_id]["has_dead_links"] is not bool(addresses):
            problems.append(
                f"{need_id}: has_dead_links is {needs[need_id]['has_dead_links']}, "
                f"expected {bool(addresses)}"
            )

    # the back links of a need, or of one of its parts
    for address, by_type in expect.get("back", {}).items():
        need_id, part = _address(address)
        if need_id not in needs:
            problems.append(f"{address}: no such need")
            continue
        if part is None:
            holder = needs[need_id]
        elif part in needs[need_id]["parts"]:
            holder = needs[need_id]["parts"][part]
        else:
            problems.append(f"{address}: no such part")
            continue
        for link_type, ids in by_type.items():
            actual = sorted(set(holder.get(f"{link_type}_back", [])))
            if actual != ids:
                problems.append(
                    f"{address}: {link_type} back links {actual}, expected {ids}"
                )
    return problems


#: A built project as :func:`_check` reads it: REQ_1 with the parts p1 and p2, linked
#: whole by TEST_A and through p1 by TEST_B; TEST_C with one dead link, to the empty part
#: of REQ_1, which the tool reports as written; and one repeated part id in REQ_1.
_BUILT = {
    "REQ_1": {
        "parts": {
            "p1": {"id": "p1", "content": " one", "tests_back": ["TEST_B"]},
            "p2": {"id": "p2", "content": " two"},
        },
        "has_dead_links": False,
        "tests_back": ["TEST_A", "TEST_B", "TEST_C"],
    },
    "REQ_2": {"parts": {}, "has_dead_links": False, "tests_back": []},
    "TEST_C": {"parts": {}, "has_dead_links": True, "tests_back": []},
}
_REPORTED = [
    "<srcdir>/index.rst:5: WARNING: part_need id p1 in need REQ_1 is already taken. "
    "need_part may get overridden. [needs.duplicate_part_id]",
    "<srcdir>/index.rst:9: WARNING: Need 'TEST_C' has unknown outgoing link 'REQ_1.' "
    "in field 'tests' [needs.link_outgoing]",
]
_FAITHFUL = {
    "clean": True,
    "expect": {
        "findings": [{"class": "duplicate part id"}, {"class": "dead link"}],
        "parts": {"REQ_1": {"p1": " one", "p2": " two"}, "REQ_2": {}},
        "dead": {"TEST_C": ["REQ_1."], "REQ_1": []},
        "back": {
            "REQ_1": {"tests": ["TEST_A", "TEST_B", "TEST_C"]},
            "REQ_1.p1": {"tests": ["TEST_B"]},
        },
    },
}


def test_the_runner_reads_a_faithful_project_as_one() -> None:
    assert _check(_FAITHFUL, _BUILT, _REPORTED) == []


@pytest.mark.parametrize(
    "key,value",
    [
        # a runner comparing part ids without their texts
        ("parts", {"REQ_1": {"p1": " one ", "p2": " two"}, "REQ_2": {}}),
        # one skipping a need the case names with no parts
        ("parts", {"REQ_1": {}, "REQ_2": {}}),
        # one counting the findings as a set
        ("findings", [{"class": "duplicate part id"}] * 2 + [{"class": "dead link"}]),
        ("findings", [{"class": "dead link"}]),
        # one reading a part's back links from its need
        ("back", {"REQ_1.p1": {"tests": ["TEST_A", "TEST_B", "TEST_C"]}}),
        # one falling back to the need's back links where a part has none of a type
        ("back", {"REQ_1.p2": {"tests": ["TEST_A"]}}),
        # one normalising a dead link's address, or ignoring a need with none
        ("dead", {"TEST_C": ["REQ_1"]}),
        ("dead", {"TEST_C": ["REQ_1."], "REQ_1": ["REQ_1.p3"]}),
    ],
    ids=[
        "texts",
        "a-need-with-no-parts",
        "findings-as-a-set",
        "a-finding-left-out",
        "a-parts-back-links-are-not-its-needs",
        "a-part-with-no-back-links",
        "a-dead-address-as-written",
        "a-need-with-no-dead-links",
    ],
)
def test_the_runner_sees_every_difference(key: str, value: Any) -> None:
    """Each pin, changed so that it no longer describes the built project, is a problem:
    each of these is a wrong runner that would leave every case of the corpus green."""
    case = {**_FAITHFUL, "expect": {**_FAITHFUL["expect"], key: value}}
    assert _check(case, _BUILT, _REPORTED) != []


def test_a_clean_case_sees_any_other_report() -> None:
    other = "<srcdir>/index.rst:3: WARNING: Unknown directive type: 'nope'. [docutils]"
    assert _check(_FAITHFUL, _BUILT, [*_REPORTED, other]) != []
    assert _check({**_FAITHFUL, "clean": False}, _BUILT, [*_REPORTED, other]) == []


def _check_filters(app: Any, case: Mapping[str, Any]) -> list[str]:
    """The problems with a case's filters: what each selects over needs and parts, and
    that it reports nothing."""
    problems: list[str] = []
    if not case.get("filters"):
        return problems
    view = SphinxNeedsData(app.env).get_needs_view()
    config = NeedsSphinxConfig(app.config)
    stream = app._warning
    for entry in case["filters"]:
        start = len(stream.getvalue())
        found = filter_needs_parts(
            view.to_list_with_parts(), config, entry["filter"], origin_docname=ORIGIN
        )
        selected = sorted(item["id_complete"] for item in found)
        if selected != entry["expected"]:
            problems.append(
                f"{entry['filter']!r}: selects {selected}, expected {entry['expected']}"
            )
        if reported := build_warnings(stream.getvalue()[start:], srcdir=app.srcdir):
            problems.append(f"{entry['filter']!r}: reports {reported}")
    return problems


@pytest.mark.parametrize(
    "test_app,case",
    [_html(p) for p in params(CASES, files=_files, skip=uninstalled_extension)],
    indirect=["test_app"],
)
def test_case(test_app: Any, case: dict[str, Any]) -> None:
    app = test_app
    needs: dict[str, dict[str, Any]] = {}
    app.connect("needs-before-sealing", _snapshot(needs))
    app.build()
    # the findings first: reading the needs again after the build re-runs their
    # post-processing, and with it the reports of their links
    warnings = build_warnings(app)
    problems = _check(case, needs, warnings) + _check_filters(app, case)
    marker = case.get("divergent", {}).get(THIS_TOOL)
    if marker is None:
        assert problems == [], f"{case['name']}: {case['why']}"
    elif not problems:
        pytest.fail(
            f"{case['name']} is marked divergent for {THIS_TOOL} ({marker}) and passes: "
            "remove the marker"
        )
    elif problems != MARKED_PROBLEMS[case["name"]]:
        pytest.fail(
            f"{case['name']} is marked divergent for {THIS_TOOL} ({marker}), and a "
            f"second deviation appeared: it gives {problems}, where the marked "
            f"deviation gives {MARKED_PROBLEMS[case['name']]}"
        )
    else:
        pytest.xfail(f"{marker}: {problems}")
