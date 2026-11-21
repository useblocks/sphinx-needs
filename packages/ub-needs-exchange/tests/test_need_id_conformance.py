"""The grammar of a need id, held to the shared conformance corpus.

``tests/fixtures/need_id_conformance.toml`` is the executable half of section 14 of
``design/exchange-contract.md``: how an id splits into a namespace and a local id at
``::``, how a namespace is parsed from its text, how a pair is joined, and the prefix that
joins an id to a namespace. This package
is its repository of record and ubCode is to vendor it, so every case is a statement both
tools are to be held to. Asserted here:

* every case of each of the four tables;
* the two laws of the module over every text the corpus holds -- ``join_id(*split_id(x))
  == x`` for every text, and ``split_id(join_id(ns, local)) == (ns, local)`` wherever
  ``join_id`` accepts the pair (for the empty namespace, wherever ``local`` does not
  itself split) -- and that splitting never raises;
* the two laws of ``namespace_prefix`` over every text and every namespace the corpus
  holds: where ``join_id(ns + xns, xlocal)`` accepts the split of a text, it is the prefix
  followed by the text; where it refuses, the prefix followed by the text is a plain id;
* the number of cases of each table, so that a trimmed corpus is a red test rather than
  quietly reduced coverage;
* the corpus's own form: unique names, only the keys of each table, pure ASCII.

The helpers are this module's own, as the other runners' are: each states the header it
implements. Standard library only, as the package is.
"""

from __future__ import annotations

import itertools
import re
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from ub_needs_exchange import (
    EMPTY_LOCAL,
    EMPTY_SEGMENT,
    SEGMENT_CHARACTER,
    SEPARATOR,
    format_namespace,
    id_problem,
    is_segment,
    join_id,
    namespace_prefix,
    parse_namespace,
    split_id,
)

CORPUS_PATH = Path(__file__).parent / "fixtures" / "need_id_conformance.toml"

#: The number of cases of each table.
#:
#: Raising one is the normal consequence of adding a case; lowering one needs a reason in
#: the commit message, and ubCode's vendored copy has to follow either way.
EXPECTED_CASE_COUNTS = {"split": 65, "namespace": 19, "join": 20, "prefix": 22}

#: The keys a case of each table may carry, as the header defines them: those it must,
#: and the alternative sets of which it carries exactly one.
REQUIRED_KEYS = {
    "split": {"name", "why", "id"},
    "namespace": {"name", "why", "text"},
    "join": {"name", "why", "namespace", "local"},
    "prefix": {"name", "why", "namespace"},
}
OUTCOME_KEYS = {
    "split": ({"namespace", "local"}, {"problem"}),
    "namespace": ({"segments"}, {"invalid"}),
    "join": ({"id"}, {"invalid"}),
    "prefix": ({"prefix"}, {"prefix", "id", "prefixed", "inside"}, {"invalid"}),
}

#: The problem classes the header defines.
PROBLEMS = {EMPTY_LOCAL, EMPTY_SEGMENT, SEGMENT_CHARACTER}


def _corpus() -> dict[str, list[dict[str, Any]]]:
    with CORPUS_PATH.open("rb") as handle:
        return tomllib.load(handle)


CORPUS = _corpus()
SPLIT = CORPUS.get("split", [])
NAMESPACE = CORPUS.get("namespace", [])
JOIN = CORPUS.get("join", [])
PREFIX = CORPUS.get("prefix", [])


def _texts() -> list[str]:
    """Every string the corpus holds: ids, local ids, namespace texts, segments and
    prefixes."""
    found: set[str] = set()
    for table in (SPLIT, NAMESPACE, JOIN, PREFIX):
        for case in table:
            for key, value in case.items():
                if key in {"name", "why"}:
                    continue
                if isinstance(value, str):
                    found.add(value)
                elif isinstance(value, list):
                    found.update(value)
    return sorted(found)


def _namespaces() -> list[tuple[str, ...]]:
    """Every namespace the corpus holds as segments: valid or not, empty or not."""
    found: set[tuple[str, ...]] = set()
    for case in SPLIT:
        found.add(tuple(case.get("namespace", ())))
    for case in NAMESPACE:
        if "segments" in case:
            found.add(tuple(case["segments"]))
    for case in (*JOIN, *PREFIX):
        found.add(tuple(case["namespace"]))
    return sorted(found)


