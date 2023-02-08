"""Test Sphinx-Needs language features for custom directive snippets."""

import os
import sys

import pytest
import pytest_lsp
from packaging import version
from pygls import __version__

TEST_DOC_ROOT_URI = os.path.join(
    "file://", os.path.abspath(os.path.dirname(__file__)), "doc_lsp_custom_directive_snippets"
)
TEST_FILE_URI = os.path.join(TEST_DOC_ROOT_URI, "index.rst")
CONF_PY_CUSTOM_DIRECTIVE_SNIPPETS_REQ = """\
.. req:: REQ Example
   :id: ID
   :status:
   :custom_option_1:

   random content.
"""
CONF_PY_CUSTOM_DIRECTIVE_SNIPPETS_TEST = """\
.. test:: Test Title
   :id: TEST_
   :status: open
   :custom_option: something

   test directive content.
"""


@pytest_lsp.fixture(
    config=pytest_lsp.ClientServerConfig(server_command=[sys.executable, "-m", "esbonio"], root_uri=TEST_DOC_ROOT_URI),
)
async def client():
    pass


@pytest.mark.skipif(
    version.parse(__version__) >= version.parse("1.0"), reason="Esbonio version >=0.16.0 using pygls >= 1.0 not tested."
)
@pytest.mark.asyncio
async def test_lsp_custom_directive_snippets(client):
    # check need custom directive snippets completion
    need_custom_directive_snippets = await client.completion_request(uri=TEST_FILE_URI, line=10, character=2)
    assert need_custom_directive_snippets

    req_snippet_idx = None
    test_snippet_idx = None
    spec_snippet_idx = None
    for index, item in enumerate(need_custom_directive_snippets.items):
        if item.label == ".. req::":
            req_snippet_idx = index
        elif item.label == ".. test::":
            test_snippet_idx = index
        elif item.label == ".. spec::":
            spec_snippet_idx = index

    # check custom directive snippets
    assert req_snippet_idx is not None
    need_custom_directive_snippets_req = need_custom_directive_snippets.items[req_snippet_idx]
    assert need_custom_directive_snippets_req.label == ".. req::"
    assert need_custom_directive_snippets_req.detail == "Requirement"
    assert need_custom_directive_snippets_req.insert_text == CONF_PY_CUSTOM_DIRECTIVE_SNIPPETS_REQ
    assert need_custom_directive_snippets_req.insert_text_format == 2  # InsertTextFormat.Snippet
    assert need_custom_directive_snippets_req.kind == 15  # CompletionItemKind.Snippet
    assert need_custom_directive_snippets_req.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"

    assert test_snippet_idx is not None
    need_custom_directive_snippets_test = need_custom_directive_snippets.items[test_snippet_idx]
    assert need_custom_directive_snippets_test.label == ".. test::"
    assert need_custom_directive_snippets_test.detail == "Test Case"
    assert need_custom_directive_snippets_test.insert_text == CONF_PY_CUSTOM_DIRECTIVE_SNIPPETS_TEST
    assert need_custom_directive_snippets_test.insert_text_format == 2  # nsertTextFormat.Snippet
    assert need_custom_directive_snippets_test.kind == 15  # CompletionItemKind.Snippet
    assert need_custom_directive_snippets_test.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"

    # check default directive snippets
    assert spec_snippet_idx is not None
    need_custom_directive_snippets_spec = need_custom_directive_snippets.items[spec_snippet_idx]
    assert need_custom_directive_snippets_spec.label == ".. spec::"
    assert need_custom_directive_snippets_spec.detail == "Specification"
    assert need_custom_directive_snippets_spec.insert_text.startswith(" spec:: ${1:title}\n\t:id: ${2:SPEC_")
    assert need_custom_directive_snippets_spec.insert_text.endswith("}\n\t:status: open\n\n\t${3:content}.\n$0")
    assert need_custom_directive_snippets_spec.insert_text_format == 2  # InsertTextFormat.Snippet
    assert need_custom_directive_snippets_spec.kind == 15  # CompletionItemKind.Snippet
    assert need_custom_directive_snippets_spec.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"
