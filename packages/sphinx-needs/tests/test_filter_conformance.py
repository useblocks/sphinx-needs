"""The portable filter language, held to the shared conformance corpus.

``tests/fixtures/filter_conformance.toml`` is the executable half of the "Filter string"
documentation. This repository is its repository of record and ubCode vendors it, so
every entry is a statement both tools are held to. Each case is one project, built once
with the ``needs`` builder; for every filter of it, four things are asserted:

* the needs (and parts) the filter engine selects -- :func:`.filter_needs_view`, or
  :func:`.filter_needs_parts` where the entry includes parts -- are ``expected``, and the
  engine reports the filter, with one ``needs.filter`` warning, exactly when the entry
  says ``error``;
* the tier that answers it: the parsed tier compiles every string inside the language
  (``try_build_simple_predicate`` is not None) and none outside it (``tier = "eval"``),
  the tier and reason the debug report gives are the ones the entry pins, and a
  constant (``tier = "refused"``) is answered by no tier;
* need by need, the parsed tier and the ``eval`` tier give the same answer, an error
  included with its message, and for a constant that answer is its refusal;
* need by need, the parsed tier selects ``expected`` too, so the index path, the parsed
  tier and ``eval`` agree.

Then the number of cases and of entries, so that a trimmed corpus is a red test rather
than quietly reduced coverage, the shape of every entry, and the header.
"""

from __future__ import annotations

import re
import tomllib
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any
from unittest.mock import patch

import pytest

from sphinx_needs import filter_common
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs.filter_common import (
    filter_needs_parts,
    filter_needs_view,
    filter_single_need,
)
from sphinx_needs.ubquery import CompiledFilter, try_build_simple_predicate
from sphinx_needs_testkit import build_warnings
from sphinx_needs_testkit.conformance import (
    case_files,
    inside,
    params,
    uninstalled_extension,
)

CORPUS_PATH = Path(__file__).parent / "fixtures" / "filter_conformance.toml"

#: The number of ``[[case]]`` rows, and of ``[[case.filters]]`` entries, the corpus
#: carries. Raising one is the normal consequence of adding a case or an entry; lowering
#: it needs a reason in the commit message, and ubCode's vendored copy has to follow
#: either way.
EXPECTED_CASE_COUNT = 25
EXPECTED_FILTER_COUNT = 305

#: The configuration the runner gives every case besides its ``ubproject.toml``: its
#: ``extensions`` are sphinx-needs, then the case's own, and each reads the case's
#: ``ubproject.toml`` (one directory up for a case whose ``srcdir`` is a subdirectory).
CONF_PY = """\
extensions = {extensions!r}
needs_from_toml = "{toml}"
"""

#: The extensions a case may load besides sphinx-needs (its ``extensions`` key), each
#: with the line of ``conf.py`` pointing it at the case's ``ubproject.toml`` where that
#: is not beside ``conf.py``.
EXTENSIONS = {
    "sphinx_codelinks": 'src_trace_config_from_toml = "{toml}"\n',
    "sphinx_test_reports": 'tr_config_from_toml = "{toml}"\n',
}

#: The ``.git`` a case loading sphinx-codelinks is given, as the header states it: a
#: detached ``HEAD`` and an ``origin``, so that its remote and its commit are found
#: with no ``git`` binary, and the build is clean.
GIT_FILES = {
    ".git/HEAD": "0123456789abcdef0123456789abcdef01234567\n",
    ".git/config": '[remote "origin"]\n\turl = https://github.com/example/case.git\n',
}

#: The title the runner puts above every case's ``source``.
TITLE = "Case\n====\n\n"

#: The document a filter is evaluated from, unless its entry says ``in_document = false``.
ORIGIN = "index"

_CASE_KEYS = {
    "name",
    "why",
    "config",
    "source",
    "files",
    "extensions",
    "srcdir",
    "python_only",
    "ubcode_only",
    "filters",
}
_ENTRY_KEYS = {
    "filter",
    "expected",
    "why",
    "error",
    "tier",
    "reason",
    "in_document",
    "include_parts",
    "python_only",
    "ubcode_only",
    "divergent",
}

#: The values of an entry's ``tier``.
_TIERS = ("index", "fast", "eval", "refused")

