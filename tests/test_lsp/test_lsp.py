"""Test Sphinx-Needs language features."""

import os
import sys

import pytest
import pytest_lsp
from pygls.lsp.types import MarkupContent, MarkupKind, Position, Range

TEST_DOC_ROOT_URI = os.path.join("file://", os.path.abspath(os.path.dirname(__file__)), "doc_example_lsp")
TEST_FILE_URI = os.path.join(TEST_DOC_ROOT_URI, "index.rst")


@pytest_lsp.fixture(
    config=pytest_lsp.ClientServerConfig(server_command=[sys.executable, "-m", "esbonio"], root_uri=TEST_DOC_ROOT_URI),
)
async def client():
    pass


@pytest.mark.asyncio
async def test_need_directive_role_completion(client):
    # check needs directive completion
    need_directive_result = await client.completion_request(uri=TEST_FILE_URI, line=10, character=3)
    assert len(need_directive_result.items) > 0

    # check user in conf.py defined need directive req exists
    need_req = need_directive_result.items[81]
    assert need_req.label == "req"
    assert need_req.filter_text == ".. req::"
    assert need_req.detail == "sphinx_needs.directives.need.NeedDirective"
    assert need_req.kind == 7  # CompletionItemKind.Class
    assert need_req.insert_text_format == 1  # InsertTextFormat.PlainText
    assert need_req.data["source_feature"] == "esbonio.lsp.directives.Directives"
    assert need_req.data["completion_type"] == "directive"

    # check user in conf.py need directive spec exists
    need_spec = need_directive_result.items[82]
    assert need_spec.label == "spec"
    assert need_spec.filter_text == ".. spec::"
    assert need_spec.detail == "sphinx_needs.directives.need.NeedDirective"
    assert need_spec.kind == 7  # CompletionItemKind.Class
    assert need_spec.insert_text_format == 1  # InsertTextFormat.PlainText
    assert need_spec.data["source_feature"] == "esbonio.lsp.directives.Directives"
    assert need_spec.data["completion_type"] == "directive"

    # check other in conf.py defined need directives also exist
    need_impl = need_directive_result.items[83]
    assert need_impl.label == "impl"
    assert need_impl.filter_text == ".. impl::"
    assert need_impl.detail == "sphinx_needs.directives.need.NeedDirective"

    need_test = need_directive_result.items[84]
    assert need_test.label == "test"
    assert need_test.filter_text == ".. test::"
    assert need_test.detail == "sphinx_needs.directives.need.NeedDirective"

    need_need = need_directive_result.items[85]
    assert need_need.label == "need"
    assert need_need.filter_text == ".. need::"
    assert need_need.detail == "sphinx_needs.directives.need.NeedDirective"

    # check Sphinx-Needs default supported derectives exist
    need_needarch = need_directive_result.items[80]
    assert need_needarch.label == "needarch"
    assert need_needarch.filter_text == ".. needarch::"
    assert need_needarch.detail == "sphinx_needs.directives.needuml.NeedarchDirective"
    assert need_needarch.kind == 7  # CompletionItemKind.Class
    assert need_needarch.insert_text_format == 1  # InsertTextFormat.PlainText
    assert need_needarch.data["source_feature"] == "esbonio.lsp.directives.Directives"
    assert need_needarch.data["completion_type"] == "directive"

    need_needlist = need_directive_result.items[68]
    assert need_needlist.label == "needlist"
    assert need_needlist.filter_text == ".. needlist::"
    assert need_needlist.detail == "sphinx_needs.directives.needlist.NeedlistDirective"
    assert need_needlist.kind == 7  # CompletionItemKind.Class
    assert need_needlist.insert_text_format == 1  # InsertTextFormat.PlainText
    assert need_needlist.data["source_feature"] == "esbonio.lsp.directives.Directives"
    assert need_needlist.data["completion_type"] == "directive"

    need_needimport = need_directive_result.items[74]
    assert need_needimport.label == "needimport"
    assert need_needimport.filter_text == ".. needimport::"
    assert need_needimport.detail == "sphinx_needs.directives.needimport.NeedimportDirective"

    # check need options for need directive req
    need_req_options_result = await client.completion_request(uri=TEST_FILE_URI, line=11, character=3)
    assert len(need_req_options_result.items) > 0

    # check need directive option id exists
    need_req_option_id = need_req_options_result.items[0]
    assert need_req_option_id.label == "id"
    assert need_req_option_id.filter_text == ":id:"
    assert need_req_option_id.detail == "sphinx_needs.directives.need.NeedDirective:id"
    assert need_req_option_id.kind == 5  # CompletionItemKind.Field
    assert need_req_option_id.data["source_feature"] == "esbonio.lsp.directives.Directives"
    assert need_req_option_id.data["completion_type"] == "directive_option"
    assert need_req_option_id.data["for_directive"] == "req"

    # check need directive option status exists
    need_req_option_status = need_req_options_result.items[1]
    assert need_req_option_status.label == "status"
    assert need_req_option_status.detail == "sphinx_needs.directives.need.NeedDirective:status"
    assert need_req_option_status.kind == 5  # CompletionItemKind.Field
    assert need_req_option_status.data["source_feature"] == "esbonio.lsp.directives.Directives"
    assert need_req_option_status.data["completion_type"] == "directive_option"
    assert need_req_option_status.data["for_directive"] == "req"

    # check need options for need directive spec
    need_spec_options_result = await client.completion_request(uri=TEST_FILE_URI, line=18, character=3)
    assert len(need_spec_options_result.items) > 0

    need_spec_option_id = need_spec_options_result.items[0]
    assert need_spec_option_id.label == "id"
    assert need_spec_option_id.filter_text == ":id:"
    assert need_spec_option_id.detail == "sphinx_needs.directives.need.NeedDirective:id"
    assert need_spec_option_id.kind == 5  # CompletionItemKind.Field
    assert need_spec_option_id.data["source_feature"] == "esbonio.lsp.directives.Directives"
    assert need_spec_option_id.data["completion_type"] == "directive_option"
    assert need_spec_option_id.data["for_directive"] == "spec"

    need_spec_option_status = need_spec_options_result.items[1]
    assert need_spec_option_status.label == "status"
    assert need_spec_option_status.filter_text == ":status:"
    assert need_spec_option_status.detail == "sphinx_needs.directives.need.NeedDirective:status"
    assert need_spec_option_status.kind == 5  # CompletionItemKind.Field
    assert need_spec_option_status.data["source_feature"] == "esbonio.lsp.directives.Directives"
    assert need_spec_option_status.data["completion_type"] == "directive_option"
    assert need_spec_option_status.data["for_directive"] == "spec"

    # check need role completion
    need_role_result = await client.completion_request(uri=TEST_FILE_URI, line=24, character=1)
    assert len(need_role_result.items) > 0

    need_role_need = need_role_result.items[92]
    assert need_role_need.label == ":need:"
    assert need_role_need.detail == "need role"
    assert need_role_need.insert_text == "need:`${1:ID}` $0"
    assert need_role_need.insert_text_format == 2  # InsertTextFormat.Snippet
    assert need_role_need.kind == 15  # CompletionItemKind.Snippet
    assert need_role_need.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"


