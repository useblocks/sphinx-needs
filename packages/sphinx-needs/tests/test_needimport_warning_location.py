"""``needimport``'s own warnings name the file and line it is written on (#2463).

Four of its warning sites reported at ``(docname, self.lineno)``: the page, with the
parser's running line. Below an ``rst_prolog`` or an include that line is shifted, and in
an included file it names the HOST page. Each warning now names the file the directive is
written in and the line the needs it imports record (``lineno``, since #2461), so the two
agree -- in a ``:start-line:`` include too, where the parser's line is the slice's.

The project has one placement per row, each with a ``needimport`` that imports a need and
triggers three of the sites (a record that is not an object, an absent id in ``:ids:``, a
``:filter:`` that fails on one record), and one naming a missing file (the fourth, the
refusal). A MyST page is the control: its warnings were already right. The build runs
from the source directory, where an included file's path is relative.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

CONF = '''\
extensions = ["sphinx_needs", "myst_parser"]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
exclude_patterns = ["_build", "incl_*"]
rst_prolog = """
.. |p1| replace:: prolog one
.. |p2| replace:: prolog two
"""
'''

INDEX = """\
Needimport warnings
===================

.. toctree::

   below
   inc_host
   slice_host
   myst
"""


def _rst_directives(tag: str) -> str:
    return f"""\
.. needimport:: /imp_{tag}.json
   :id_prefix: {tag.upper()}_
   :ids: IMP_1, IMP_2, NOPE_{tag.upper()}
   :filter: title.startswith("ok") or undefined_{tag}

.. needimport:: /missing_{tag}.json
"""


SEVEN_LINES = "".join(f"Included line {n}.\n" for n in range(1, 8))

FILES: dict[str, str] = {
    "conf.py": CONF,
    "index.rst": INDEX,
    # below an rst_prolog and a 7-line include
    "block7.txt": SEVEN_LINES,
    "below.rst": "Below an include\n================\n\n.. include:: block7.txt\n\n"
    + _rst_directives("b"),
    # inside a plain include
    "inc_host.rst": "Inside an include\n=================\n\nHost paragraph.\n\n"
    ".. include:: incl_body.rst\n",
    "incl_body.rst": "Included text.\n\n" + _rst_directives("i"),
    # inside an include sliced by :start-line:
    "slice_host.rst": "Inside a sliced include\n=======================\n\n"
    ".. include:: incl_slice.rst\n   :start-line: 3\n",
    "incl_slice.rst": "Sliced off one.\nSliced off two.\nSliced off three.\n\n"
    "Kept text.\n\n" + _rst_directives("s"),
    # the control: a MyST page
    "myst.md": """\
# MyST page

Some text.

```{needimport} /imp_m.json
:id_prefix: M_
:ids: IMP_1, IMP_2, NOPE_M
:filter: title.startswith("ok") or undefined_m
```