#: The warning a case's build may give besides none (:func:`test_case`): the
#: deprecation of `filter_data`, which the residue's own filters read.
_DEPRECATED = "[needs.deprecated]"

#: The finding of a field named `source`, which switches the facets off: each tool
#: reports it its own way, and the header leaves it uncompared.
_SOURCE_SHADOWED = "[needs.source_shadowed]"

#: The finding of an `inherits` naming no need type, which the header leaves uncompared;
#: an `inherits` on a cycle gives the same code, and is no case's to give.
_UNKNOWN_INHERITS = re.compile(
    r"WARNING: Need type '[^']+' inherits '[^']+', which is not a need type; "
    r"its inherits is ignored\. \[needs\.type_inherits\]"
)

#: The one code a reported filter carries, compared bare.
_FILTER_CODE = "filter"

#: The finding of a `c.is_a` literal naming no need type, which the header leaves
#: uncompared: the filter selects nothing, which `expected` compares.
_UNKNOWN_TYPE_CODE = "filter_type"
_CODE = re.compile(r"\[needs\.([a-z_]+)\]$")


def _corpus() -> list[dict[str, Any]]:
    with CORPUS_PATH.open("rb") as handle:
        return tomllib.load(handle)["case"]


CASES = _corpus()


def test_the_corpus_still_has_every_case() -> None:
    entries = sum(len(case["filters"]) for case in CASES)
    assert (len(CASES), entries) == (EXPECTED_CASE_COUNT, EXPECTED_FILTER_COUNT), (
        f"{CORPUS_PATH.name} carries {len(CASES)} cases and {entries} filters, expected "
        f"{EXPECTED_CASE_COUNT} and {EXPECTED_FILTER_COUNT}. Adding a case or a filter "
        "means raising the count; anything else means some were lost."
    )


def test_every_case_name_is_unique() -> None:
    names = Counter(case["name"] for case in CASES)
    assert [name for name, count in names.items() if count > 1] == []


def test_every_case_has_a_complete_expectation() -> None:
    """Every case says why and what it builds, and every entry the ids it selects, in
    order, with only the keys the header defines, each of its own shape."""
    for case in CASES:
        name = case["name"]
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), name
        assert set(case) <= _CASE_KEYS, name
        assert case["why"] and isinstance(case["config"], str) and case["source"], name
        assert not (case.get("python_only") and case.get("ubcode_only")), name
        assert case["filters"], name
        extensions = case.get("extensions", [])
        assert isinstance(extensions, list) and set(extensions) <= set(EXTENSIONS), name
        assert len(set(extensions)) == len(extensions), name
        if "srcdir" in case:
            # a subdirectory of the case directory, which the case's own
            # `ubproject.toml` names as its source directory, as ubCode reads it
            srcdir = case["srcdir"]
            assert srcdir and inside(srcdir) != Path(), name
            assert tomllib.loads(case["config"])["source"]["dir"] == srcdir, name
        seen: set[tuple[str, bool, bool]] = set()
        for entry in case["filters"]:
            where = f"{name}: {entry.get('filter')!r}"
            assert set(entry) <= _ENTRY_KEYS, where
            assert isinstance(entry["filter"], str) and entry["filter"], where
            # the same string twice in a case is a copy, unless it is evaluated otherwise
            key = (
                entry["filter"],
                entry.get("in_document", True),
                entry.get("include_parts", False),
            )
            assert key not in seen, where
            seen.add(key)
            expected = entry["expected"]
            assert all(isinstance(i, str) for i in expected), where
            assert expected == sorted(set(expected)), where
            assert entry.get("error", _FILTER_CODE) == _FILTER_CODE, where
            assert entry.get("tier", "fast") in _TIERS, where
            assert "reason" not in entry or entry.get("tier") == "eval", where
            # a constant selects nothing and is reported
            if entry.get("tier") == "refused":
                assert expected == [] and entry.get("error") == _FILTER_CODE, where
            assert entry.get("in_document", True) in (True, False), where
            assert entry.get("include_parts", False) in (True, False), where
            if "divergent" in entry:
                assert set(entry["divergent"]) == {"ubcode"}, where
                assert entry["divergent"]["ubcode"], where
            # an entry only sphinx-needs runs is not also a divergence of ubCode's
            assert not (entry.get("python_only") and entry.get("divergent")), where
            assert not (entry.get("python_only") and entry.get("ubcode_only")), where