@pytest.mark.asyncio
async def test_need_auto_generated_id_completion(client):
    # check needs option id snippet, auto-generated need IDs, e.g. :id: REQ_e0bafd9b
    need_req_options_result = await client.completion_request(uri=TEST_FILE_URI, line=11, character=3)
    needs_option_id = need_req_options_result.items[19]
    assert needs_option_id.label == ":id:"
    assert needs_option_id.detail == "needs option"
    assert needs_option_id.insert_text.startswith("id: ${1:REQ_")
    assert needs_option_id.insert_text.endswith("}\n$0")
    assert needs_option_id.insert_text_format == 2  # InsertTextFormat.Snippet
    assert needs_option_id.kind == 15  # CompletionItemKind.Snippet


@pytest.mark.asyncio
async def test_need_directive_snippets_completion(client):
    # check need directive snippets completion
    need_directive_snippets = await client.completion_request(uri=TEST_FILE_URI, line=10, character=2)
    assert len(need_directive_snippets.items) > 0

    need_directive_snippets_req = need_directive_snippets.items[165]
    assert need_directive_snippets_req.label == ".. req::"
    assert need_directive_snippets_req.detail == "Requirement"
    assert need_directive_snippets_req.insert_text.startswith(" req:: ${1:title}\n\t:id: ${2:REQ_")
    assert need_directive_snippets_req.insert_text.endswith("}\n\t:status: open\n\n\t${3:content}.\n$0")
    assert need_directive_snippets_req.insert_text_format == 2  # InsertTextFormat.Snippet
    assert need_directive_snippets_req.kind == 15  # CompletionItemKind.Snippet
    assert need_directive_snippets_req.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"


