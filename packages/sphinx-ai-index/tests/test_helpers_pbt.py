"""Property-based tests for extension helper functions."""

import pytest
from docutils import nodes, utils
from hypothesis import given
from hypothesis import strategies as st

from sphinx_ai_index import (
    PageSummaryNode,
    _page_summary,
    _top_level_sections,
    depart_page_summary_node_html,
    visit_page_summary_node_html,
)


def _create_doc() -> nodes.document:
    return utils.new_document("test")


def create_text_node(text: str) -> nodes.Text:
    return nodes.Text(text)


def create_summary_node(text: str) -> PageSummaryNode:
    node = PageSummaryNode()
    node += create_text_node(text)
    return node


def create_section(title: str) -> nodes.section:
    sec = nodes.section()
    # Sections usually start with a title node
    title_node = nodes.title()
    title_node += create_text_node(title)
    sec += title_node
    return sec


# --- Strategies ---

# Generate arbitrary text that might be found in a page summary
st_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cc", "Cs")), min_size=0, max_size=100
)
# Generate a list of strings to become sections
st_section_titles = st.lists(
    st.text(
        alphabet=st.characters(blacklist_categories=("Cc", "Cs")),
        min_size=1,
        max_size=50,
    ),
    max_size=10,
)


@given(st_text)
def test_page_summary_single_node(summary_text: str) -> None:
    """Property: If there's exactly 1 summary node anywhere, it returns its stripped text."""
    doc = _create_doc()

    # Put it in some random nested structure
    p = nodes.paragraph()
    p += create_summary_node(summary_text)

    doc += p

    expected = summary_text.strip()
    assert _page_summary(doc) == expected


@given(st.lists(st_text, min_size=2, max_size=5))
def test_page_summary_multiple_nodes(texts: list[str]) -> None:
    """Property: If there are multiple nodes, it always returns the *first* one in document order."""
    doc = _create_doc()

    for t in texts:
        doc += create_summary_node(t)

    expected = texts[0].strip()
    assert _page_summary(doc) == expected


@given(st.lists(st_text, min_size=0, max_size=5))
def test_page_summary_no_nodes(texts: list[str]) -> None:
    """Property: Missing summary node always returns empty string."""
    doc = _create_doc()

    # insert paragraphs but NO summary nodes
    for t in texts:
        p = nodes.paragraph()
        p += create_text_node(t)
        doc += p

    assert _page_summary(doc) == ""


@given(st_section_titles)
def test_top_level_sections_extraction(titles: list[str]) -> None:
    """Property: _top_level_sections accurately extracts immediate children of the root section."""
    doc = _create_doc()

    # According to Sphinx parsing, the overall page is usually wrapped in a root section
    root_sec = create_section("Root Title")

    # Expected titles are those of sections WITH children (as per _top_level_sections logic)
    # The logic requires child.children to be true. Let's make sure the sections we add aren't empty.
    expected = []

    for t in titles:
        child_sec = create_section(t)
        # Add a dummy paragraph so it's not totally empty (logic checks `and child.children`)
        # Wait, the title is already a child! `create_section` adds the title_node.
        # So child.children > 0 is always true for `create_section`.
        root_sec += child_sec
        expected.append(t)

    doc += root_sec
    assert _top_level_sections(doc) == expected


@given(st_section_titles)
def test_top_level_sections_ignores_deep_nesting(titles: list[str]) -> None:
    """Property: Deeply nested sections are not extracted as top-level."""
    doc = _create_doc()
    root_sec = create_section("Root")

    if not titles:
        doc += root_sec
        assert _top_level_sections(doc) == []
        return

    top_sec = create_section(titles[0])

    # Put all other sections INSIDE top_sec (so they are depth=2)
    for t in titles[1:]:
        sub_sec = create_section(t)
        top_sec += sub_sec

    root_sec += top_sec
    doc += root_sec

    # Only the first one should be extracted
    assert _top_level_sections(doc) == [titles[0]]


@given(st.lists(st.text(), max_size=5))
def test_top_level_sections_ignores_non_sections(contents: list[str]) -> None:
    """Property: Paragraphs and other nodes directly under root section are ignored."""
    doc = _create_doc()
    root_sec = create_section("Root")

    for c in contents:
        p = nodes.paragraph()
        p += create_text_node(c)
        root_sec += p

    doc += root_sec
    assert _top_level_sections(doc) == []


def test_top_level_sections_no_root_section() -> None:
    """Property: Document completely lacking any section returns empty list."""
    doc = _create_doc()
    p = nodes.paragraph()
    p += create_text_node("Hello")
    doc += p
    assert _top_level_sections(doc) == []


def test_page_summary_skip_nodes_coverage() -> None:
    node = create_summary_node("test")
    with pytest.raises(nodes.SkipNode):
        visit_page_summary_node_html(None, node)
    depart_page_summary_node_html(None, node)
