from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needarch"}], indirect=True)
def test_doc_needarch(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert html


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needarch_negative_tests"}], indirect=True
)
def test_doc_needarch_negative(test_app):
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True)

    assert out.returncode == 1
    assert (
        "sphinx_needs.directives.needuml.NeedArchException: Directive needarch "
        "can only be used inside a need." in out.stderr.decode("utf-8")
    )


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needarch_jinja_func_import"}], indirect=True
)
def test_doc_needarch_jinja_import(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert html

    # check needarch
    all_needumls = app.env.needs_all_needumls
    assert len(all_needumls) == 1

    need_arch = all_needumls["needarch-index-0"]
    assert need_arch["is_arch"]
    assert need_arch["content"] == 'Alice -> Bob: Hi Bob\nBob --> Alice: hi Alice\n\n{{import("uses", "tests")}}'

    assert need_arch["content_calculated"]
    assert "@startuml\n\nAlice -> Bob: Hi Bob\n" in need_arch["content_calculated"]
    assert (
        'node "<size:12>User Story</size>\\n**Story**\\n<size:10>US_001</size>" as US_001'
        in need_arch["content_calculated"]
    )
    assert (
        'node "<size:12>User Story</size>\\n**Story 002**\\n<size:10>US_002</size>" as US_002'
        in need_arch["content_calculated"]
    )
    assert (
        'card "<size:12>Interface</size>\\n**Test interface**\\n<size:10>INT_001</size>" as INT_001'
        in need_arch["content_calculated"]
    )
    assert (
        'card "<size:12>Interface</size>\\n**Test interface2**\\n<size:10>INT_002</size>" as INT_002'
        in need_arch["content_calculated"]
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needarch_jinja_func_import_negative_tests"}],
    indirect=True,
)
def test_doc_needarch_jinja_import_negative(test_app):
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True)

    assert out.returncode == 1
    assert (
        "sphinx_needs.directives.needuml.NeedumlException: "
        "Jinja function 'import()' is not supported in non-embedded needuml directive." in out.stderr.decode("utf-8")
    )


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needarch_jinja_func_need"}], indirect=True
)
def test_needarch_jinja_func_need(test_app):
    app = test_app
    app.build()

    all_needumls = app.env.needs_all_needumls
    assert len(all_needumls) == 1

    assert "{{flow(need().id)}}" in all_needumls["needuml-index-0"]["content"]

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "as INT_001 [[../index.html#INT_001]]" in html

    import subprocess

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True)
    assert out.returncode == 0