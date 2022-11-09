"""Test Sphinx-Needs language features MyST/Markdown support."""

import os
import sys

import pytest
import pytest_lsp
from pygls.lsp.types import MarkupContent, MarkupKind, Position, Range

TEST_DOC_ROOT_URI = os.path.join("file://", os.path.abspath(os.path.dirname(__file__)), "doc_lsp_support_MyST")
TEST_MD_FILE_URI = os.path.join(TEST_DOC_ROOT_URI, "myfile.md")


@pytest_lsp.fixture(
    config=pytest_lsp.ClientServerConfig(server_command=[sys.executable, "-m", "esbonio"], root_uri=TEST_DOC_ROOT_URI),
)
async def client():
    pass


@pytest.mark.asyncio
async def test_lsp_goto_definition_support_for_myst(client):
    # Check Goto Defintion support for MySt/Markdown file, e.g. myfile.md
    goto_md = await client.definition_request(uri=TEST_MD_FILE_URI, position=Position(line=19, character=8))
    goto_md_location = goto_md[0]

    assert goto_md_location.range
    assert type(goto_md_location.range) == Range

    # check defintion location range, e.g. location of SPEC_2
    assert goto_md_location.range.start.line == 12
    assert goto_md_location.range.start.character == 0
    assert goto_md_location.range.end.line == 12
    assert goto_md_location.range.end.character == 0

    # Check Goto defintion jump location in another markdown file, e.g. md_subfolder/MySecond.md
    goto_md_subfolder = await client.definition_request(uri=TEST_MD_FILE_URI, position=Position(line=21, character=8))
    goto_md_subfolder_location = goto_md_subfolder[0]

    assert goto_md_subfolder_location.range
    assert type(goto_md_subfolder_location.range) == Range

    # check defintion location range, e.g. location of REQ_3
    assert goto_md_subfolder_location.uri.endswith("MySecond.md")
    assert goto_md_subfolder_location.range.start.line == 2
    assert goto_md_subfolder_location.range.start.character == 0
    assert goto_md_subfolder_location.range.end.line == 2
    assert goto_md_subfolder_location.range.end.character == 0

    # Check Goto definition jump location in another rst file, e.g. index.rst
    goto_rst = await client.definition_request(uri=TEST_MD_FILE_URI, position=Position(line=23, character=8))
    goto_rst_location = goto_rst[0]

    assert goto_rst_location.range
    assert type(goto_rst_location.range) == Range

    # check defintion location range, e.g. location of REQ_1
    assert goto_rst_location.uri.endswith("index.rst")
    assert goto_rst_location.range.start.line == 10
    assert goto_rst_location.range.start.character == 0
    assert goto_rst_location.range.end.line == 10
    assert goto_rst_location.range.end.character == 0


@pytest.mark.asyncio
async def test_lsp_hover_support_for_myst(client):
    # Check Hover support for MyST/Markdown file
    hover_directive_result = await client.hover_request(uri=TEST_MD_FILE_URI, position=Position(line=6, character=9))
    assert type(hover_directive_result.contents) == MarkupContent
    assert type(hover_directive_result.contents.kind) == MarkupKind
    assert hover_directive_result.contents.kind == "markdown"  # MarkupKind.Markdown
    assert hover_directive_result.contents.value == "**MD REQ Title**\n\n```\nsome stuff from md req.\n```"

    # Check Hover support for need in another markdown file, e.g. REQ_3
    hover_directive_another_file = await client.hover_request(
        uri=TEST_MD_FILE_URI, position=Position(line=21, character=8)
    )
    assert type(hover_directive_another_file.contents) == MarkupContent
    assert type(hover_directive_another_file.contents.kind) == MarkupKind
    assert hover_directive_another_file.contents.kind == "markdown"  # MarkupKind.Markdown
    assert (
        hover_directive_another_file.contents.value
        == "\n**Sub MD Req title**\n\n```\nMD in Subfolder with some req content.\n```"
    )


