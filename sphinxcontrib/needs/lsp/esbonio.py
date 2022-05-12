"""Suport Sphinx-Needs language features."""
import getpass
import os
import re
from hashlib import blake2b
from typing import List, Tuple

from esbonio.lsp import LanguageFeature
from esbonio.lsp.rst import CompletionContext
from esbonio.lsp.sphinx import SphinxLanguageServer

from pygls.lsp.types import (
    CompletionItem,
    CompletionItemKind,
    InsertTextFormat,
    Position,
    Range,
    TextEdit,
)

from sphinxcontrib.needs.lsp.needs_store import NeedsStore


def col_to_word_index(col: int, words: List[str]) -> int:
    """Return the index of a word in a list of words for a given line character column."""
    length = 0
    index = 0
    for word in words:
        length = length + len(word)
        if col <= length + index:
            return index
        index = index + 1
    return index - 1


def get_lines(ls, params) -> List[str]:
    """Get all text lines in the current document."""
    # text_doc = ls.workspace.get_document(params.text_document.uri)
    text_doc = params.doc
    ls.logger.debug(f"text_doc: {text_doc}")
    source = text_doc.source
    return source.splitlines()


def get_word(ls, params) -> str:
    """Return the word in a line of text at a character position."""
    line_no, col = params.position
    lines = get_lines(ls, params)
    if line_no >= len(lines):
        return ""
    line = lines[line_no]
    words = line.split()
    index = col_to_word_index(col, words)
    return words[index]


def get_lines_and_word(ls, params) -> Tuple[List[str], str]:
    return (get_lines(ls, params), get_word(ls, params))


def doc_completion_items(ls, docs: List[str], doc_pattern: str) -> List[CompletionItem]:
    """Return completion items for a given doc pattern."""

    # calc all doc paths that start with the given pattern
    all_paths = [doc for doc in docs if doc.startswith(doc_pattern)]

    if len(all_paths) == 0:
        return

    # leave if there is just one path
    if len(all_paths) == 1:
        insert_text = all_paths[0][len(doc_pattern) :]
        return [
            CompletionItem(
                label=insert_text,
                insert_text=insert_text,
                kind=CompletionItemKind.File,
                detail="needs doc",
            )
        ]

    # look at increasingly longer paths
    # stop if there are at least two options
    max_path_length = max(path.count("/") for path in all_paths)
    current_path_length = doc_pattern.count("/")

    if max_path_length == current_path_length == 0:
        sub_paths = all_paths
        return [
            CompletionItem(
                label=sub_path, kind=CompletionItemKind.File, detail="path to needs doc"
            )
            for sub_path in sub_paths
        ]

    # create list that contains only paths up to current path length
    sub_paths = []
    for path in all_paths:
        if path.count("/") >= current_path_length:
            new_path = "/".join(
                path.split("/")[current_path_length : current_path_length + 1]
            )
            if new_path not in sub_paths:
                sub_paths.append(new_path)
    sub_paths.sort()

    items = []
    for sub_path in sub_paths:
        if sub_path.find(".rst") > -1:
            kind = CompletionItemKind.File
        else:
            kind = 19  # Folder
        items.append(
            CompletionItem(label=sub_path, kind=kind, detail="path to needs doc")
        )
    return items


def complete_need_link(
    ls, params: CompletionContext, lines: List[str], line: str, word: str
):
    # specify the need type, e.g.,
    # ->req
    if word.count(">") == 1:
        return [
            CompletionItem(label=need_type, detail="need type")
            for need_type in ls.needs_store.types
        ]

    word_parts = word.split(">")

    # specify doc in which need is specified, e.g.,
    # ->req>fusion/index.rst
    if word.count(">") == 2:
        requested_type = word_parts[1]  # e.g., req, test, ...
        if requested_type in ls.needs_store.types:
            return doc_completion_items(
                ls, ls.needs_store.docs_per_type[requested_type], word_parts[2]
            )

    # specify the exact need, e.g.,
    # ->req>fusion/index.rst>REQ_001
    if word.count(">") == 3:
        requested_type = word_parts[1]  # e.g., req, test, ...
        requested_doc = word_parts[2]  # [0:-4]  # without `.rst` file extension
        if requested_doc in ls.needs_store.needs_per_doc:
            substitution = word[word.find("->") :]
            start_char = line.find(substitution)
            line_number = params.position.line
            return [
                CompletionItem(
                    label=need["id"],
                    insert_text=need["id"],
                    documentation=need["description"],
                    detail=need["title"],
                    additional_text_edits=[
                        TextEdit(
                            range=Range(
                                start=Position(
                                    line=line_number, character=start_char
                                ),
                                end=Position(
                                    line=line_number,
                                    character=start_char + len(substitution),
                                ),
                            ),
                            new_text="",
                        )
                    ],
                )
                for need in ls.needs_store.needs_per_doc[requested_doc]
                if need["type"] == requested_type
            ]


