"""An incremental build re-reads the documents whose need templates changed.

A need's templates are rendered when the document is read, so their output is part of
what the pickled environment keeps. Before the fix nothing told Sphinx about them:
editing a ``.need`` file, creating a missing one, or changing ``needs_template_folder``
or ``needs_render_context`` left every page showing the old output until a full build.

Now each template file a render reads or tries to read is a dependency of the document,
and a change of the template folder, or of the comparable part of the render context,
re-reads every document with a templated need -- and no other. A render-context value
that cannot be compared across builds (a function) never forces a re-read.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
"""

INDEX = """\
Index
=====

.. toctree::

   templated
   imported
   plain
   missing

.. req:: On the index
   :id: REQ_INDEX
"""

TEMPLATED = """\
Templated
=========

.. req:: Templated
   :id: REQ_TPL
   :template: wrap
   :post_template: post

   Body.
"""

MISSING = """\
Missing
=======

.. req:: Missing template
   :id: REQ_MISSING
   :pre_template: later
"""

IMPORTED = """\
Imported
========

.. needimport:: plain.json
   :id_prefix: IMP_
   :post_template: post
"""

PLAIN = """\
Plain
=====

.. req:: Plain
   :id: REQ_PLAIN
"""

PLAIN_JSON = json.dumps(
    {
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs": {
                    "X_1": {"id": "X_1", "type": "req", "title": "X", "content": ""}
                }
            }
        },
    }
)


