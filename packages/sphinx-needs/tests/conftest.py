"""Pytest configuration and fixtures for the sphinx-needs suite.

The Sphinx application lifecycle (``test_app`` and the temporary directories it builds
in), the PlantUML renderer resolution, the warning normalisation and the doctree snapshot
extension are NOT here: they are the workspace's, in ``packages/sphinx-needs-testkit``,
because sphinx-mounts' and sphinx-codelinks' suites need the same things and used to carry
their own copies. The plugin line below is how this suite asks for them, and the two
fixtures under it are what that plugin deliberately does not know: where this suite's test
projects live, and what a build of one of them must assert.

Everything else in this file is sphinx-needs' own -- the parent-child doctree invariant,
the fence on every need's source hops, the ``fixture_file`` marker's parametrisation, and
the two project builders.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path, PurePath

import pytest
import yaml
from _pytest.mark import ParameterSet
from docutils.nodes import document
from docutils.statemachine import string2lines
from sphinx.application import Sphinx
from sphinx.testing.util import SphinxTestApp

import sphinx_needs.needs
from sphinx_needs._jinja import render_template_string
from sphinx_needs._need_source import (
    SRCDIR_ROOT,
    NeedSourceHop,
    placement_index,
    project_legacy,
)
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.need_item import NeedItem, NeedItemSource
from sphinx_needs.nodes import Need
from sphinx_needs_testkit import make_plantuml_inert

# The order is load-bearing, not alphabetical: `sphinx.testing.fixtures` defines a
# `sphinx_test_tempdir` of its own, the testkit overrides it (this suite builds in one
# named directory that `--sn-build-dir` can move), and where two plugins define a fixture
# at the same level the one registered LAST wins. Measured: with sphinx's second, every
# test still passes and the whole suite quietly builds in pytest's session tempdir
# instead, with `--sn-build-dir` inert.
pytest_plugins = ["sphinx.testing.fixtures", "sphinx_needs_testkit.fixtures"]

THIS_DIR = Path(__file__).parent


@pytest.fixture(scope="session")
def tests_dir() -> Path:
    """This suite's own ``tests`` directory, which a relative ``srcdir`` resolves against.

    The testkit's, to be given: it is shared by three suites and lives beside none of
    their trees of test projects.
    """
    return THIS_DIR


# node classes from extensions outside sphinx-needs are exempt from the parent check:
# sphinx-design installs its tab nodes by assigning ``children`` directly, so they never get
# a parent (#1757), and the invariant guarded here (#1564) is about sphinx-needs' own nodes
_PARENT_CHECK_EXEMPT_MODULES = ("sphinx_design.",)


def _check_parent_child(app: Sphinx, doctree: document, docname: str):
    for idx, node in enumerate(doctree.findall()):
        if idx == 0:
            continue
        if type(node).__module__.startswith(_PARENT_CHECK_EXEMPT_MODULES):
            continue
        assert node.parent is not None, (
            f"{docname}: <{type(node).__name__}> has no parent"
        )


def _check_declared_config(app: Sphinx, exception: Exception | None) -> None:
    """Sphinx's configuration holds the declared options alone: a ``needs_*`` attribute
    that is no declared value is state a build wrote there (#2402), which a ``conf.py``
    could set and Sphinx pickles. What a build stores elsewhere (on the environment, say)
    is out of this check's reach. ``name in config`` asks Sphinx for its declared
    values, its own ``needs_sphinx`` and ``needs_extensions`` included."""
    if exception is not None:
        return
    undeclared = sorted(
        k for k in vars(app.config) if k.startswith("needs_") and k not in app.config
    )
    assert undeclared == [], (
        f"undeclared needs_* values on Sphinx's Config: {undeclared}"
    )


@pytest.fixture(scope="session")
def test_app_events() -> Sequence[tuple[str, Callable[..., object], int]]:
    """What every ``test_app`` build in THIS suite asserts, over and above the test.

    The parent-child check runs after any other handler of ``doctree-resolved``, hence the
    priority: placing it here gives coverage to a large part of the suite, and to whatever
    is added to it next. The configuration check runs after every other handler of
    ``build-finished``, so it sees what the whole build wrote.
    """
    return (
        ("doctree-resolved", _check_parent_child, 999),
        ("build-finished", _check_declared_config, 999),
    )


#: what the first line of a need's text is: a directive's marker, reStructuredText or
#: MyST (backticks, tildes or colons), or the item of a ``list2need`` (whose ``*`` needs
#: no space after it); after a MyST block quote's ``>``, an rst grid cell's ``|``, or
#: the bullets of the list item the directive opens
_TEXT_START = re.compile(
    r"\s*([>|]\s*|(?:[-+]|#\.|\d+[.)])\s+)*"
    r"(\.\. [\w:.-]+::|(`{3,}|~{3,}|:{3,})\s*\{[\w:.-]+\}|\*)"
)


@pytest.fixture(autouse=True, scope="session")
def _need_source_fence() -> Iterator[None]:
    """The fence on every need's source hops, in every build of this suite.

    It wraps the doctree-read walk that ``setup()`` connects (``analyse_need_locations``,
    looked up by name when each application is set up, so every application of the
    session is covered, in every xdist worker) and checks each need the walk visits:

    - a source of sphinx-needs' own class carries hops;
    - the legacy ``sections`` and ``signature`` the walk writes equal the projection of
      the placement hop's semantic location, which the walk computes from the doctree on
      its own (:func:`~sphinx_needs._need_source.placement_semantic`), for every need;
    - the ``parent_needs`` the walk writes name the nearest need node enclosing the need's
      node, read from the doctree before the walk (:func:`_enclosing_need`), or nothing;
    - every hop with a path has the one root, ``srcdir``, and a relative path;
    - the walk changes the placement hop alone, and only its ``semantic`` (unset before);
    - lines point at text: every hop under the ``srcdir`` root names a file that exists,
      and where it has a ``start_line``, that line holds the directive's marker or the
      list item, and its ``end_line`` a non-blank line at or after it.
    """
    original = sphinx_needs.needs.analyse_need_locations

    def fenced(app: Sphinx, doctree: document) -> None:
        needs = SphinxNeedsData(app.env).get_needs_mutable()
        walked = {
            node["refid"]: needs[node["refid"]]
            for node in doctree.findall(Need)
            if node["refid"] in needs
        }
        before = {
            need_id: need.source.hops
            for need_id, need in walked.items()
            if isinstance(need.source, NeedItemSource)
        }
        # sphinx-needs' own source class carries hops; a third party's need not
        lacking = [
            need_id
            for need_id, need in walked.items()
            if need_id not in before
            and type(need.source).__module__ == NeedItem.__module__
        ]
        assert not lacking, f"sources without hops: {lacking}"
        # read before the walk, which takes the hidden needs out of the doctree
        enclosing = {
            node["refid"]: _enclosing_need(node) for node in doctree.findall(Need)
        }
        original(app, doctree)
        wrong_parents = {
            need_id: (need["parent_needs"], enclosing[need_id])
            for need_id, need in walked.items()
            if list(need["parent_needs"]) != enclosing[need_id]
        }
        assert not wrong_parents, f"parent_needs (walked, enclosing): {wrong_parents}"
        files: dict[Path, list[str]] = {}
        for need_id, hops in before.items():
            _check_need_source(app, walked[need_id], hops, files)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sphinx_needs.needs, "analyse_need_locations", fenced)
        yield


def _enclosing_need(node: Need) -> list[str]:
    """The id of the nearest need node above this one, as a one-item list, or ``[]``.

    The whole of what ``parent_needs`` means, read from the doctree alone and
    independently of the walk: a need is the child of the need whose content holds it,
    wherever it sits in that content, hidden or not (#2398).
    """
    parent = node.parent
    while parent is not None:
        if isinstance(parent, Need):
            return [parent["refid"]]
        parent = parent.parent
    return []


def _check_need_source(
    app: Sphinx,
    need: NeedItem,
    before: tuple[NeedSourceHop, ...],
    files: dict[Path, list[str]],
) -> None:
    """The checks of :func:`_need_source_fence` on one walked need."""
    source = need.source
    assert isinstance(source, NeedItemSource)
    after = source.hops
    where = f"{need.id}: {after!r}"
    index = placement_index(after)
    if index is None:
        assert after == before, where
        return
    semantic = after[index].semantic
    assert semantic is not None, where
    assert project_legacy(semantic) == (
        tuple(need["sections"]),
        need["signature"],
    ), where
    assert len(after) == len(before), where
    for position, (old, new) in enumerate(zip(before, after, strict=True)):
        if position == index:
            assert old.semantic is None, where
            assert new == dataclasses.replace(old, semantic=new.semantic), where
        else:
            assert new == old, where
    for hop in after:
        physical = hop.physical
        if physical is None or physical.path is None:
            continue
        # R6: one root, and a path relative to it
        assert physical.root == SRCDIR_ROOT, where
        assert not PurePath(physical.path).is_absolute(), where
        file = Path(app.srcdir, physical.path)
        assert file.is_file(), f"{where}: no file {file}"
        if physical.start_line is None:
            assert physical.end_line is None, where
            continue
        if file not in files:
            # read as the product reads it: the project's encoding (a BOM stripped),
            # split as docutils numbers lines
            files[file] = string2lines(
                file.read_text(encoding=app.config.source_encoding),
                tab_width=app.env.settings.get("tab_width", 8),
                convert_whitespace=True,
            )
        lines = files[file]
        assert 1 <= physical.start_line <= len(lines), where
        assert _TEXT_START.match(lines[physical.start_line - 1]), (
            f"{where}: line {physical.start_line} is {lines[physical.start_line - 1]!r}"
        )
        if physical.end_line is not None:
            assert physical.start_line <= physical.end_line <= len(lines), where
            assert lines[physical.end_line - 1].strip(), where


@pytest.fixture
def make_app(make_app):
    """``sphinx.testing``'s ``make_app``, with this suite's PlantUML policy on every app.

    ONE RULE, and it is the whole of this fixture: **no build in this suite renders with
    sphinxcontrib-plantuml's default command**, which is the bare word ``plantuml`` --
    i.e. whatever unpinned renderer the developer's machine happens to carry, or nothing
    at all on a CI runner. ``test_app`` says that for its own builds; a third of this
    suite's Sphinx applications are made here instead, and two of those modules were
    measured drawing six diagrams with a homebrew PlantUML 1.2026.1 against the 1.2026.8
    this repository pins.

    A build that HAS chosen a renderer -- in its ``confoverrides``, or in the ``conf.py``
    its project writes, which is how the needflow conformance corpus does it -- is left
    exactly as it was. That is the difference between this and a blanket "make_app never
    renders": the corpus renders on purpose, and a render failure there is a warning its
    harness refuses.

    :func:`sphinx_needs_testkit.plantuml_conf` is how a test chooses one lazily, so a
    parametrisation that draws nothing never needs a jar.
    """

    def _make_app(*args, **kwargs):
        app = make_app(*args, **kwargs)
        # sphinxcontrib-plantuml's own default, as it registers it (`add_config_value`)
        if getattr(app.config, "plantuml", None) == "plantuml":
            make_plantuml_inert(app)
        return app

    return _make_app


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Generate tests for a ``@pytest.mark.fixture_file`` decorator."""
    for marker in metafunc.definition.iter_markers(name="fixture_file"):
        params = create_parameters(*marker.args, **marker.kwargs)
        metafunc.parametrize(argnames="content", argvalues=params)


def create_parameters(
    *rel_paths: str, skip_files: list[str] | None = None
) -> list[ParameterSet]:
    """Create parameters for a pytest param_file decorator."""
    paths: list[Path] = []
    for rel_path in rel_paths:
        assert not Path(rel_path).is_absolute()
        path = THIS_DIR.joinpath(rel_path)
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(path.glob("*.yaml"))
        else:
            raise FileNotFoundError(f"File / folder not found: {path}")

    if skip_files:
        paths = [
            path for path in paths if str(path.relative_to(THIS_DIR)) not in skip_files
        ]

    if not paths:
        raise FileNotFoundError(f"No files found: {rel_paths}")

    if len(paths) == 1:
        with paths[0].open(encoding="utf8") as f:
            try:
                data = yaml.safe_load(f)
            except Exception as err:
                raise OSError(f"Error loading {paths[0]}") from err
        return [pytest.param(value, id=id) for id, value in data.items()]
    else:
        params: list[ParameterSet] = []
        for subpath in paths:
            with subpath.open(encoding="utf8") as f:
                try:
                    data = yaml.safe_load(f)
                except Exception as err:
                    raise OSError(f"Error loading {subpath}") from err
            for key, value in data.items():
                params.append(
                    pytest.param(
                        value,
                        id=f"{subpath.relative_to(THIS_DIR).with_suffix('').as_posix()}-{key}",
                    )
                )
        return params


@pytest.fixture
def write_fixture_files():
    def _inner(tmp: Path, content: dict[str, str]) -> None:
        section_file_mapping: dict[str, Path] = {
            "conf": tmp / "conf.py",
            "ubproject": tmp / "ubproject.toml",
            "rst": tmp / "index.rst",
            "schemas": tmp / "schemas.json",
        }
        for section, file_path in section_file_mapping.items():
            if section in content:
                if isinstance(content[section], dict):
                    # used for schemas.json
                    file_path.write_text(
                        json.dumps(content[section], indent=2), encoding="utf-8"
                    )
                elif isinstance(content[section], str):
                    file_path.write_text(content[section], encoding="utf-8")
                else:
                    raise ValueError(
                        f"Unsupported content type for section '{section}': {type(content[section])}"
                    )

    return _inner


@pytest.fixture
def schema_benchmark_app(tmpdir: Path, request: pytest.SubRequest, make_app):
    """Fixture to create a schema benchmark Sphinx project."""
    need_cnt: int = request.param

    assert need_cnt % 10 == 0, "need_cnt must be a multiple of 10"
    page_cnt = int(need_cnt / 10)

    this_file_dir = Path(__file__).parent

    src_dir = this_file_dir / "doc_test" / "doc_schema_benchmark"
    page_template_path = src_dir / "page.rst.j2"
    with page_template_path.open() as fp:
        template_content = fp.read()

    pages_dir = Path(tmpdir) / "pages"
    pages_dir.mkdir(exist_ok=True)
    toctree_content = """
.. toctree::
    :maxdepth: 2

"""
    width = len(str(page_cnt))
    for i in range(1, page_cnt + 1):
        i_fmt = f"{i:0{width}d}"
        page_rst_content = render_template_string(
            template_content, {"page_nr": i_fmt}, autoescape=False
        )

        page_name = f"page_{i_fmt}"
        page_file = f"{page_name}.rst"
        page_rst_path = pages_dir / page_file
        page_rst_path.write_text(page_rst_content, encoding="utf-8")
        toctree_content += f"   pages/{page_name}\n"

    index_file = tmpdir / "index.rst"
    index_file.write_text(toctree_content, encoding="utf-8")

    copy_files = [
        src_dir / "conf.py",
        src_dir / "schemas.json",
        src_dir / "ubproject.toml",
    ]
    for copy_file in copy_files:
        dst_file = tmpdir / copy_file.name
        dst_file.write_text(copy_file.read_text(), encoding="utf-8")

    app: SphinxTestApp = make_app(
        # the schema builder does only validate, no output
        buildername="schema",
        srcdir=Path(tmpdir),
        freshenv=True,
    )
    yield app
    app.cleanup()