def test_the_corpus_header_records_where_it_is_canonical() -> None:
    """ubCode's copy names this path; the header must keep saying this one is canonical."""
    header = CORPUS_PATH.read_text(encoding="utf-8")
    assert "packages/sphinx-needs/tests/fixtures/filter_conformance.toml" in header
    assert "THIS copy is CANONICAL" in header


def _files(case: Mapping[str, Any]) -> list[tuple[Path, str]]:
    """The case's project: its configuration, its document, its other files, and a
    ``.git`` where it loads sphinx-codelinks."""
    srcdir = case.get("srcdir")
    toml = "../" * len(PurePosixPath(srcdir).parts) if srcdir else ""
    toml += "ubproject.toml"
    loaded = case.get("extensions", [])
    template = CONF_PY.replace("{toml}", toml)
    if srcdir:
        template += "".join(
            EXTENSIONS[name].replace("{toml}", toml)
            for name in loaded
            if name in EXTENSIONS
        )
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


@contextmanager
def _eval_tier_only() -> Iterator[None]:
    """Every string is refused by the parsed tier, so it is answered through ``eval``."""
    refused = CompiledFilter(None, "refused", False)
    with patch.object(filter_common, "compile_portable", lambda _: refused):
        yield


def _outcome(answer: Callable[[], bool]) -> bool | str:
    """A need's answer: the boolean, or the message of the error the filter reports."""
    try:
        return answer()
    except NeedsInvalidFilter as error:
        return f"error: {error}"


def _check(app: Any, entry: dict[str, Any]) -> list[str]:
    """The problems with one entry; an empty list when it holds."""
    filter_string: str = entry["filter"]
    expected: list[str] = entry["expected"]
    origin = ORIGIN if entry.get("in_document", True) else None
    view = SphinxNeedsData(app.env).get_needs_view()
    config = NeedsSphinxConfig(app.config)
    problems: list[str] = []

    def problem(text: str) -> None:
        problems.append(f"{filter_string!r}: {text}")

    # the engine: its selection, and what it reports
    stream = app._warning
    start = len(stream.getvalue())
    if entry.get("include_parts"):
        items = list(view.to_list_with_parts())
        found = filter_needs_parts(
            view.to_list_with_parts(), config, filter_string, origin_docname=origin
        )
    else:
        items = list(view.values())
        found = filter_needs_view(view, config, filter_string, origin_docname=origin)
    selected = sorted(item["id_complete"] for item in found)
    if selected != expected:
        problem(f"selects {selected}, expected {expected}")
    reported = build_warnings(stream.getvalue()[start:], srcdir=app.srcdir)
    codes = [m[1] if (m := _CODE.search(w)) else w for w in reported]
    codes = [code for code in codes if code != _UNKNOWN_TYPE_CODE]
    want = [_FILTER_CODE] if entry.get("error") else []
    if codes != want:
        problem(f"reports {reported}, expected codes {want}")

    # the tier
    tier, reason = filter_common._filter_tier(filter_string)
    compiled = try_build_simple_predicate(filter_string) is not None
    if entry.get("tier") == "refused":
        if (tier, reason) != ("refused", None):
            problem(f"is answered by the {tier} tier, expected none (refused)")
    elif entry.get("tier") == "eval":
        if compiled or tier != "eval":
            problem(f"is answered by the {tier} tier, expected eval")
        elif "reason" in entry and reason != entry["reason"]:
            problem(f"falls to eval for {reason!r}, expected {entry['reason']!r}")
    else:
        if not compiled:
            problem(f"is refused by the parsed tier ({reason}), expected compiled")
        if tier != entry.get("tier", tier) or tier == "eval":
            problem(f"is answered by the {tier} tier, expected {entry.get('tier')}")

    # need by need: the parsed tier against eval, and against the engine
    def answers() -> dict[str, bool | str]:
        return {
            item["id_complete"]: _outcome(
                lambda item=item: filter_single_need(
                    item, config, filter_string, origin_docname=origin
                )
            )
            for item in items
        }

    parsed = answers()
    with _eval_tier_only():
        evaluated = answers()
    if (by_parsed := sorted(i for i, a in parsed.items() if a is True)) != expected:
        problem(f"selects {by_parsed} need by need, expected {expected}")
    for item_id, answer in parsed.items():
        if answer != evaluated[item_id]:
            problem(
                f"{item_id}: the parsed tier gives {answer!r}, eval {evaluated[item_id]!r}"
            )
    if entry.get("tier") == "refused":
        # refused before either tier runs, so both answer every need with the refusal
        refusal = f"error: {filter_common._constant_filter_message(filter_string)}"
        if (wrong := {i: a for i, a in evaluated.items() if a != refusal}) != {}:
            problem(f"is not refused need by need: {wrong}")
    return problems