@pytest.mark.asyncio
async def test_lsp_id_selection_completion_support_for_myst(client):
    # Check ID selection completion support for MyST/Markdown file
    # 1. for rst/Sphinx style: :need:`->`
    # 2. for MyST/Markdown style: {need}`->`

    # check need type suggestion for :need:`->`
    need_type_rst = await client.completion_request(uri=TEST_MD_FILE_URI, line=25, character=9)
    assert len(need_type_rst.items) == 2
    assert need_type_rst.items[0].label == "req"
    assert need_type_rst.items[0].detail == "need type"
    assert need_type_rst.items[1].label == "spec"
    assert need_type_rst.items[1].detail == "need type"

    # check need file path suggestion for :need:`->req>`
    need_file_path_rst = await client.completion_request(uri=TEST_MD_FILE_URI, line=27, character=13)
    assert len(need_file_path_rst.items) == 3

    need_file_path_rst_option_1 = need_file_path_rst.items[0]
    assert need_file_path_rst_option_1.label == "index.rst"
    assert need_file_path_rst_option_1.detail == "path to needs doc"
    assert need_file_path_rst_option_1.kind == 17  # CompletionItemKind.File
    assert need_file_path_rst_option_1.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"

    need_file_path_rst_option_2 = need_file_path_rst.items[1]
    assert need_file_path_rst_option_2.label == "md_subfolder"
    assert need_file_path_rst_option_2.kind == 19  # CompletionItemKind.Folder

    need_file_path_rst_option_3 = need_file_path_rst.items[2]
    assert need_file_path_rst_option_3.label == "myfile.md"
    assert need_file_path_rst_option_3.kind == 17  # CompletionItemKind.File

    # check need file path suggestion containing subfolder for :need:`->req>md_subfolder/`
    need_file_path_subfolder_rst = await client.completion_request(uri=TEST_MD_FILE_URI, line=31, character=26)
    assert len(need_file_path_subfolder_rst.items) == 1
    assert need_file_path_subfolder_rst.items[0].label == "MySecond.md"
    assert need_file_path_subfolder_rst.items[0].detail == "needs doc"
    assert need_file_path_subfolder_rst.items[0].insert_text == "MySecond.md"
    assert need_file_path_subfolder_rst.items[0].kind == 17  # CompletionItemKind.File

    # check need ID suggestion for :need:`->req>md_subfolder/MySecond.md>`
    need_id_rst = await client.completion_request(uri=TEST_MD_FILE_URI, line=33, character=38)
    assert len(need_id_rst.items) == 1
    assert need_id_rst.items[0].label == "REQ_3"
    assert need_id_rst.items[0].insert_text == "REQ_3"
    assert need_id_rst.items[0].detail == "Sub MD Req title"
    assert need_id_rst.items[0].documentation == "MD in Subfolder with some req content."

    # check need type suggestion for {need}`->`
    need_type_md = await client.completion_request(uri=TEST_MD_FILE_URI, line=35, character=9)
    assert len(need_type_md.items) == 2
    assert need_type_md.items[0].label == "req"
    assert need_type_md.items[0].detail == "need type"
    assert need_type_md.items[1].label == "spec"
    assert need_type_md.items[1].detail == "need type"

    # check need file path suggestion for {need}`->req>`
    need_file_path_md = await client.completion_request(uri=TEST_MD_FILE_URI, line=37, character=13)
    assert len(need_file_path_md.items) == 3

    need_file_path_md_option_1 = need_file_path_md.items[0]
    assert need_file_path_md_option_1.label == "index.rst"
    assert need_file_path_md_option_1.detail == "path to needs doc"
    assert need_file_path_md_option_1.kind == 17  # CompletionItemKind.File
    assert need_file_path_md_option_1.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"

    need_file_path_md_option_2 = need_file_path_md.items[1]
    assert need_file_path_md_option_2.label == "md_subfolder"
    assert need_file_path_md_option_2.kind == 19  # CompletionItemKind.Folder

    need_file_path_md_option_3 = need_file_path_md.items[2]
    assert need_file_path_md_option_3.label == "myfile.md"
    assert need_file_path_md_option_3.kind == 17  # CompletionItemKind.File

    # check need ID suggestion for :need:`->req>myfile.md>`
    need_id_md = await client.completion_request(uri=TEST_MD_FILE_URI, line=29, character=23)
    assert len(need_id_md.items) == 1
    need_id_md_result = need_id_md.items[0]
    assert need_id_md_result.label == "REQ_2"
    assert need_id_md_result.insert_text == "REQ_2"
    assert need_id_md_result.detail == "MD REQ Title"
    assert need_id_md_result.documentation == "some stuff from md req."
    assert need_id_md_result.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"


