"""Test Sphinx-Needs language features for custom directive snippets."""

import os
import sys

import pytest
import pytest_lsp

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


@pytest.mark.asyncio
async def test_lsp_custom_directive_snippets(client):
    # check need custom directive snippets completion
    need_custom_directive_snippets = await client.completion_request(uri=TEST_FILE_URI, line=10, character=2)
    assert need_custom_directive_snippets

    # check custom directive snippets
    need_custom_directive_snippets_req = need_custom_directive_snippets.items[165]
    assert need_custom_directive_snippets_req.label == ".. req::"
    assert need_custom_directive_snippets_req.detail == "Requirement"
    assert need_custom_directive_snippets_req.insert_text == CONF_PY_CUSTOM_DIRECTIVE_SNIPPETS_REQ
    assert need_custom_directive_snippets_req.insert_text_format == 2  # InsertTextFormat.Snippet
    assert need_custom_directive_snippets_req.kind == 15  # CompletionItemKind.Snippet
    assert need_custom_directive_snippets_req.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"

    need_custom_directive_snippets_test = need_custom_directive_snippets.items[168]
    assert need_custom_directive_snippets_test.label == ".. test::"
    assert need_custom_directive_snippets_test.detail == "Test Case"
    assert need_custom_directive_snippets_test.insert_text == CONF_PY_CUSTOM_DIRECTIVE_SNIPPETS_TEST
    assert need_custom_directive_snippets_test.insert_text_format == 2  # nsertTextFormat.Snippet
    assert need_custom_directive_snippets_test.kind == 15  # CompletionItemKind.Snippet
    assert need_custom_directive_snippets_test.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"

    # check default directive snippets
    need_custom_directive_snippets_spec = need_custom_directive_snippets.items[166]
    assert need_custom_directive_snippets_spec.label == ".. spec::"
    assert need_custom_directive_snippets_spec.detail == "Specification"
    assert need_custom_directive_snippets_spec.insert_text.startswith(" spec:: ${1:title}\n\t:id: ${2:SPEC_")
    assert need_custom_directive_snippets_spec.insert_text.endswith("}\n\t:status: open\n\n\t${3:content}.\n$0")
    assert need_custom_directive_snippets_spec.insert_text_format == 2  # InsertTextFormat.Snippet
    assert need_custom_directive_snippets_spec.kind == 15  # CompletionItemKind.Snippet
    assert need_custom_directive_snippets_spec.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"