def test_a_case_loading_sphinx_codelinks_is_a_git_checkout() -> None:
    """The runner writes the header's two ``.git`` files for a case loading
    sphinx-codelinks, its extensions into ``conf.py``, and, for a case whose ``srcdir``
    is a subdirectory, its ``conf.py`` and document there, every extension pointed at
    the ``ubproject.toml`` one directory up."""
    case = {
        "config": "[source]\ndir = 'docs'\n",
        "source": "",
        "srcdir": "docs",
        "extensions": ["sphinx_codelinks", "sphinx_test_reports"],
    }
    files = {path.as_posix(): text for path, text in _files(case)}
    assert set(files) == {
        "docs/conf.py",
        "docs/index.rst",
        "ubproject.toml",
        ".git/HEAD",
        ".git/config",
    }
    assert files[".git/HEAD"] == GIT_FILES[".git/HEAD"]
    assert files[".git/config"] == GIT_FILES[".git/config"]
    assert files["docs/conf.py"] == (
        "extensions = ['sphinx_needs', 'sphinx_codelinks', 'sphinx_test_reports']\n"
        'needs_from_toml = "../ubproject.toml"\n'
        'src_trace_config_from_toml = "../ubproject.toml"\n'
        'tr_config_from_toml = "../ubproject.toml"\n'
    )
    plain = {
        path.as_posix(): text for path, text in _files({"config": "", "source": ""})
    }
    assert set(plain) == {"conf.py", "index.rst", "ubproject.toml"}
    assert plain["conf.py"] == (
        "extensions = ['sphinx_needs']\nneeds_from_toml = \"ubproject.toml\"\n"
    )
    with pytest.raises(AssertionError, match="does not allow"):
        _files({"config": "", "source": "", "extensions": ["sphinx_mounts"]})


#: The cases red until sphinx-needs serves the ``source`` namespace.
_PINNED = frozenset(
    {
        "source-facets-of-page-include-import-and-external-needs",
        "source-facets-of-code-and-report-needs",
        "source-paths-are-relative-to-the-source-directory",
        "a-field-named-source-switches-the-facets-off",
    }
)


@pytest.mark.parametrize(
    "test_app,case",
    params(CASES, files=_files, skip=uninstalled_extension),
    indirect=["test_app"],
)
def test_case(
    test_app: Any, case: dict[str, Any], request: pytest.FixtureRequest
) -> None:
    if case["name"] in _PINNED:
        request.applymarker(
            pytest.mark.xfail(
                strict=True, reason="pinned before the source facets land"
            )
        )
    app = test_app
    app.build()
    # the project itself builds clean: a case whose configuration or document is not
    # read as written tests something else (the warnings a case may earn are the
    # deprecation of `filter_data`, which the residue's own filters read, the finding of
    # an `inherits` naming no need type, and that of a field named `source`, which
    # switches the facets off: configuration findings the header leaves uncompared)
    assert [
        w
        for w in build_warnings(app)
        if not w.endswith(_DEPRECATED)
        and not w.endswith(_SOURCE_SHADOWED)
        and not _UNKNOWN_INHERITS.fullmatch(w)
    ] == [], case["name"]
    problems = [
        problem
        for entry in case["filters"]
        if not entry.get("ubcode_only")
        for problem in _check(app, entry)
    ]
    assert problems == [], f"{case['name']}: {case['why']}"
