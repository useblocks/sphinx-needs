"""``incdir`` on generated PlantUML nodes must name the *physical* source dir.

``sphinxcontrib-plantuml`` starts the PlantUML process with
``cwd = os.path.join(srcdir, node["incdir"])``, so ``incdir`` decides where
relative ``!include`` paths are resolved. Deriving it from the *logical* docname
breaks for any document whose source file does not physically live under
``srcdir`` -- e.g. a document contributed by ``sphinx-mounts``, which registers
an absolute external path for its docname. PlantUML then gets a non-existent
``cwd`` and fails with the misleading "plantuml command cannot be run".

See https://github.com/useblocks/sphinx-needs/issues/1749.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from sphinx.project import Project

if TYPE_CHECKING:
    from docutils import nodes
    from sphinx.application import Sphinx
    from sphinx.testing.util import SphinxTestApp


class MountAwareProject(Project):
    """A stand-in for ``sphinx-mounts``, reduced to the essential trick.

    A mount registers a docname whose source file lives *outside* ``srcdir`` by
    storing an **absolute** path in the project's docname->path mapping. Sphinx
    joins that onto ``srcdir`` and an absolute right-hand operand wins, so the
    external file is read transparently. Reproducing it here keeps the test free
    of a ``sphinx-mounts`` dependency.

    Defined at module level (rather than inside the fixture's ``conf.py``) so
    that Sphinx can pickle the environment holding it.
    """

    #: Directory whose ``*.rst`` files are mounted under the ``mounted/`` prefix.
    bundle: Path

    def discover(
        self,
        exclude_paths: Any = (),
        include_paths: Any = ("**",),
    ) -> set[str]:
        docs = super().discover(exclude_paths, include_paths)
        for src in sorted(self.bundle.glob("*.rst")):
            docname = f"mounted/{src.stem}"
            self.docnames.add(docname)
            # ``str``, deliberately -- do not "modernise" this to ``Path``.
            # Sphinx stores ``_StrPath`` here, a ``Path`` subclass that still
            # supports string slicing, because its own HTML builder does
            # ``env.doc2path(docname, False)[len(docname):]`` to recover the
            # source suffix. A plain ``pathlib.Path`` raises ``TypeError:
            # 'PosixPath' object is not subscriptable`` there on Sphinx 7.4.
            # ``str`` is the one type that works across sphinx>=7.4,<10.
            self._docname_to_path[docname] = str(src)
            self._path_to_docname[str(src)] = docname
            docs.add(docname)
        return docs


def _install_project(app: Sphinx) -> None:
    """Swap in the mount-aware project, mirroring what sphinx-mounts does on
    ``builder-inited`` -- before ``env.find_files`` calls ``discover()``."""
    if not isinstance(app.project, MountAwareProject):
        mounted = MountAwareProject(app.project.srcdir, app.project.source_suffix)
        mounted.bundle = Path(app.confdir).parent / "bundle"
        mounted.docnames = set(app.project.docnames)
        mounted._docname_to_path = dict(app.project._docname_to_path)
        mounted._path_to_docname = dict(app.project._path_to_docname)
        app.project = mounted
    if app.env is not None:
        app.env.project = app.project


def _collect_incdirs(app: Sphinx, doctree: nodes.document, docname: str) -> None:
    """Record the ``incdir`` of every PlantUML node, keyed by docname."""
    from sphinxcontrib.plantuml import plantuml

    for node in doctree.findall(plantuml):
        app.collected_incdirs.setdefault(docname, []).append(node["incdir"])  # type: ignore[attr-defined]


def mount_stub_setup(app: Sphinx) -> dict[str, Any]:
    """``setup()`` body for the fixture project's ``conf.py``.

    ``_collect_incdirs`` runs at priority 900, i.e. *after* sphinx-needs' own
    ``doctree-resolved`` handlers (default 500) have replaced the needuml,
    needflow, needsequence and needgantt nodes with generated PlantUML ones.
    """
    app.collected_incdirs = {}  # type: ignore[attr-defined]
    app.connect("builder-inited", _install_project)
    app.connect("doctree-resolved", _collect_incdirs, priority=900)
    return {"version": "0.1"}


CONF_PY = """
from tests.test_plantuml_incdir import mount_stub_setup

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
plantuml_output_format = "svg_img"


def setup(app):
    return mount_stub_setup(app)
"""

HOST_INDEX = """
Host project
============

.. toctree::

   sub/host
   mounted/index
"""

# A needuml in a *nested* host document: ``incdir`` must stay the plain
# srcdir-relative directory it has always been, so PlantUML's content-addressed
# cache keeps working -- and stays machine-independent -- for ordinary projects.
HOST_SUB = """
Host subdirectory page
======================

.. needuml::

   class HostLocal
"""

# The mounted document. It exercises all four directives that route through
# ``set_plantuml_paths()``, so a site-specific mistake in any of them is caught.
# The ``!include`` resolves only when ``incdir`` points at the bundle on disk.
#
# The three needs form a sender -> message -> receiver chain, because
# needsequence throws its PlantUML node away and emits "no needs found" unless
# it can draw at least one connection (see ``process_needsequence``). Every need
# also carries ``:duration:``, without which needgantt warns.
BUNDLE_INDEX = """
Mounted bundle
==============

.. req:: A mounted sender
   :id: MOUNTED_REQ
   :duration: 3
   :links: MOUNTED_MSG

.. req:: A mounted message
   :id: MOUNTED_MSG
   :duration: 2
   :links: MOUNTED_RCV

.. req:: A mounted receiver
   :id: MOUNTED_RCV
   :duration: 1

.. needuml::

   !include lib.puml

   MountedIncludeWorked -> MountedLocal

.. needflow::

.. needsequence::
   :start: MOUNTED_REQ
   :link_types: links

.. needgantt::
"""

BUNDLE_LIB_PUML = """
class MountedIncludeWorked
class MountedLocal
"""


@pytest.fixture
def mounted_project(tmp_path: Path) -> tuple[Path, Path]:
    """Write a host project plus a sibling bundle mounted into it."""
    host = tmp_path / "host"
    bundle = tmp_path / "bundle"
    (host / "sub").mkdir(parents=True)
    bundle.mkdir()

    (host / "conf.py").write_text(textwrap.dedent(CONF_PY), encoding="utf-8")
    (host / "index.rst").write_text(textwrap.dedent(HOST_INDEX), encoding="utf-8")
    (host / "sub" / "host.rst").write_text(textwrap.dedent(HOST_SUB), encoding="utf-8")
    (bundle / "index.rst").write_text(textwrap.dedent(BUNDLE_INDEX), encoding="utf-8")
    (bundle / "lib.puml").write_text(textwrap.dedent(BUNDLE_LIB_PUML), encoding="utf-8")
    return host, bundle


def test_incdir_uses_physical_source_dir(
    mounted_project: tuple[Path, Path],
    sphinx_test_tempdir: Path,
    make_app: Callable[..., SphinxTestApp],
    get_warnings_list: Callable[[SphinxTestApp], list[str]],
) -> None:
    host, bundle = mounted_project
    plantuml = "java -Djava.awt.headless=true -jar {}".format(
        sphinx_test_tempdir / "utils" / "plantuml.jar"
    )
    app = make_app(srcdir=host, freshenv=True, confoverrides={"plantuml": plantuml})
    app.build()

    incdirs: dict[str, list[str]] = app.collected_incdirs  # type: ignore[attr-defined]

    # Ordinary nested host document -- unchanged, srcdir-relative.
    assert incdirs["sub/host"] == ["sub"]

    # Mounted document -- the bundle's physical directory, not the logical
    # docname dir ``mounted``, which does not exist under srcdir at all.
    # One entry per generated-PlantUML directive, in document order: needuml,
    # needflow, needsequence, needgantt -- i.e. every ``set_plantuml_paths()``
    # call site except needarch, which shares needuml's.
    assert incdirs["mounted/index"] == [str(bundle)] * 4

    # End-to-end proof that PlantUML ran and resolved the bundle-relative
    # ``!include``. Before the fix this failed with "plantuml command cannot be
    # run", because the non-existent cwd surfaced as ENOENT from ``subprocess``.
    assert get_warnings_list(app) == []
    rendered = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (Path(app.outdir) / "_images").glob("*.svg")
    )
    assert "MountedIncludeWorked" in rendered
