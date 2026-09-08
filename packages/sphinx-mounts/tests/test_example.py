"""End-to-end test of the full example under ``tests/example/``.

The example is a complete, checked-in reference setup: a host Sphinx
project, two Bazel-generated bundles (one RST, one Markdown), ten
checked-in "showcase" bundles — one folder per file-referencing
directive (literalinclude, include,, csv-table,, raw,, image,, figure,
graphviz,, uml,, mermaid) plus a Sphinx-Needs kitchen sink covering all
three of its doc-relative file references, one checked-in "release
notes" bundle mounted in file-list mode(``files``),and one checked-in
"fragments" bundle of loose files mounted with ``attach_each`` — all
wired into the host's toctree via ``attach_to``. The example is also
**edition-variant**:``[needs.variant_data]`` in ``ubproject.toml`` sets
``edition = "basic"``,two ``[[source.variant_sources]]`` rules gate the
host's own ``variants/{basic,pro}.rst`` pages by glob,and two checked-in
``reference/`` edition bundles are each gated whole by an ``if`` on their
mount entry. This test runs the pipeline the example's README documents:

1. Copy the example to a tmp workspace (so the developer's real
   ``bazel-bin/`` is untouched).
2. ``bazel build //:all_bundles`` to materialise the bundles under
   ``bazel-bin/bundles/...``.
3. ``sphinx-build`` against the host project. ``sphinx-mounts`` reads
   ``ubproject.toml``, mounts both bundles in place,, and ``attach_to``
   injects each bundle's entry doc into the host's ``index.rst``
   toctree at doctree-read time. The variant keys narrow the doc set to
   the basic edition:``variants/basic.rst`` and the ``reference/basic``
   bundle are built;``variants/pro.rst`` and the ``reference/pro`` bundle
   are gated off,and the references to them are downgraded to INFO so
   ``-W`` passes.

4. Assert that all three layers(host,, RST bundle,, MD bundle) appear
   in the rendered HTML, plus the attach_to wiring did its work.

5. Flip ``edition`` to ``"pro"`` in the workspace's TOML and run the
   pipeline again:the mirror image must hold — pro pages and bundle
   present, basic absent,and ``-W`` passes again.

Marked ``bazel``;skipped when no ``bazel``/``bazelisk`` is on PATH.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from sphinx_needs_testkit import sphinx_build_command

TESTS_DIR = Path(__file__).parent
EXAMPLE_DIR = TESTS_DIR / "example"


def _find_bazel() -> str | None:
    return shutil.which("bazel") or shutil.which("bazelisk")


def _run_sphinx_build(docs: Path, html_out: Path) -> str:
    """Run ``sphinx-build -nW`` against the host project; fail on nonzero.

    Returns the combined stdout+stderr log, so callers can assert on the
    INFO records the variant machinery emits (``mounts.mount_gated``,
    ``mounts.variant_excluded_reference``)."""
    result = subprocess.run(
        sphinx_build_command(
            "-b", "html", "-nW", "--keep-going", "-c", docs, docs, html_out
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            "sphinx-build failed:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n"
        )
    return f"{result.stdout}\n{result.stderr}"


@pytest.mark.bazel
def test_example_pipeline_end_to_end(tmp_path: Path) -> None:
    bazel = _find_bazel()
    if bazel is None:
        pytest.skip("bazel/bazelisk not on PATH")
    pytest.importorskip("myst_parser")
    # The showcase bundles render graphviz and plantuml diagrams at build
    # time under ``-nW``; skip (don't fail) when their extensions or
    # binaries are unavailable. Mermaid runs in ``raw`` mode, so no
    # ``mmdc`` binary is required.
    pytest.importorskip("sphinxcontrib.plantuml")
    pytest.importorskip("sphinxcontrib.mermaid")
    pytest.importorskip("sphinx_needs")
    if shutil.which("dot") is None:
        pytest.skip(
            "'dot' not on PATH — required to render the showcase graphviz "
            "bundle under -nW"
        )
    # One condition, not a resolution chain: the example is built by Bazel in a
    # sandbox that cannot see ``vendor/``, so ``PLANTUML_JAR`` (which its
    # ``.bazelrc`` passes through ``--action_env`` and its ``docs/conf.py``
    # reads) is the only route to a renderer it has. ``uv run poe
    # test-mounts-bazel`` is the task that sets it -- it is the one sphinx-mounts
    # task that kept ``uses``, for exactly this reason.
    if not os.environ.get("PLANTUML_JAR"):
        pytest.skip(
            "PLANTUML_JAR is unset, and the example's Bazel sandbox has no other "
            "route to a renderer — run `uv run poe test-mounts-bazel`, which sets "
            "it from the jar committed under vendor/plantuml/, or export it "
            "yourself (with java on PATH), to render the showcase uml bundle "
            "under -nW"
        )

    workspace = tmp_path / "ws"
    shutil.copytree(EXAMPLE_DIR, workspace)

    # Per-test --output_base so this never touches the developer's real
    # Bazel state.
    output_base = tmp_path / "bazel-out-base"
    output_base.mkdir()

    bazel_build = subprocess.run(
        [
            bazel,
            f"--output_base={output_base}",
            "build",
            "//:all_bundles",
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if bazel_build.returncode != 0:
        pytest.fail(
            "bazel build failed:\n"
            f"stdout:\n{bazel_build.stdout}\n"
            f"stderr:\n{bazel_build.stderr}\n"
        )

    # Both bundles should now exist on disk where ubproject.toml expects
    # them.
    bazel_bin = workspace / "bazel-bin" / "bundles"
    assert (bazel_bin / "api-foo" / "index.rst").exists()
    assert (bazel_bin / "api-foo" / "reference.rst").exists()
    assert (bazel_bin / "api-foo" / "coverage.rst").exists()
    assert (bazel_bin / "api-bar" / "index.md").exists()
    # The pre-built HTML report (consumed by html_extra_path) is
    # materialised too, alongside the bundles.
    assert (
        workspace
        / "bazel-bin"
        / "coverage_report"
        / "extra"
        / "coverage"
        / "index.html"
    ).exists()

    # The directive "showcase" bundles are plain checked-in files (NOT
    # Bazel-generated): they live under ``showcase/<directive>/`` and are
    # copied into the workspace as-is, then mounted directly from there.
    assert (workspace / "showcase" / "literalinclude" / "greeter.py").exists()
    assert (workspace / "showcase" / "uml" / "sequence.puml").exists()
    assert (workspace / "showcase" / "csv-table" / "data.csv").exists()
    # The Sphinx-Needs bundle ships the three files its directives read.
    needs_bundle = workspace / "showcase" / "needs"
    assert (needs_bundle / "arch-common.puml").exists()
    assert (needs_bundle / "imported-needs.json").exists()
    assert (needs_bundle / "report-template.rst").exists()

    # The "release notes" bundle is checked in too and mounted via file-list
    # mode. ``2026-q3-draft.rst`` is present on disk but deliberately left out
    # of the mount's ``files`` list (asserted absent from the output in 2d).
    release_notes = workspace / "release-notes"
    assert (release_notes / "index.rst").exists()
    assert (release_notes / "notes" / "2026-q1.rst").exists()
    assert (release_notes / "notes" / "2026-q3-draft.rst").exists()

    # The "fragments" bundle is a set of loose files with NO index, mounted
    # with attach_each (asserted in 2e).
    fragments = workspace / "fragments"
    assert (fragments / "note-one.rst").exists()
    assert (fragments / "note-two.rst").exists()
    assert not (fragments / "index.rst").exists()

    # Run sphinx-build against the host project. -W turns any unresolved
    # reference into a failure, so a broken mount surfaces here.
    docs = workspace / "docs"
    html_basic = tmp_path / "html-basic"
    log_basic = _run_sphinx_build(docs, html_basic)

    # 1) Host's own RST page rendered.
    index_html = (html_basic / "index.html").read_text(encoding="utf-8")
    install_html = (html_basic / "installation.html").read_text(encoding="utf-8")
    assert "INDEX_PAGE_MARKER" in index_html
    assert "INSTALL_PAGE_MARKER" in install_html

    # 2) RST bundle rendered (entry + reference).
    foo_index = (html_basic / "_generated" / "api-foo" / "index.html").read_text(
        encoding="utf-8"
    )
    foo_ref = (html_basic / "_generated" / "api-foo" / "reference.html").read_text(
        encoding="utf-8"
    )
    assert "API_FOO_INDEX_MARKER" in foo_index
    assert "API_FOO_REFERENCE_MARKER" in foo_ref

    # 2b) Each checked-in "showcase" bundle renders one file-referencing
    #     directive at _generated/showcase/<directive>/index.html. The
    #     build succeeding under -nW already proves every directive
    #     resolved its path *inside* its bundle (and passed path_check);
    #     these spot-checks confirm the referenced content actually landed.
    def _showcase(name: str) -> str:
        return (html_basic / "_generated" / "showcase" / name / "index.html").read_text(
            encoding="utf-8"
        )

    # Text directives embed the referenced file's content verbatim.
    assert "SHOWCASE_GREETER" in _showcase("literalinclude")
    assert "SHOWCASE_INCLUDE_BODY" in _showcase("include")
    assert "SHOWCASE_CSV_ROW" in _showcase("csv-table")
    assert "SHOWCASE_RAW_BODY" in _showcase("raw")
    assert "SHOWCASE_MERMAID_NODE" in _showcase("mermaid")  # mermaid (raw mode)
    # image / figure / graphviz / uml render to files in the shared _images/.
    assert "SHOWCASE_IMAGE" in _showcase("image")
    assert "SHOWCASE_FIGURE" in _showcase("figure")
    assert "SHOWCASE_GRAPHVIZ" in _showcase("graphviz")
    assert "SHOWCASE_UML" in _showcase("uml")
    assert (html_basic / "_images").is_dir()

    # 2b-bis) The Sphinx-Needs bundle is the one showcase covering several
    #     directives, so it has a page per directive rather than a single
    #     index. Each reads a different bundle-local file through a different
    #     mechanism; all three must resolve against the bundle root.
    needs_out = html_basic / "_generated" / "showcase" / "needs"

    def _needs_page(name: str) -> str:
        return (needs_out / f"{name}.html").read_text(encoding="utf-8")

    assert "SHOWCASE_NEEDS_INDEX" in _needs_page("index")

    # needimport: the needs.json is addressed bundle-relative via relfn2path,
    # and its needs become real needs in the host build.
    needimport_html = _needs_page("needimport")
    assert "SHOWCASE_NEEDIMPORT" in needimport_html
    assert "SHOWCASE_NEEDIMPORT_TITLE" in needimport_html
    assert "SN_IMP_SPEC" in needimport_html

    # needreport: the Jinja template is addressed bundle-relative too, and the
    # bundle ships its own so it needs nothing from the host but sphinx-needs.
    needreport_html = _needs_page("needreport")
    assert "SHOWCASE_NEEDREPORT" in needreport_html
    assert "SHOWCASE_NEEDREPORT_TEMPLATE" in needreport_html

    # needuml / needarch: PlantUML resolves ``!include`` against the working
    # directory sphinx-needs derives from the document's *source file*. The
    # marker only reaches the rendered SVG if the bundle-local .puml was found,
    # so this is the assertion that would fail were that directory taken from
    # the logical docname instead (sphinx-needs #1749).
    assert "SHOWCASE_NEEDUML" in _needs_page("needuml")
    assert "SHOWCASE_NEEDARCH" in _needs_page("needarch")
    included_in = [
        svg.name
        for svg in (html_basic / "_images").glob("*.svg")
        if "SHOWCASE_NEEDS_PUML_INCLUDE" in svg.read_text(encoding="utf-8")
    ]
    assert len(included_in) == 2, (
        "expected the bundle-local arch-common.puml to be !include-d into both "
        f"the needuml and the needarch diagram, got {included_in}"
    )

    # ``report-template.rst`` is Jinja input, not a document: the mount's
    # ``exclude`` keeps it out of the doc set despite its .rst suffix, so no
    # orphan page of unrendered Jinja is published.
    assert not (needs_out / "report-template.html").exists()

    # 2c) The pre-built HTML coverage report is shipped into the site by
    #     html_extra_path — so the built output is self-contained and
    #     copyable to any server — and the api-foo bundle's coverage page
    #     links to + embeds it via a bundle-relative URL. The report is
    #     read in place; it is never staged into the docs source tree.
    assert (html_basic / "coverage" / "index.html").exists()
    assert (html_basic / "coverage" / "greeter.py.html").exists()
    report_html = (html_basic / "coverage" / "index.html").read_text(encoding="utf-8")
    assert "API_FOO_COVERAGE_REPORT_MARKER" in report_html
    foo_cov = (html_basic / "_generated" / "api-foo" / "coverage.html").read_text(
        encoding="utf-8"
    )
    assert "API_FOO_COVERAGE_MARKER" in foo_cov
    assert 'href="../../coverage/index.html"' in foo_cov
    assert 'src="../../coverage/index.html"' in foo_cov

    # 2d) File-list mode (``files``): only the three explicitly listed files
    #     were mounted, at a FLAT namespace under _generated/release-notes/
    #     (each file's basename is the docname tail, so the source-side
    #     ``notes/`` subdirectory is dropped). The entry doc is wired in via
    #     attach_to, exactly like a directory mount.
    rn_index = (html_basic / "_generated" / "release-notes" / "index.html").read_text(
        encoding="utf-8"
    )
    rn_q1 = (html_basic / "_generated" / "release-notes" / "2026-q1.html").read_text(
        encoding="utf-8"
    )
    rn_q2 = (html_basic / "_generated" / "release-notes" / "2026-q2.html").read_text(
        encoding="utf-8"
    )
    assert "RELEASE_NOTES_INDEX_MARKER" in rn_index
    assert "RELEASE_NOTES_Q1_MARKER" in rn_q1
    assert "RELEASE_NOTES_Q2_MARKER" in rn_q2
    # Flat namespace: the source-side ``notes/`` subdirectory is not part of
    # any docname, so no such directory exists in the output.
    assert not (html_basic / "_generated" / "release-notes" / "notes").exists()
    # Selective pick: the draft file sits in the same source tree but was
    # left out of the ``files`` list, so — unlike a directory mount — it was
    # never discovered and produced no page.
    assert not (
        html_basic / "_generated" / "release-notes" / "2026-q3-draft.html"
    ).exists()

    # 2e) attach_each: the "fragments" bundle is a file-list mount of loose
    #     files with NO index. attach_each wires *every* listed file into the
    #     host toctree, so both pages render and neither is orphaned — without
    #     any index doc authored for the bundle.
    frag_one = (html_basic / "_generated" / "fragments" / "note-one.html").read_text(
        encoding="utf-8"
    )
    frag_two = (html_basic / "_generated" / "fragments" / "note-two.html").read_text(
        encoding="utf-8"
    )
    assert "FRAGMENT_ONE_MARKER" in frag_one
    assert "FRAGMENT_TWO_MARKER" in frag_two
    # No index doc exists or was invented for the fragments bundle.
    assert not (html_basic / "_generated" / "fragments" / "index.html").exists()

    # 3) Markdown bundle rendered.
    bar_index = (html_basic / "_generated" / "api-bar" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "API_BAR_INDEX_MARKER" in bar_index

    # 4) Both wiring styles produce toctree links in the rendered
    #    host index.html — api-foo via ``attach_to`` (doctree-level
    #    injection; the host source RST never references its mount
    #    path), api-bar via a hand-written toctree entry in the
    #    host's ``index.rst``.
    source_index_rst = (docs / "index.rst").read_text(encoding="utf-8")
    assert "_generated/api-foo" not in source_index_rst, (
        "api-foo is wired via attach_to; the host source RST must not "
        "reference its mount path"
    )
    assert "_generated/api-bar/index" in source_index_rst, (
        "api-bar has no attach_to in this example; the host references "
        "its entry doc by hand"
    )
    assert "_generated/api-foo/index.html" in index_html
    assert "_generated/api-bar/index.html" in index_html
    # The showcase bundles are wired via attach_to too, so their entry
    # docs appear in the host index toctree (and never in its source RST).
    assert "_generated/showcase" not in source_index_rst
    assert "_generated/showcase/literalinclude/index.html" in index_html
    assert "_generated/showcase/uml/index.html" in index_html
    assert "_generated/showcase/needs/index.html" in index_html
    # The file-list release-notes bundle is wired via attach_to as well, so
    # its entry doc appears in the host index toctree but never in the source.
    assert "_generated/release-notes" not in source_index_rst
    assert "_generated/release-notes/index.html" in index_html
    # attach_each wires *every* fragment into the host index toctree (no
    # entry doc), and the host source RST never references the mount path.
    assert "_generated/fragments" not in source_index_rst
    assert "_generated/fragments/note-one.html" in index_html
    assert "_generated/fragments/note-two.html" in index_html

    # 4b) The edition-variant host pages are wired into the host toctree by
    #     hand, but only the page the CURRENT variant builds survives; the
    #     reference to the excluded one is downgraded to INFO (so ``-W``
    #     still passes), and the reference/basic mount's entry doc is wired
    #     in via attach_to (never in the source RST).
    assert "variants/basic" in source_index_rst
    assert "variants/pro" in source_index_rst
    assert "_generated/reference" not in source_index_rst
    assert "variants/basic.html" in index_html
    assert "variants/pro.html" not in index_html
    assert "_generated/reference/basic/index.html" in index_html
    assert "_generated/reference/pro/index.html" not in index_html
    # The INFO records are the proof that the gating was applied, not a typo.
    assert "mounts.mount_gated" in log_basic
    assert "mounts.variant_excluded_reference" in log_basic

    # 4c) The basic variant's own conditional page renders, links to the
    #     basic edition bundle,and the pro pages/bundle are absent. The
    #     variant_sources rule removed ``variants/pro.rst`` from the doc set,and
    #     the ``if = "var.edition == 'pro'"`` gate removed the whole pro
    #     bundle — no pages, no docnames at all.
    basic_variant = (html_basic / "variants" / "basic.html").read_text(encoding="utf-8")
    assert "VARIANT_BASIC_PAGE_MARKER" in basic_variant
    assert "_generated/reference/basic/index.html" in basic_variant
    ref_basic_index = (
        html_basic / "_generated" / "reference" / "basic" / "index.html"
    ).read_text(encoding="utf-8")
    assert "REFERENCE_BASIC_INDEX_MARKER" in ref_basic_index
    assert (
        html_basic / "_generated" / "reference" / "basic" / "reference.html"
    ).exists()
    assert not (html_basic / "_generated" / "reference" / "pro").exists()
    assert not (html_basic / "variants" / "pro.html").exists()

    # 5) Nothing was copied into the host srcdir — neither the mounted
    #    bundles (_generated) nor the html_extra_path report (coverage).

    assert not (docs / "_generated").exists()
    assert not (docs / "coverage").exists()

    # 6) Build the OTHER edition: flip the variant map in the workspace's
    #    TOML (the checked-in file is ``edition = "basic"``)and run the
    #    pipeline again. Exactly the mirror image must hold — pro pages
    #    and bundle present,, basic absent,, and ``-W`` still passes. The
    #    conditions are evaluated against the SAME map sphinx-needs resolved
    #    (needs_variant_data confval), so the two tools cannot disagree.

    (docs / "ubproject.toml").write_text(
        (docs / "ubproject.toml")
        .read_text(encoding="utf-8")
        .replace('edition = "basic"', 'edition = "pro"'),
        encoding="utf-8",
    )
    html_pro = tmp_path / "html-pro"
    log_pro = _run_sphinx_build(docs, html_pro)

    index_pro = (html_pro / "index.html").read_text(encoding="utf-8")
    assert "INDEX_PAGE_MARKER" in index_pro
    assert "variants/basic.html" not in index_pro
    assert "variants/pro.html" in index_pro
    assert "_generated/reference/basic/index.html" not in index_pro
    assert "_generated/reference/pro/index.html" in index_pro
    assert "mounts.mount_gated" in log_pro
    assert "mounts.variant_excluded_reference" in log_pro

    pro_variant = (html_pro / "variants" / "pro.html").read_text(encoding="utf-8")
    assert "VARIANT_PRO_PAGE_MARKER" in pro_variant
    assert "_generated/reference/pro/index.html" in pro_variant
    ref_pro_index = (
        html_pro / "_generated" / "reference" / "pro" / "index.html"
    ).read_text(encoding="utf-8")
    assert "REFERENCE_PRO_INDEX_MARKER" in ref_pro_index
    assert (html_pro / "_generated" / "reference" / "pro" / "reference.html").exists()
    assert not (html_pro / "_generated" / "reference" / "basic").exists()
    assert not (html_pro / "variants" / "basic.html").exists()
    # The two builds shared one workspace;the flip is the only change.