TEXTS = _texts()
NAMESPACES = _namespaces()


# --- the corpus's own form -----------------------------------------------------------


def test_the_corpus_still_has_every_case() -> None:
    counts = {table: len(CORPUS.get(table, [])) for table in EXPECTED_CASE_COUNTS}
    assert counts == EXPECTED_CASE_COUNTS, (
        f"{CORPUS_PATH.name} carries {counts}, expected {EXPECTED_CASE_COUNTS}. Adding a "
        "case means raising EXPECTED_CASE_COUNTS; anything else means cases were lost."
    )


def test_the_corpus_has_only_its_four_tables() -> None:
    assert set(CORPUS) == set(EXPECTED_CASE_COUNTS)


def test_every_case_name_is_unique() -> None:
    names = Counter(case["name"] for table in CORPUS.values() for case in table)
    assert [name for name, count in names.items() if count > 1] == []


@pytest.mark.parametrize("table", sorted(EXPECTED_CASE_COUNTS))
def test_every_case_uses_only_the_keys_of_its_table(table: str) -> None:
    """The keys a table's case must carry, then exactly one of its two outcomes; a
    kebab-case name that starts with the table's name; a one-line ``why``; values of the
    type the header gives."""
    for case in CORPUS[table]:
        name = case["name"]
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), name
        assert name.startswith(f"{table}-"), name
        assert case["why"], name
        assert case["why"].splitlines() == [case["why"]], name
        rest = set(case) - REQUIRED_KEYS[table]
        assert REQUIRED_KEYS[table] <= set(case), name
        assert rest in OUTCOME_KEYS[table], name
        for key, value in case.items():
            if key in {"namespace", "segments"}:
                assert isinstance(value, list), name
                assert all(isinstance(item, str) for item in value), name
            elif key == "invalid":
                assert value is True, name
            elif key == "inside":
                assert isinstance(value, bool), name
            elif key == "problem":
                assert value in PROBLEMS, name
            else:
                assert isinstance(value, str), name
        if "id" in case:  # only a non-empty namespace puts its prefix before an id
            assert case["namespace"], name
            assert case["prefixed"] == case["prefix"] + case["id"], name


def test_the_corpus_file_is_pure_ascii() -> None:
    """Every non-ASCII or control character of a case is a ``\\u`` escape: the file's
    bytes are printable ASCII and line feeds, so no editor, platform or encoding guess
    can change what a case tests."""
    data = CORPUS_PATH.read_bytes()
    bad = sorted({byte for byte in data if not (0x20 <= byte < 0x7F or byte == 0x0A)})
    assert bad == []


def test_the_corpus_header_records_where_it_is_canonical() -> None:
    """ubCode's copy names this path; the header must keep saying this one is canonical."""
    header = CORPUS_PATH.read_text(encoding="ascii")
    assert (
        "packages/ub-needs-exchange/tests/fixtures/need_id_conformance.toml" in header
    )
    assert "THIS copy is CANONICAL" in header


# --- the cases -----------------------------------------------------------------------


@pytest.mark.parametrize("case", SPLIT, ids=[case["name"] for case in SPLIT])
def test_split(case: dict[str, Any]) -> None:
    text = case["id"]
    if "problem" in case:
        assert split_id(text) == ((), text)
        assert id_problem(text) == case["problem"]
    else:
        assert split_id(text) == (tuple(case["namespace"]), case["local"])
        assert id_problem(text) is None


@pytest.mark.parametrize("case", NAMESPACE, ids=[case["name"] for case in NAMESPACE])
def test_namespace(case: dict[str, Any]) -> None:
    text = case["text"]
    if "invalid" in case:
        with pytest.raises(ValueError):
            parse_namespace(text)
    else:
        segments = tuple(case["segments"])
        assert parse_namespace(text) == segments
        assert all(is_segment(segment) for segment in segments)
        assert format_namespace(parse_namespace(text)) == text


@pytest.mark.parametrize("case", JOIN, ids=[case["name"] for case in JOIN])
def test_join(case: dict[str, Any]) -> None:
    namespace = tuple(case["namespace"])
    if "invalid" in case:
        with pytest.raises(ValueError):
            join_id(namespace, case["local"])
    else:
        assert join_id(namespace, case["local"]) == case["id"]


