"""Pytest configuration and fixtures for the sphinx-needs suite.

The Sphinx application lifecycle (``test_app`` and the temporary directories it builds
in), the PlantUML renderer resolution, the warning normalisation and the doctree snapshot
extension are NOT here: they are the workspace's, in ``packages/sphinx-needs-testkit``,
because sphinx-mounts' and sphinx-codelinks' suites need the same things and used to carry
their own copies. The plugin line below is how this suite asks for them, and the two
fixtures under it are what that plugin deliberately does not know: where this suite's test
projects live, and what a build of one of them must assert.

Everything else in this file is sphinx-needs' own -- the parent-child doctree invariant,
the ``fixture_file`` marker's parametrisation, and the two project builders.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
import yaml
from _pytest.mark import ParameterSet
from docutils.nodes import document
from sphinx.application import Sphinx
from sphinx.testing.util import SphinxTestApp

from sphinx_needs._jinja import render_template_string
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


@pytest.fixture(scope="session")
def test_app_events() -> Sequence[tuple[str, Callable[..., object], int]]:
    """What every ``test_app`` build in THIS suite asserts, over and above the test.

    The parent-child check runs after any other handler of ``doctree-resolved``, hence the
    priority: placing it here gives coverage to a large part of the suite, and to whatever
    is added to it next.
    """
    return (("doctree-resolved", _check_parent_child, 999),)


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
