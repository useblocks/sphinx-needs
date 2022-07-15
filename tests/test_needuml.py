from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needuml"}], indirect=True)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert html


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needuml"}], indirect=True)
def test_needuml_option_key(test_app):
    app = test_app
    app.build()

    # check multiple needumls inside a need
    all_needs = app.env.needs_all_needs
    all_needumls = app.env.needs_all_needumls

    assert len(all_needumls) == 9

    # check first need with 2 needumls, 1 with key option, 1 without
    curr_need_01 = all_needs["INT_002"]
    assert curr_need_01

    curr_need_uml_01 = all_needumls["needuml-index-1"]
    curr_need_uml_02 = all_needumls["needuml-index-2"]

    assert curr_need_uml_01["key"] is None
    assert curr_need_uml_02["key"] == "sequence"

    assert "class \"{{needs['ST_001'].title}}\" as test" in curr_need_uml_01["content"]
    assert curr_need_uml_02["content"] == "Alice -> Bob: Hi Bob\nBob --> Alice: Hi Alice"

    assert curr_need_01["diagram"] == curr_need_uml_01["content"]
    assert curr_need_01["sequence"] == curr_need_uml_02["content"]

    # check second need with 2 needumls, both have key option
    curr_need_02 = all_needs["INT_003"]
    curr_need_uml_03 = all_needumls["needuml-index-3"]
    curr_need_uml_04 = all_needumls["needuml-index-4"]

    assert curr_need_uml_03["key"] == "class"
    assert curr_need_uml_04["key"] == "sequence"

    assert "class \"{{needs['ST_001'].title}}\" as test" in curr_need_uml_03["content"]
    assert curr_need_uml_04["content"] == "Alice -> Bob: Hi Bob\nBob --> Alice: Hi Alice"

    assert curr_need_02["diagram"] is None
    assert curr_need_02["class"] == curr_need_uml_03["content"]
    assert curr_need_02["sequence"] == curr_need_uml_04["content"]

    # check third need with 4 needumls, 2 have key option, 2 don't have
    curr_need_03 = all_needs["INT_004"]
    curr_need_uml_05 = all_needumls["needuml-index-5"]
    curr_need_uml_06 = all_needumls["needuml-index-6"]
    curr_need_uml_07 = all_needumls["needuml-index-7"]
    curr_need_uml_08 = all_needumls["needuml-index-8"]

    assert curr_need_uml_05["key"] == "class"
    assert curr_need_uml_06["key"] is None
    assert curr_need_uml_07["key"] == "sequence"
    assert curr_need_uml_08["key"] is None

    # only store the first needuml from those don't have key option under diagram
    assert curr_need_uml_06["content"] == "Superman -> Batman: Hi Bruce\nBatman --> Superman: Hi Clark"
    assert curr_need_03["diagram"] == curr_need_uml_06["content"]


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needuml_duplicate_key"}], indirect=True
)
def test_needuml_option_key_duplicate(test_app):
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True)
    assert out.returncode == 1

    assert (
        "sphinx_needs.directives.needuml.NeedumlException: Inside need: INT_001, "
        "found duplicate Needuml option key name: sequence" in out.stderr.decode("utf-8")
    )


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needuml_key_name_diagram"}], indirect=True
)
def test_needuml_option_key_forbidden(test_app):
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True)
    assert out.returncode == 1

    assert (
        "sphinx_needs.directives.needuml.NeedumlException: Needuml option key name can't be: diagram"
        in out.stderr.decode("utf-8")
    )


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needuml"}], indirect=True)
def test_needuml_jinja_uml_key(test_app):
    app = test_app
    app.build()

    # check multiple needumls inside a need
    all_needs = app.env.needs_all_needs
    all_needumls = app.env.needs_all_needumls

    curr_need = all_needs["INT_003"]
    curr_needuml = all_needumls["needuml-index-3"]
    assert curr_need["content_node"].children[1].rawsource == "needuml-index-3"

    assert curr_needuml["key"] == "class"
    assert '{{uml("INT_002", "sequence")}}' in curr_needuml["content"]


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needuml_key_exists_in_extra_links"}], indirect=True
)
def test_needuml_key_exists_in_extra_links(test_app):
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True)
    assert out.returncode == 1

    assert (
        "sphinx_needs.directives.needuml.NeedumlException: Needuml key: checks, already exists in "
        "needs_extra_links options: ['links', 'parent_needs', 'checks']" in out.stderr.decode("utf-8")
    )


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needuml_key_exists_in_extra_options"}], indirect=True
)
def test_needuml_key_exists_in_extra_options(test_app):
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True)
    assert out.returncode == 1

    assert (
        "sphinx_needs.directives.needuml.NeedumlException: Needuml key: my_extra_option, already exists in "
        "needs_extra_options: ['my_extra_option', 'another_option'," in out.stderr.decode("utf-8")
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_key_exists_in_need_default_options"}],
    indirect=True,
)
def test_needuml_key_exists_in_need_default_options(test_app):
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True)
    assert out.returncode == 1

    assert (
        "sphinx_needs.directives.needuml.NeedumlException: Needuml key: lineno, already exists in "
        "need default options: ['docname', 'lineno'," in out.stderr.decode("utf-8")
    )
