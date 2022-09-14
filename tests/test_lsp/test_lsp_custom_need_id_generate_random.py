"""Test Sphinx-Needs language features for custom need ID generation with random()."""

import os
import sys

import pytest
import pytest_lsp

TEST_DOC_ROOT_URI = os.path.join(
    "file://", os.path.abspath(os.path.dirname(__file__)), "doc_lsp_custom_need_id_generate_random"
)
TEST_FILE_URI = os.path.join(TEST_DOC_ROOT_URI, "index.rst")


@pytest_lsp.fixture(
    config=pytest_lsp.ClientServerConfig(server_command=[sys.executable, "-m", "esbonio"], root_uri=TEST_DOC_ROOT_URI),
)
async def client():
    pass


@pytest.mark.asyncio
async def test_directive_snippets_with_custom_need_id_generate_random(client):
    need_directive_snippets = await client.completion_request(uri=TEST_FILE_URI, line=10, character=2)
    assert len(need_directive_snippets.items) > 0

    need_directive_snippets_req = need_directive_snippets.items[145]
    assert need_directive_snippets_req.label == ".. req::"
    assert need_directive_snippets_req.detail == "Requirement"
    assert need_directive_snippets_req.insert_text.startswith(" req:: ${1:title}\n\t:id: ${2:Test_REQ_")
    assert "_Test" in need_directive_snippets_req.insert_text


@pytest.mark.asyncio
async def test_id_auto_generation_with_custom_id_generate_random(client):
    need_req_options_result = await client.completion_request(uri=TEST_FILE_URI, line=11, character=3)
    needs_option_id = need_req_options_result.items[19]
    assert needs_option_id.label == ":id:"
    assert needs_option_id.detail == "needs option"
    assert needs_option_id.insert_text.startswith("id: ${1:Test_REQ_")
    assert needs_option_id.insert_text.endswith("_Test}\n$0")
