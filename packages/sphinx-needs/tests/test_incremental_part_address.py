"""An incremental build follows a value copied from a part's address, the whole id first.

A ``copy`` given an address (a rule's ``from``, the ``need_id`` of an inline ``copy``)
reads the need whose id is the address as written when there is one -- a need's id may
hold a ``.`` -- and else the need of the part the address names. The page of the need
holding the copy shows the value, so an incremental build re-writes that page when the
need the copy read changes, whichever of the two it is, and when a need under the whole
address appears or goes away in another document (the copy then reads another need).

The oracle is a fresh build: after each edit, the incremental build's pages are those a
fresh build of the same sources writes. The reader's page never changes; the needs it
reads are on other pages.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings

#: the copies, as derive rules
RULE_CONF = """\
extensions = ["sphinx_needs"]
needs_fields = {
    "owner": {"schema": {"type": "string"}},
    "from_part": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "owner", "from": "REQ_1.p1"},
    },
    "from_dotted": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "owner", "from": "DOT_1.x"},
    },
}
"""
#: the copies, as inline calls
INLINE_CONF = """\
extensions = ["sphinx_needs"]
needs_fields = {
    "owner": {"schema": {"type": "string"}},
    "from_part": {"schema": {"type": "string"}},
    "from_dotted": {"schema": {"type": "string"}},
}
"""
INLINE_CALLS = (
    '   :from_part: [[copy("owner", "REQ_1.p1")]]\n'
    '   :from_dotted: [[copy("owner", "DOT_1.x")]]\n'
)

INDEX = "Index\n=====\n\n.. toctree::\n\n   reqs\n   reader\n   others\n"


def _reqs(owner: str = "alice", dotted_owner: str = "bob") -> str:
    """``REQ_1`` with its part ``p1``, and ``DOT_1.x``, a need whose id holds a dot."""
    return (
        "Reqs\n====\n\n"
        f".. req:: With a part\n   :id: REQ_1\n   :owner: {owner}\n\n"
        "   Text :np:`(p1) the part`.\n\n"
        f".. req:: Dotted\n   :id: DOT_1.x\n   :owner: {dotted_owner}\n"
    )


def _reader(calls: str) -> str:
    return f"Reader\n======\n\n.. spec:: Reads\n   :id: SPEC_1\n{calls}"


def _others(twin: bool = False) -> str:
    """Another document; with ``twin``, a need whose id is the part's address."""
    text = "Others\n======\n\n.. req:: Other\n   :id: REQ_2\n"
    if twin:
        text += "\n.. req:: Twin\n   :id: REQ_1.p1\n   :owner: zed\n"
    return text


def _project(
    form: str, owner: str = "alice", dotted_owner: str = "bob", twin: bool = False
) -> dict[str, str]:
    return {
        "conf.py": RULE_CONF if form == "rule" else INLINE_CONF,
        "index.rst": INDEX,
        "reqs.rst": _reqs(owner, dotted_owner),
        "reader.rst": _reader("" if form == "rule" else INLINE_CALLS),
        "others.rst": _others(twin),
    }


#: each state: the edit, as the project before and after it
STATES: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    # the control: the part's need changed
    "s1-part-need-changed": ({}, {"owner": "alice2"}),
    # the need whose id holds a dot changed
    "s5-dotted-need-changed": ({}, {"dotted_owner": "bob2"}),
    # a need whose id is the part's address added in another document
    "s6-twin-added": ({}, {"twin": True}),
    # that need removed again
    "s7-twin-removed": ({"twin": True}, {}),
}


def _write(srcdir: Path, pages: dict[str, str]) -> Path:
    """Write the project; a file whose text is the same is left untouched, so that
    Sphinx, which compares modification times, sees only the edited page changed."""
    srcdir.mkdir(parents=True, exist_ok=True)
    for name, text in pages.items():
        path = srcdir / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
    return srcdir


def _build(
    make_app: Callable[..., SphinxTestApp], srcdir: Path, *, fresh: bool
) -> list[str]:
    app = make_app("html", srcdir=srcdir, freshenv=fresh)
    try:
        app.build()
        return build_warnings(app)
    finally:
        app.cleanup()


_BODY = re.compile(
    r'<div class="body" role="main">(.*?)<div class="sphinxsidebar"', re.DOTALL
)
#: The id of a need's container, which hashes where the project is
_CONTAINER_ID = re.compile(r"SNCB-[0-9a-f]+")


def _reader_page(srcdir: Path) -> str:
    text = (srcdir / "_build" / "html" / "reader.html").read_text(encoding="utf-8")
    match = _BODY.search(text)
    assert match is not None
    return _CONTAINER_ID.sub("SNCB-", match.group(1))