def _write(srcdir: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = srcdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return srcdir


def _edit(path: Path, text: str) -> None:
    """Write a file, its mtime past the last read whatever the clock's granularity
    (and not in the future, which would keep its documents outdated)."""
    path.write_text(text, encoding="utf-8")
    now = time.time()
    os.utime(path, (now, now))


def _project(tmp_path: Path, *, missing: bool = False) -> Path:
    """The project; with ``missing``, a document whose need names a template that does
    not exist (the ``missing`` page: a need with no template otherwise)."""
    return _write(
        tmp_path / "src",
        {
            "conf.py": CONF,
            "index.rst": INDEX,
            "templated.rst": TEMPLATED,
            "imported.rst": IMPORTED,
            "plain.rst": PLAIN,
            "missing.rst": MISSING if missing else PLAIN.replace("REQ_PLAIN", "REQ_M"),
            "plain.json": PLAIN_JSON,
            "needs_templates/wrap.need": "WRAP v1 {{ content }}\n",
            "needs_templates/post.need": "POST v1 {{ id }}\n",
        },
    )


def _build(
    make_app: Callable[..., SphinxTestApp],
    srcdir: Path,
    *,
    fresh: bool = False,
    parallel: int = 1,
    **confoverrides: Any,
) -> tuple[list[str], dict[str, dict[str, Any]], list[str]]:
    """Build, and return the documents read, the needs written, and the warnings."""
    app = make_app(
        "needs",
        srcdir=srcdir,
        freshenv=fresh,
        parallel=parallel,
        confoverrides=confoverrides,
    )
    read: list[str] = []
    app.connect("env-before-read-docs", lambda _app, _env, docs: read.extend(docs))
    try:
        app.build()
        data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
        return (
            sorted(read),
            data["versions"][data["current_version"]]["needs"],
            build_warnings(app),
        )
    finally:
        app.cleanup()


def test_editing_a_template_re_reads_the_documents_using_it(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    srcdir = _project(tmp_path)
    _, needs, _ = _build(make_app, srcdir, fresh=True)
    assert needs["REQ_TPL"]["content"] == "WRAP v1 Body."
    assert needs["IMP_X_1"]["post_content"] == "POST v1 IMP_X_1"

    _edit(srcdir / "needs_templates" / "post.need", "POST v2 {{ id }}\n")
    read, needs, _ = _build(make_app, srcdir)
    # both documents rendering `post`, and no other
    assert read == ["imported", "templated"]
    assert needs["REQ_TPL"]["post_content"] == "POST v2 REQ_TPL"
    assert needs["IMP_X_1"]["post_content"] == "POST v2 IMP_X_1"

    # nothing changed: nothing is read
    read, _, _ = _build(make_app, srcdir)
    assert read == []


def test_creating_and_deleting_a_template_re_reads_the_document(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """A template that does not exist yet is a dependency too: creating it renders it;
    deleting one that exists reports it missing. Until it exists, its document is
    re-read on every build, as Sphinx treats a missing dependency."""
    srcdir = _project(tmp_path, missing=True)
    _, needs, warnings = _build(make_app, srcdir, fresh=True)
    assert needs["REQ_MISSING"]["pre_content"] == ""
    assert sum("[needs.template_missing]" in w for w in warnings) == 1
    read, _, _ = _build(make_app, srcdir)
    assert read == ["missing"]

    _edit(srcdir / "needs_templates" / "later.need", "LATER {{ id }}\n")
    read, needs, warnings = _build(make_app, srcdir)
    assert read == ["missing"]
    assert needs["REQ_MISSING"]["pre_content"] == "LATER REQ_MISSING"
    assert not any("[needs.template_missing]" in w for w in warnings)
    read, _, _ = _build(make_app, srcdir)
    assert read == []

    (srcdir / "needs_templates" / "wrap.need").unlink()
    read, needs, warnings = _build(make_app, srcdir)
    assert read == ["templated"]
    assert needs["REQ_TPL"]["content"] == ""
    assert sum("[needs.template_missing]" in w for w in warnings) == 1


def test_changing_the_template_folder_re_reads_the_templated_documents(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    srcdir = _project(tmp_path)
    _write(
        srcdir,
        {
            "other/wrap.need": "OTHER {{ content }}\n",
            "other/post.need": "OTHER POST {{ id }}\n",
        },
    )
    _build(make_app, srcdir, fresh=True)
    read, needs, _ = _build(make_app, srcdir, needs_template_folder="other")
    # the documents with a templated need; not `index` or `plain`
    assert read == ["imported", "templated"]
    assert needs["REQ_TPL"]["content"] == "OTHER Body."
    assert needs["IMP_X_1"]["post_content"] == "OTHER POST IMP_X_1"
    read, _, _ = _build(make_app, srcdir, needs_template_folder="other")
    assert read == []


def test_changing_the_render_context_re_reads_the_templated_documents(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    srcdir = _project(tmp_path)
    _write(srcdir, {"needs_templates/wrap.need": "WRAP {{ who }} {{ content }}\n"})
    _, needs, _ = _build(
        make_app, srcdir, fresh=True, needs_render_context={"who": "alice"}
    )
    assert needs["REQ_TPL"]["content"] == "WRAP alice Body."
    read, needs, _ = _build(make_app, srcdir, needs_render_context={"who": "bob"})
    assert read == ["imported", "templated"]
    assert needs["REQ_TPL"]["content"] == "WRAP bob Body."


def _shout(text: str) -> str:
    return text.upper()


class _Opaque:
    """A picklable value without equality: its pickled copy never equals it."""


def _shout_other(text: str) -> str:
    return text.lower()


@pytest.mark.parametrize(
    "value",
    ["module_function", "lambda", "opaque"],
)
def test_a_render_context_value_that_cannot_be_compared_never_forces_a_re_read(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, value: str
) -> None:
    """The render context is compared with the one the documents were read with. A
    module-level function pickles by reference and compares equal to itself: nothing
    is re-read (and changing it is a change). A lambda (or closure) cannot be pickled,
    and an object without equality never equals its pickled copy: each is left out of
    the comparison, so it forces no re-read on every build, and no build fails
    pickling the environment."""
    values = {"module_function": _shout, "lambda": lambda t: t, "opaque": _Opaque()}
    srcdir = _project(tmp_path)
    context = {"v": values[value], "who": "alice"}
    _build(make_app, srcdir, fresh=True, needs_render_context=context)
    read, _, _ = _build(make_app, srcdir, needs_render_context=dict(context))
    assert read == []
    read, _, _ = _build(make_app, srcdir, needs_render_context=dict(context))
    assert read == []


def test_changing_a_render_context_module_function_re_reads(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """A module-level function IS compared: replacing it by another re-reads the
    templated documents."""
    srcdir = _project(tmp_path)
    _build(make_app, srcdir, fresh=True, needs_render_context={"v": _shout})
    read, _, _ = _build(make_app, srcdir, needs_render_context={"v": _shout_other})
    assert read == ["imported", "templated"]


@pytest.mark.parametrize("folder", ["needs_templates", "elsewhere"])
def test_a_project_without_templated_needs_is_not_re_read(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, folder: str
) -> None:
    srcdir = _write(tmp_path / "src", {"conf.py": CONF, "index.rst": PLAIN})
    _build(make_app, srcdir, fresh=True)
    read, _, _ = _build(make_app, srcdir, needs_template_folder=folder)
    assert read == []


class _Ambiguous:
    """What an array's ``==`` gives: a value whose truth cannot be told."""

    def __bool__(self) -> bool:
        raise ValueError("the truth value of an array is ambiguous")


class _ArrayLike:
    """A picklable render-context value whose ``==`` is not a boolean (an array, a data
    frame), without numpy."""

    def __eq__(self, other: object) -> Any:
        return _Ambiguous()

    __hash__ = object.__hash__


def test_a_render_context_value_with_an_ambiguous_equality_builds(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """The render context is compared on every build of every project, templated or
    not: a value whose ``==`` cannot be told true or false (a numpy array, a pandas
    frame) is left out of the comparison rather than failing the build."""
    srcdir = _write(tmp_path / "src", {"conf.py": CONF, "index.rst": PLAIN})
    _, needs, _ = _build(
        make_app, srcdir, fresh=True, needs_render_context={"arr": _ArrayLike()}
    )
    assert "REQ_PLAIN" in needs
    read, _, _ = _build(make_app, srcdir, needs_render_context={"arr": _ArrayLike()})
    assert read == []
