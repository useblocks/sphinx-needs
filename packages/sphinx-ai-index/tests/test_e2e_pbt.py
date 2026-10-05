"""Property-based E2E tests for the AI Sphinx extension."""

import io
import json
import tempfile
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st
from sphinx.application import Sphinx


# A strategy to generate random valid-ish RST content so it doesn't just error out immediately on every parse
@st.composite
def st_rst_content(draw: Any) -> tuple[str, str, list[str], str]:
    """Generate somewhat legible RST strings to feed into Sphinx."""
    # Build a file starting with a title
    title = draw(
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs", "Cc"),
                blacklist_characters=("\\",),
            ),
            min_size=1,
            max_size=20,
        )
    )
    # the title underline must be at least as long as the title
    title_line = "=" * max(len(title), 4)

    parts = [title, title_line, ""]

    # Maybe add a summary
    has_summary = draw(st.booleans())
    summary_text = ""
    if has_summary:
        summary_text = draw(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs", "Cc"),
                    blacklist_characters=("\\",),
                ),
                min_size=1,
                max_size=50,
            )
        )
        # Ensure summary text isn't a directive itself to avoid breaking
        summary_text = summary_text.replace("\n", " ").strip()
        if summary_text:
            parts.extend([".. page-summary::", "", f"   {summary_text}", ""])

    # Maybe add some sections
    num_sections = draw(st.integers(min_value=0, max_value=3))
    expected_sections = []

    for _ in range(num_sections):
        sec_title = draw(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs", "Cc"),
                    blacklist_characters=("\\",),
                ),
                min_size=1,
                max_size=20,
            )
        )
        sec_line = "-" * max(len(sec_title), 4)
        parts.extend([sec_title, sec_line, "", "Some content", ""])
        expected_sections.append(sec_title)

    return "\n".join(parts), title.strip(), expected_sections, summary_text.strip()


def run_sphinx_build(srcdir: Path, outdir: Path, builder: str = "html") -> Sphinx:
    doctreedir = srcdir / "_build" / ".doctrees"
    app = Sphinx(
        srcdir=str(srcdir),
        confdir=str(srcdir),
        outdir=str(outdir),
        doctreedir=str(doctreedir),
        buildername=builder,
        status=io.StringIO(),
        warning=io.StringIO(),
    )
    app.build()
    return app


# We use a relatively small max_examples because Sphinx I/O can be slow
@settings(max_examples=10, deadline=None)
@given(st.lists(st_rst_content(), min_size=1, max_size=5))
def test_e2e_property_always_valid_json(
    pages: list[tuple[str, str, list[str], str]],
) -> None:
    """Property: Valid RST chunks never crash the build and always produce conforming JSON schema."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        srcdir = tmp_path / "src"
        srcdir.mkdir(exist_ok=True)
        outdir = tmp_path / "out"
        outdir.mkdir(exist_ok=True)

        # Write conf.py
        (srcdir / "conf.py").write_text(
            "project = 'e2e-test'\n"
            "extensions = ['sphinx_ai_index']\n"
            "html_theme = 'alabaster'\n"
        )

        # Write RST files
        page_names = []
        for i, (
            content,
            expected_title,
            expected_sections,
            expected_summary,
        ) in enumerate(pages):
            name = "index" if i == 0 else f"page_{i}"
            page_names.append(
                (name, content, expected_title, expected_sections, expected_summary)
            )
            (srcdir / f"{name}.rst").write_text(content, encoding="utf-8")

        if len(pages) > 1:
            # Link them from index so Sphinx doesn't complain about unincluded documents
            index_tree = (srcdir / "index.rst").read_text(encoding="utf-8")
            toctree = (
                "\n\n.. toctree::\n\n"
                + "\n".join(f"   {name}" for name, _, _, _, _ in page_names[1:])
                + "\n"
            )
            (srcdir / "index.rst").write_text(index_tree + toctree, encoding="utf-8")

        run_sphinx_build(srcdir, outdir)

        index_file = outdir / "ai_docs_index.json"
        assert index_file.exists()

        # Verify Schema
        data = json.loads(index_file.read_text(encoding="utf-8"))
        assert data["version"] == "1.0"
        assert isinstance(data["pages"], list)
        assert len(data["pages"]) == len(pages)

        for page in data["pages"]:
            assert isinstance(page["title"], str)
            assert isinstance(page["rst_source_path"], str)
            assert isinstance(page["html_path"], str)
            assert isinstance(page["sections"], list)
            assert all(isinstance(s, str) for s in page["sections"])
            assert isinstance(page["summary"], str)

        # Note: Accurately mapping expected properties inside Sphinx's parser can be tricky
        # because Sphinx sanitizes titles and strips multiple spaces, but establishing
        # the schema invariance is the primary goal of this test.