@pytest.mark.parametrize("form", ["rule", "inline"])
@pytest.mark.parametrize("state", STATES)
def test_the_reader_page_follows_the_need_its_copy_reads(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, form: str, state: str
) -> None:
    """After the edit, the reader's page is the page a fresh build writes."""
    before, after = STATES[state]
    incremental = _write(tmp_path / "incremental", _project(form, **before))
    assert _build(make_app, incremental, fresh=True) == []
    shown_before = _reader_page(incremental)
    _write(incremental, _project(form, **after))
    _build(make_app, incremental, fresh=False)

    fresh = _write(tmp_path / "fresh", _project(form, **after))
    assert _build(make_app, fresh, fresh=True) == []
    expected = _reader_page(fresh)
    # the edit changes what the reader shows, so a page left as it was is stale
    assert expected != shown_before
    assert _reader_page(incremental) == expected, "the reader's page was not re-written"


EXTEND_CONF = """\
extensions = ["sphinx_needs"]
needs_fields = {"owner": {"schema": {"type": "string"}}}
"""
EXTEND_INDEX = "Index\n=====\n\n.. toctree::\n\n   reqs\n   extends\n"


def _extend_project(target: str, owner: str) -> dict[str, str]:
    """``needextend`` by id in a document of its own, naming ``target``."""
    return {
        "conf.py": EXTEND_CONF,
        "index.rst": EXTEND_INDEX,
        "reqs.rst": _reqs(),
        "extends.rst": f"Extends\n=======\n\n.. needextend:: {target}\n"
        f"   :owner: {owner}\n",
    }


def _page(srcdir: Path, name: str) -> str:
    text = (srcdir / "_build" / "html" / f"{name}.html").read_text(encoding="utf-8")
    match = _BODY.search(text)
    assert match is not None
    return _CONTAINER_ID.sub("SNCB-", match.group(1))


@pytest.mark.parametrize("target", ["REQ_1", "DOT_1.x"])
def test_the_page_of_a_need_an_extend_names_follows_the_extend(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, target: str
) -> None:
    """A ``needextend`` names its need by the whole id, a ``.`` in it or not: when the
    extend changes, the page of the need it names is re-written (``REQ_1`` is the
    control)."""
    incremental = _write(tmp_path / "incremental", _extend_project(target, "ext1"))
    assert _build(make_app, incremental, fresh=True) == []
    shown_before = _page(incremental, "reqs")
    _write(incremental, _extend_project(target, "ext2"))
    _build(make_app, incremental, fresh=False)

    fresh = _write(tmp_path / "fresh", _extend_project(target, "ext2"))
    assert _build(make_app, fresh, fresh=True) == []
    expected = _page(fresh, "reqs")
    assert expected != shown_before
    assert _page(incremental, "reqs") == expected, "the need's page was not re-written"


EXTEND_COPY_INDEX = "Index\n=====\n\n.. toctree::\n\n   reqs\n   extends\n   others\n"


def _extend_copy_project(target: str, owner: str) -> dict[str, str]:
    """``needextend`` by id naming ``target``, which sets its ``owner`` to a copy of
    ``REQ_2``'s; ``REQ_2`` is in a third document."""
    return {
        "conf.py": EXTEND_CONF,
        "index.rst": EXTEND_COPY_INDEX,
        "reqs.rst": _reqs(),
        "extends.rst": f"Extends\n=======\n\n.. needextend:: {target}\n"
        '   :owner: [[copy("owner", "REQ_2")]]\n',
        "others.rst": "Others\n======\n\n.. req:: Other\n   :id: REQ_2\n"
        f"   :owner: {owner}\n",
    }


@pytest.mark.parametrize("target", ["REQ_1", "DOT_1.x"])
def test_the_page_of_a_need_an_extend_names_follows_what_the_extend_reads(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, target: str
) -> None:
    """A value a ``needextend`` by id sets with a dynamic function is computed on the
    need the extend names, by the whole id: when the need that function reads changes
    in another document, the page of the extended need is re-written (``REQ_1`` is the
    control)."""
    incremental = _write(tmp_path / "incremental", _extend_copy_project(target, "two1"))
    assert _build(make_app, incremental, fresh=True) == []
    shown_before = _page(incremental, "reqs")
    _write(incremental, _extend_copy_project(target, "two2"))
    _build(make_app, incremental, fresh=False)

    fresh = _write(tmp_path / "fresh", _extend_copy_project(target, "two2"))
    assert _build(make_app, fresh, fresh=True) == []
    expected = _page(fresh, "reqs")
    assert expected != shown_before
    assert _page(incremental, "reqs") == expected, "the need's page was not re-written"