```{needimport} /missing_m.json
```
""",
}

for _tag in "bism":
    FILES[f"imp_{_tag}.json"] = json.dumps(
        {
            "current_version": "1.0",
            "versions": {
                "1.0": {
                    "needs": {
                        "IMP_1": {"id": "IMP_1", "type": "req", "title": "ok one"},
                        "IMP_2": {"id": "IMP_2", "type": "req", "title": "two"},
                        "BAD": 1,
                    }
                }
            },
        }
    )

PLACEMENTS = {
    # placement: (its tag, the file its directives are written in)
    "after-prolog-and-include": ("b", "below.rst"),
    "inside-include": ("i", "incl_body.rst"),
    "inside-start-line-include": ("s", "incl_slice.rst"),
    "myst-page": ("m", "myst.md"),
}

SITES = {
    # site: text only its message has
    "diagnostic": "is not an object",
    "ids": "has no needs with the ids",
    "filter": "not valid",
    "refusal": "Could not load needs import file",
}


def _line(file: str, text: str) -> int:
    """The 1-based line of ``file`` that starts with ``text``."""
    lines = FILES[file].splitlines()
    (index,) = [i for i, line in enumerate(lines) if line.startswith(text)]
    return index + 1


def _written_lines(placement: str) -> tuple[int, int]:
    """The lines the placement's two directives are written on: the importing one, and
    the one naming a missing file."""
    tag, file = PLACEMENTS[placement]
    opener = "```{needimport}" if file.endswith(".md") else ".. needimport::"
    return (
        _line(file, f"{opener} /imp_{tag}.json"),
        _line(file, f"{opener} /missing_{tag}.json"),
    )


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[dict[tuple[str, str], list[str]], list[str], dict[str, str]]]:
    """The project, built once: each ``(placement, site)``'s warning locations, the
    warnings no placement and site claims, and where each imported need is written
    (``<srcdir>/<file>:<lineno>``)."""
    srcdir = tmp_path_factory.mktemp("needimport_locations") / "docs"
    srcdir.mkdir()
    for name, text in FILES.items():
        (srcdir / name).write_text(text, encoding="utf-8")
    app = SphinxTestApp(
        "html",
        srcdir=srcdir,
        freshenv=True,
        status=io.StringIO(),
        warning=io.StringIO(),
    )
    try:
        # built from the source directory, as a project usually is: docutils then
        # records an included file relative to the working directory, which the
        # warning must make absolute again, as Sphinx does for a node's location
        with pytest.MonkeyPatch.context() as patch:
            patch.chdir(srcdir)
            app.build()
        locations: dict[tuple[str, str], list[str]] = {}
        unclaimed: list[str] = []
        for warning in build_warnings(app):
            location, _, message = warning.partition(": WARNING: ")
            claims = [
                (placement, site)
                for placement, (tag, _) in PLACEMENTS.items()
                if f"_{tag}.json" in message or f"undefined_{tag}" in message
                for site, text in SITES.items()
                if text in message
            ]
            if len(claims) == 1:
                locations.setdefault(claims[0], []).append(location)
            else:
                unclaimed.append(warning)
        needs = SphinxNeedsData(app.env).get_needs_view()
        written: dict[str, str] = {}
        for placement, (tag, _) in PLACEMENTS.items():
            need = needs[f"{tag.upper()}_IMP_1"]
            # the hop after the imported file's: the file the directive is written in
            (file_hop, *_) = [
                hop.physical.path
                for hop in need.source.hops[1:]
                if hop.physical is not None and hop.physical.path
            ]
            written[placement] = f"<srcdir>/{file_hop}:{need['lineno']}"
        yield locations, unclaimed, written
    finally:
        app.cleanup()


def test_every_warning_is_one_placement_s_and_one_site_s(built) -> None:
    """The control: the project's warnings are exactly one per placement and site."""
    locations, unclaimed, _ = built
    assert unclaimed == []
    assert {key: len(found) for key, found in locations.items()} == {
        (placement, site): 1 for placement in PLACEMENTS for site in SITES
    }


@pytest.mark.parametrize("placement", PLACEMENTS)
def test_the_imported_need_records_the_written_line(built, placement: str) -> None:
    """The control (#2461): the imported need records the file and line its directive
    is written on."""
    _, file = PLACEMENTS[placement]
    importing, _ = _written_lines(placement)
    assert built[2][placement] == f"<srcdir>/{file}:{importing}"


@pytest.mark.parametrize("site", SITES)
@pytest.mark.parametrize("placement", PLACEMENTS)
def test_a_needimport_warning_names_the_written_line(
    built, placement: str, site: str
) -> None:
    """Each site's warning names the file and line the directive is written on: for
    the importing directive, the place its need records."""
    locations, _, written = built
    _, file = PLACEMENTS[placement]
    importing, missing = _written_lines(placement)
    if site == "refusal":
        assert locations.get((placement, site)) == [f"<srcdir>/{file}:{missing}"]
    else:
        assert locations.get((placement, site)) == [written[placement]]
        assert written[placement] == f"<srcdir>/{file}:{importing}"