def generate_hash(user_name, doc_uri, need_prefix, line_number):
    salt = os.urandom(blake2b.SALT_SIZE)  # pylint: disable=no-member
    return blake2b(
        f"{user_name}{doc_uri}{need_prefix}{line_number}".encode(),
        digest_size=4,
        salt=salt,
    ).hexdigest()


def generate_need_id(
    ls, params, lines: List[str], word: str, need_type: str = None
) -> str:
    """Generate a need ID including hash suffix."""

    user_name = getpass.getuser()
    #doc_uri = params.text_document.uri
    doc_uri = params.doc.uri
    line_number = params.position.line

    if not need_type:
        try:
            match = re.search(".. ([a-z]+)::", lines[line_number - 1])
            need_type = match.group(1)
        except AttributeError:
            return "ID"

    need_prefix = need_type.upper()
    hash_part = generate_hash(user_name, doc_uri, need_prefix, line_number)
    need_id = need_prefix + "_" + hash_part
    # re-generate hash if ID is already in use
    while need_id in ls.needs_store.needs:
        hash_part = generate_hash(user_name, doc_uri, need_prefix, line_number)
        need_id = need_prefix + "_" + hash_part
    return need_id


def complete_directive(ls, params, lines: List[str], word: str):
    # need_type ~ req, work, act, ...
    items = []
    for need_type, title in ls.needs_store.declared_types.items():
        text = (
            " " + need_type + ":: ${1:title}\n"
            "\t:id: ${2:"
            + generate_need_id(ls, params, lines, word, need_type=need_type)
            + "}\n"
            "\t:status: open\n\n"
            "\t${3:content}.\n$0"
        )
        label = f".. {need_type}::"
        items.append(
            CompletionItem(
                label=label,
                detail=title,
                insert_text=text,
                insert_text_format=InsertTextFormat.Snippet,
                kind=CompletionItemKind.Snippet,
            )
        )
    return items


def complete_role_or_option(ls, params, lines: List[str], word: str):
    return [
        CompletionItem(
            label=":id:",
            detail="needs option",
            insert_text="id: ${1:"
            + generate_need_id(ls, params, lines, word)
            + "}\n$0",
            insert_text_format=InsertTextFormat.Snippet,
            kind=CompletionItemKind.Snippet,
        ),
        CompletionItem(
            label=":need:",
            detail="need role",
            insert_text="need:`${1:ID}` $0",
            insert_text_format=InsertTextFormat.Snippet,
            kind=CompletionItemKind.Snippet,
        ),
    ]


class NeedlsFeatures(LanguageFeature):
    """Sphinx-Needs features support for the language server."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.needs_store = NeedsStore()

    # TODO: need to finish this later after testing
    # Open-Needs-IDE language features completion triggers: '>', '/', ':', '.'
    completion_triggers = [re.compile(r'(?P<test>.*)')]

    def complete(self, context: CompletionContext) -> List[CompletionItem]:
        self.logger.debug(f"Needls context: {context}")

        # TODO: how to trigger load needs.json???? where to find needs.json???
        needs_json = "../../../vscode-restructuredtext/docs/_build/needs/needs.json"
        self.needs_store.load_needs(needs_json)

        self.logger.debug(f"NeedsStore needs: {self.needs_store.needs}")
        # check if needs initialzed
        if not self.needs_store.needs_initialized:
            return []

        lines, word = get_lines_and_word(self, context)
        line_number = context.position.line
        if line_number >= len(lines):
            self.logger.info(
                f"line {line_number} is empty, no completion trigger characters detected"
            )
            return []
        line = lines[line_number]

        # TODO: why not fully working???
        # if word starts with '->' or ':need:->', complete_need_link
        if word.startswith("->") or word.startswith(":need:`->"):
            new_word = word.replace(":need:`->", "->")
            new_word = new_word.replace("`", "")  # in case need:`->...>...`
            return complete_need_link(self, context, lines, line, new_word)

        # if word starts with ':', complete_role_or_option
        if word.startswith(":"):
            return complete_role_or_option(self, context, lines, word)

        # if word starts with '..', complete_directive
        if word.startswith(".."):
            return complete_directive(self, context, lines, word)



def esbonio_setup(rst: SphinxLanguageServer):
    rst.logger.debug("Starting register Sphinx-Needs language features...")
    needls_features = NeedlsFeatures(rst)
    rst.add_feature(needls_features)

    sphinx_needs_feature = rst.get_feature("sphinxcontrib.needs.esbonio.NeedlsFeatures")
    rst.logger.debug(f"Registered Sphinx-Needs language features: {sphinx_needs_feature}.")

    if sphinx_needs_feature:
        rst.logger.debug(f"Successfully registered Sphinx-Needs language features: {sphinx_needs_feature}.")