@pytest.mark.asyncio
async def test_lsp_need_directive_snippets_completion_for_myst(client):
    # Check need directive snippets support for MyST/Markdown
    needs_directive_snippets_suggestion = await client.completion_request(uri=TEST_MD_FILE_URI, line=47, character=2)
    assert needs_directive_snippets_suggestion.items

    req_md_idx = None
    spec_md_idx = None
    for index, item in enumerate(needs_directive_snippets_suggestion.items):
        if item.label == "md:.. req::":
            req_md_idx = index
        if item.label == "md:.. spec::":
            spec_md_idx = index

    assert req_md_idx is not None
    needs_directive_req_md = needs_directive_snippets_suggestion.items[req_md_idx]
    assert needs_directive_req_md.label == "md:.. req::"
    assert needs_directive_req_md.detail == "Markdown directive snippet"
    assert needs_directive_req_md.insert_text.startswith("```{req} ${1:title}\n:id: ${2:REQ_")
    assert needs_directive_req_md.insert_text.endswith("}\n:status: open\n\n${3:content}.\n```$0")
    assert needs_directive_req_md.insert_text_format == 2  # InsertTextFormat.Snippet
    assert needs_directive_req_md.kind == 15  # CompletionItemKind.Snippet
    assert needs_directive_req_md.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"

    assert spec_md_idx is not None
    needs_directive_spec_md = needs_directive_snippets_suggestion.items[spec_md_idx]
    assert needs_directive_spec_md.label == "md:.. spec::"
    assert needs_directive_spec_md.detail == "Markdown directive snippet"
    assert needs_directive_spec_md.insert_text.startswith("```{spec} ${1:title}\n:id: ${2:SPEC_")
    assert needs_directive_spec_md.insert_text.endswith("}\n:status: open\n\n${3:content}.\n```$0")
    assert needs_directive_spec_md.insert_text_format == 2  # InsertTextFormat.Snippet
    assert needs_directive_spec_md.kind == 15  # CompletionItemKind.Snippet
    assert needs_directive_spec_md.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"

    # check need directive snippets inside block {eval-rst}
    needs_directive_snippets_inside_eval_rst_suggestion = await client.completion_request(
        uri=TEST_MD_FILE_URI, line=5, character=2
    )
    assert needs_directive_snippets_inside_eval_rst_suggestion.items

    req_md_in_eval_rst_idx = None
    spec_md_in_eval_rst_idx = None
    for index, item in enumerate(needs_directive_snippets_inside_eval_rst_suggestion.items):
        if item.label == ".. req::":
            req_md_in_eval_rst_idx = index
        if item.label == ".. spec::":
            spec_md_in_eval_rst_idx = index

    assert req_md_in_eval_rst_idx is not None
    needs_directive_req_md_inside_eval_rst = needs_directive_snippets_inside_eval_rst_suggestion.items[
        req_md_in_eval_rst_idx
    ]
    assert needs_directive_req_md_inside_eval_rst.label == ".. req::"
    assert needs_directive_req_md_inside_eval_rst.detail == "Requirement"
    assert needs_directive_req_md_inside_eval_rst.insert_text.startswith(" req:: ${1:title}\n\t:id: ${2:REQ_")
    assert needs_directive_req_md_inside_eval_rst.insert_text.endswith("}\n\t:status: open\n\n\t${3:content}.\n$0")
    assert needs_directive_req_md_inside_eval_rst.insert_text_format == 2  # InsertTextFormat.Snippet
    assert needs_directive_req_md_inside_eval_rst.kind == 15  # CompletionItemKind.Snippet
    assert needs_directive_req_md_inside_eval_rst.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"

    assert spec_md_in_eval_rst_idx is not None
    needs_directive_spec_md_inside_eval_rst = needs_directive_snippets_inside_eval_rst_suggestion.items[
        spec_md_in_eval_rst_idx
    ]
    assert needs_directive_spec_md_inside_eval_rst.label == ".. spec::"
    assert needs_directive_spec_md_inside_eval_rst.detail == "Specification"
    assert needs_directive_spec_md_inside_eval_rst.insert_text.startswith(" spec:: ${1:title}\n\t:id: ${2:SPEC_")
    assert needs_directive_spec_md_inside_eval_rst.insert_text.endswith("}\n\t:status: open\n\n\t${3:content}.\n$0")
    assert needs_directive_spec_md_inside_eval_rst.insert_text_format == 2  # InsertTextFormat.Snippet
    assert needs_directive_spec_md_inside_eval_rst.kind == 15  # CompletionItemKind.Snippet
    assert needs_directive_spec_md_inside_eval_rst.data["source_feature"] == "sphinx_needs.lsp.esbonio.NeedlsFeatures"


@pytest.mark.asyncio
async def test_lsp_needs_option_id_completion_for_myst(client):
    # Needs option id suggestion is the same for MyST/Markdown as for rst/Sphinx file, e.g. :id:
    needs_option_suggestion = await client.completion_request(uri=TEST_MD_FILE_URI, line=13, character=1)
    assert needs_option_suggestion.items

    option_id_idx = None
    for index, item in enumerate(needs_option_suggestion.items):
        if item.label == ":id:":
            option_id_idx = index

    assert option_id_idx is not None
    needs_option_id = needs_option_suggestion.items[option_id_idx]
    assert needs_option_id.label == ":id:"
    assert needs_option_id.detail == "needs option"
    assert needs_option_id.insert_text.startswith("id: ${1:SPEC_")
    assert needs_option_id.insert_text.endswith("}\n$0")
    assert needs_option_id.insert_text_format == 2  # InsertTextFormat.Snippet
    assert needs_option_id.kind == 15  # CompletionItemKind.Snippet


@pytest.mark.asyncio
async def test_lsp_need_role_need_completion_for_myst(client):
    # Need role need support for MyST/Markdown file
    # Same usage like rst file, but will be adapted to MyST/Markdown style, which isinsert {need}`` instead of :need:
    need_role_need_suggestion = await client.completion_request(uri=TEST_MD_FILE_URI, line=45, character=1)
    assert need_role_need_suggestion.items

    need_role_idx = None
    for index, item in enumerate(need_role_need_suggestion.items):
        if item.label == "md::need:":
            need_role_idx = index

    assert need_role_idx is not None
    need_role_need = need_role_need_suggestion.items[need_role_idx]
    assert need_role_need.label == "md::need:"
    assert need_role_need.detail == "Markdown need role"
    assert need_role_need.insert_text == "{need}`${1:ID}`$0"
    assert need_role_need.insert_text_format == 2  # InsertTextFormat.Snippet
    assert need_role_need.kind == 15  # CompletionItemKind.Snippet