@pytest.mark.asyncio
async def test_need_id_selection_completion(client):
    # check need ID selection completion for need type, e.g. :need:`->`
    id_selection_need_type_result = await client.completion_request(uri=TEST_FILE_URI, line=26, character=9)
    assert len(id_selection_need_type_result.items) == 2
    assert id_selection_need_type_result.items[0].label == "req"
    assert id_selection_need_type_result.items[0].detail == "need type"
    assert id_selection_need_type_result.items[1].label == "spec"
    assert id_selection_need_type_result.items[1].detail == "need type"

    # check need ID selection completion for need file, e.g. :need:`->req>`
    id_selection_need_file_result = await client.completion_request(uri=TEST_FILE_URI, line=28, character=13)
    assert len(id_selection_need_file_result.items) == 1
    id_selection_need_file = id_selection_need_file_result.items[0]
    assert id_selection_need_file.label == "index.rst"
    assert id_selection_need_file.detail == "needs doc"
    assert id_selection_need_file.insert_text == "index.rst"
    assert id_selection_need_file.kind == 17  # CompletionItemKind.File
    assert id_selection_need_file.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"

    # check need ID selection completion for need ID, e.g. :need:`->req>index.rst>`
    id_selection_need_id_result = await client.completion_request(uri=TEST_FILE_URI, line=30, character=23)
    assert len(id_selection_need_id_result.items) == 1
    id_selection_need_id = id_selection_need_id_result.items[0]
    assert id_selection_need_id.label == "REQ_1"
    assert id_selection_need_id.insert_text == "REQ_1"
    assert id_selection_need_id.detail == "First requirement"
    assert id_selection_need_id.documentation == "Requirement content"
    assert id_selection_need_id.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"


@pytest.mark.asyncio
async def test_goto_definition(client):
    # check goto defintion results
    location_result = await client.definition_request(uri=TEST_FILE_URI, position=Position(line=24, character=8))
    defined_location = location_result[0]

    assert defined_location.range
    assert type(defined_location.range) == Range

    # check defintion location range, e.g. for :need:`REQ_1` at line 25, go to definiton for REQ_1 will
    # jump to begining of the definition of REQ_1, which is at line 11, character 0
    assert defined_location.range.start.line == 10
    assert defined_location.range.start.character == 0
    assert defined_location.range.end.line == 10
    assert defined_location.range.end.character == 0


@pytest.mark.asyncio
async def test_hover(client):
    # check hover results
    hover_directive_result = await client.hover_request(uri=TEST_FILE_URI, position=Position(line=18, character=9))
    assert type(hover_directive_result.contents) == MarkupContent
    assert type(hover_directive_result.contents.kind) == MarkupKind
    assert hover_directive_result.contents.kind == "markdown"  # MarkupKind.Markdown
    assert hover_directive_result.contents.value == "**First specification**\n\n```\nSpecification content\n```"

    hover_role_result = await client.hover_request(uri=TEST_FILE_URI, position=Position(line=24, character=8))
    assert type(hover_role_result.contents) == MarkupContent
    assert type(hover_role_result.contents.kind) == MarkupKind
    assert hover_role_result.contents.kind == "markdown"  # MarkupKind.Markdown
    assert hover_role_result.contents.value == "\n**First requirement**\n\n```\nRequirement content\n```"