@pytest.mark.parametrize("case", PREFIX, ids=[case["name"] for case in PREFIX])
def test_prefix(case: dict[str, Any]) -> None:
    namespace = tuple(case["namespace"])
    if "invalid" in case:
        with pytest.raises(ValueError):
            namespace_prefix(namespace)
        return
    prefix = namespace_prefix(namespace)
    assert prefix == case["prefix"]
    if "id" in case:
        prefixed = prefix + case["id"]
        assert prefixed == case["prefixed"]
        split_namespace = split_id(prefixed)[0]
        inside = split_namespace[: len(namespace)] == namespace
        assert inside == case["inside"]
        if not inside:  # outside means a plain id, not some other namespace
            assert split_namespace == ()
            assert id_problem(prefixed) is not None


# --- the laws, over every text the corpus holds --------------------------------------


@pytest.mark.parametrize("text", TEXTS, ids=[f"text-{i}" for i in range(len(TEXTS))])
def test_join_undoes_split(text: str) -> None:
    """``join_id(*split_id(x)) == x`` for EVERY text, and neither raises; the problem is
    set exactly when the text holds ``::`` and its split is the empty namespace."""
    namespace, local = split_id(text)
    assert join_id(namespace, local) == text
    problem = id_problem(text)
    assert (problem is not None) == (SEPARATOR in text and namespace == ())


def test_split_undoes_join() -> None:
    """``split_id(join_id(ns, local)) == (ns, local)`` for every namespace and every text
    of the corpus that ``join_id`` accepts, a non-empty namespace; for the empty namespace,
    where ``local`` does not itself split (``join_id`` gives any ``local`` back unchanged,
    so that the first law holds, and ``nc::X`` then splits)."""
    checked = 0
    for namespace, local in itertools.product(NAMESPACES, TEXTS):
        try:
            joined = join_id(namespace, local)
        except ValueError:
            continue
        if namespace == () and split_id(local)[0] != ():
            assert joined == local
            continue
        assert split_id(joined) == (namespace, local), (namespace, local)
        checked += 1
    assert checked > len(TEXTS)  # the positive control: most pairs were joined


def test_join_refuses_what_would_not_split_back() -> None:
    """The converse: with a non-empty namespace, ``join_id`` refuses exactly the pairs
    whose joined text would not split back to them."""
    for namespace, local in itertools.product(NAMESPACES, TEXTS):
        if namespace == ():
            continue
        joined = format_namespace(namespace) + SEPARATOR + local
        splits_back = split_id(joined) == (namespace, local)
        try:
            join_id(namespace, local)
        except ValueError:
            assert not splits_back, (namespace, local)
        else:
            assert splits_back, (namespace, local)


def test_the_prefix_joins_what_join_accepts() -> None:
    """``namespace_prefix(ns) + x == join_id(ns + xns, xlocal)`` for every namespace of
    the corpus the prefix accepts and every text of the corpus whose split joins under it,
    with ``(xns, xlocal) = split_id(x)``; and where ``join_id`` refuses, the prefixed text
    is a plain id, which splits to the empty namespace with a problem. Both counts are
    positive controls: some pairs join and some do not."""
    accepted = refused = 0
    for namespace, text in itertools.product(NAMESPACES, TEXTS):
        try:
            prefix = namespace_prefix(namespace)
        except ValueError:
            continue
        text_namespace, local = split_id(text)
        try:
            joined = join_id(namespace + text_namespace, local)
        except ValueError:
            assert namespace != (), (namespace, text)
            assert split_id(prefix + text) == ((), prefix + text), (namespace, text)
            assert id_problem(prefix + text) is not None, (namespace, text)
            refused += 1
        else:
            assert prefix + text == joined, (namespace, text)
            accepted += 1
    assert accepted > 0
    assert refused > 0


def test_the_prefix_refuses_exactly_what_join_refuses() -> None:
    """The prefix accepts a namespace exactly when ``join_id`` accepts it with a local id
    that joins any namespace (``X``), so the two never disagree about a segment."""
    for namespace in NAMESPACES:
        try:
            join_id(namespace, "X")
        except ValueError:
            with pytest.raises(ValueError):
                namespace_prefix(namespace)
        else:
            namespace_prefix(namespace)
