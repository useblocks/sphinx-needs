"""Suport Sphinx-Needs language features."""
import getpass
import os
import re
import typing
from hashlib import blake2b
from pathlib import Path
from typing import List, Optional, Tuple, Union

from esbonio.lsp import LanguageFeature
from esbonio.lsp.rst import CompletionContext, DefinitionContext, HoverContext
from esbonio.lsp.sphinx import SphinxLanguageServer
from jinja2 import BaseLoader, Environment
from packaging import version
from pygls import __version__

if version.parse(__version__) < version.parse("1.0"):
    from pygls.lsp.types import (
        CompletionItem,
        CompletionItemKind,
        InsertTextFormat,
        Location,
        Position,
        Range,
        TextEdit,
    )
else:
    from lsprotocol.types import (  # type: ignore[no-redef]
        CompletionItem,
        CompletionItemKind,
        InsertTextFormat,
        Location,
        Position,
        Range,
        TextEdit,
    )

from sphinx.application import Sphinx

from sphinx_needs.lsp.needs_store import NeedsStore


def get_needs_json(app: Sphinx) -> Optional[Path]:
    """
    Get the location of needs.json.
    """

    needs_json = None
    # check if needs.json is built automatically during each sphinx-build,
    # which requres needs_build_json = True in conf.py
    outdir = Path(app.outdir)
    if getattr(app.config, "needs_build_json", False):
        needs_json = outdir / "needs.json"
    else:
        # needs.json is manually built, need to check directory buildDir
        # check buildDir/needs.json, e,g, _build/needs.json, when user using: sphinx-build -b needs srcdir buiddir
        if app.builder and hasattr(app.builder, "name"):
            curr_builder = app.builder.name
            builddir = Path(app.outdir[: -len(curr_builder)])
            needs_json = builddir / "needs.json"

    return needs_json


class NeedlsFeatures(LanguageFeature):
    """Sphinx-Needs features support for the language server."""

    def __init__(self, rst: SphinxLanguageServer) -> None:
        super().__init__(rst)
        self.needs_store = NeedsStore()

    # Open-Needs-IDE language features completion triggers: '>', '/', ':', '.'
    completion_triggers = [re.compile(r"(>)|(\.\.)|(:)|(\/)")]

    def complete(self, context: CompletionContext) -> List[CompletionItem]:

        if isinstance(self.rst, SphinxLanguageServer) and self.rst.app:
            # get and check needs.json path
            needs_json = get_needs_json(self.rst.app)
            if not (needs_json and needs_json.exists()):
                self.logger.warning(f"needs.json {needs_json} not exists. No Sphinx-Needs language features activated.")
                return []

            # load needs.json
            self.needs_store.load_needs(needs_json)

            # check and set conf.py path
            conf_py_path = Path(self.rst.app.srcdir) / "conf.py"
            self.needs_store.set_conf_py(conf_py_path)
            # set declared need types
            self.needs_store.set_declared_types()

            self.logger.debug(f"NeedsStore needs: {self.needs_store.needs}")
            # check if needs initialzed
            if not self.needs_store.needs_initialized:
                return []

            lines, word = get_lines_and_word(self, context)
            line_number = context.position.line
            if line_number >= len(lines):
                self.logger.info(f"line {line_number} is empty, no completion trigger characters detected")
                return []
            line = lines[line_number]

            # if word starts with '->' or ':need:->', complete_need_link
            if word.startswith("->") or word.startswith(":need:`->") or word.startswith("{need}`->"):
                new_word = word.replace(":need:`->", "->")
                if new_word != "->":
                    new_word = word.replace("{need}`->", "->")
                new_word = new_word.replace("`", "")  # in case need:`->...>...`
                return complete_need_link(self, context, lines, line, new_word)

            # if word starts with ':', complete_role_or_option
            if word.startswith(":"):
                return complete_role_or_option(self, context, lines, word)

            # if word starts with '..', complete_directive
            if word.startswith(".."):
                return complete_directive(self, context, lines, word)

            return []

        return []

    hover_triggers = [re.compile(r".*")]

    def hover(self, context: HoverContext) -> str:
        """Return textDocument/hover response value."""
        self.logger.debug(f"hover params: {context}")

        if isinstance(self.rst, SphinxLanguageServer) and self.rst.app:
            # get and check needs.json path
            needs_json = get_needs_json(self.rst.app)
            if not (needs_json and needs_json.exists()):
                self.logger.warning(f"needs.json {needs_json} not exists. No Sphinx-Needs language features activated.")
                return ""

            # load needs.json
            self.needs_store.load_needs(needs_json)

            try:
                need_id = get_need_type_and_id(self, context)[1]
            except IndexError:
                return ""
            if not need_id:
                return ""

            try:
                title = self.needs_store.needs[need_id]["title"]
                description = self.needs_store.needs[need_id]["description"]
                hover_value = f"**{title}**\n\n```\n{description}\n```"
                return hover_value
            except KeyError:
                # need is not in the database
                return ""
        return ""

    definition_triggers = [re.compile(r".*")]

    def definition(self, context: DefinitionContext) -> List[Location]:
        """Return location of definition of a need."""
        if isinstance(self.rst, SphinxLanguageServer) and self.rst.app:
            # get and check needs.json path
            needs_json = get_needs_json(self.rst.app)
            if not (needs_json and needs_json.exists()):
                self.logger.warning(f"needs.json {needs_json} not exists. No Sphinx-Needs language features activated.")
                return []

            # load needs.json
            self.needs_store.load_needs(needs_json)

            if not self.needs_store.is_setup():
                return []

            need_type, need_id = get_need_type_and_id(self, context)

            # get need defining doc
            try:
                need = self.needs_store.needs[need_id]
            except KeyError:
                return []

            doc_path = Path(self.rst.app.srcdir) / typing.cast(str, need["docname"])
            if doc_path.with_suffix(".rst").exists():
                doc_path = doc_path.with_suffix(".rst")
            elif doc_path.with_suffix(".rest").exists():
                doc_path = doc_path.with_suffix(".rest")
            elif doc_path.with_suffix(".md").exists():
                doc_path = doc_path.with_suffix(".md")
            else:
                return []

            # get the need definition position (line, col) from file
            with open(doc_path) as file:
                source_lines = file.readlines()
            # get the line number
            line_count = 0
            line_no = None
            pattern = f":id: {need_id}"
            for line in source_lines:
                if pattern in line:
                    line_no = line_count
                    break
                line_count = line_count + 1
            if not line_no:
                return []

            # get line of directive (e.g., .. req::)
            line_directive = None
            directive_patterns = [f".. {need_type}::", f"```{{{need_type}}}"]
            for line_count in range(line_no - 1, -1, -1):
                if any(dp in source_lines[line_count] for dp in directive_patterns):
                    line_directive = line_count
                    break
            if not line_directive:
                return []

            pos = Position(line=line_directive, character=0)
            return [Location(uri=doc_path.as_uri(), range=Range(start=pos, end=pos))]
        return []


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


def get_lines(ls: NeedlsFeatures, params: Union[CompletionContext, DefinitionContext, HoverContext]) -> List[str]:
    """Get all text lines in the current document."""
    text_doc = params.doc
    ls.logger.debug(f"text_doc: {text_doc}")
    source = text_doc.source
    return source.splitlines()


def get_word(ls: NeedlsFeatures, params: Union[CompletionContext, DefinitionContext, HoverContext]) -> str:
    """Return the word in a line of text at a character position."""
    line_no = params.position.line
    col = params.position.character
    lines = get_lines(ls, params)
    if line_no >= len(lines):
        return ""
    line = lines[line_no]
    words = line.split()
    index = col_to_word_index(col, words)
    word: str = words[index]
    return word


def get_lines_and_word(ls: NeedlsFeatures, params: CompletionContext) -> Tuple[List[str], str]:
    return (get_lines(ls, params), get_word(ls, params))


def get_need_type_and_id(
    ls: NeedlsFeatures, params: Union[DefinitionContext, HoverContext]
) -> Tuple[Optional[str], Optional[str]]:
    """Return tuple (need_type, need_id) for a given document position."""
    word = get_word(ls, params)
    for need in ls.needs_store.needs.values():
        if need["id"] in word:
            return (need["type"], need["id"])
    return (None, None)


def doc_completion_items(ls: NeedlsFeatures, docs: List[str], doc_pattern: str) -> List[CompletionItem]:
    """Return completion items for a given doc pattern."""

    # calc all doc paths that start with the given pattern
    all_paths = [doc for doc in docs if doc.startswith(doc_pattern)]

    if len(all_paths) == 0:
        return []

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
            CompletionItem(label=sub_path, kind=CompletionItemKind.File, detail="path to needs doc")
            for sub_path in sub_paths
        ]

    # create list that contains only paths up to current path length
    sub_paths = []
    for path in all_paths:
        if path.count("/") >= current_path_length:
            new_path = "/".join(path.split("/")[current_path_length : current_path_length + 1])
            if new_path not in sub_paths:
                sub_paths.append(new_path)
    sub_paths.sort()

    items = []
    for sub_path in sub_paths:
        if sub_path.find(".rst") > -1 or sub_path.find(".md") > -1:
            kind = CompletionItemKind.File
        else:
            kind = CompletionItemKind.Folder
        items.append(CompletionItem(label=sub_path, kind=kind, detail="path to needs doc"))
    return items


def complete_need_link(
    ls: NeedlsFeatures, params: CompletionContext, lines: List[str], line: str, word: str
) -> List[CompletionItem]:
    # specify the need type, e.g.,
    # ->req
    if word.count(">") == 1:
        return [CompletionItem(label=need_type, detail="need type") for need_type in ls.needs_store.types]

    word_parts = word.split(">")

    # specify doc in which need is specified, e.g.,
    # ->req>fusion/index.rst
    if word.count(">") == 2:
        requested_type = word_parts[1]  # e.g., req, test, ...
        if requested_type in ls.needs_store.types:
            return doc_completion_items(ls, ls.needs_store.docs_per_type[requested_type], word_parts[2])

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
                                start=Position(line=line_number, character=start_char),
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

    return []


def generate_hash(user_name: str, doc_uri: str, need_prefix: str, line_number: int) -> str:
    salt = os.urandom(blake2b.SALT_SIZE)  # pylint: disable=no-member
    return blake2b(
        f"{user_name}{doc_uri}{need_prefix}{line_number}".encode(),
        digest_size=4,
        salt=salt,
    ).hexdigest()


class JinjaHelperFunction:
    """
    Jinja helper functions.
    """

    def __init__(
        self, ls: NeedlsFeatures, params: CompletionContext, lines: List[str], need_type: Optional[str] = None
    ) -> None:
        self.ls = ls
        self.params = params
        self.lines = lines
        self.need_type = need_type

    def random(self) -> str:
        """Generate a random need ID including hash suffix.."""

        user_name = getpass.getuser()
        doc_uri = self.params.doc.uri
        line_number = self.params.position.line

        need_type = self.need_type
        if not need_type:
            match = re.search(".. ([a-z]+)::", self.lines[line_number - 1])
            # Check for MyST/Markdown style
            if not match and self.params.doc.filename.endswith(".md"):
                match = re.search("```{([a-z]+)}", self.lines[line_number - 1])

            if match:
                need_type = match.group(1)
                if not need_type:
                    return "ID"
            else:
                return "ID"

        need_prefix = need_type.upper()

        hash_part = generate_hash(user_name, doc_uri, need_prefix, line_number)
        need_id = need_prefix + "_" + hash_part
        # re-generate hash if ID is already in use
        while need_id in self.ls.needs_store.needs:
            hash_part = generate_hash(user_name, doc_uri, need_prefix, line_number)
            need_id = need_prefix + "_" + hash_part
        return need_id

    def from_title(self) -> str:
        """Generate a need ID from title."""

        # default id from title if not exists
        id_from_title = "title"
        line_number = self.params.position.line
        match = re.search(r".. ([a-z]+):: ([\w\s]+)", self.lines[line_number - 1])
        # check for MyST/Markdown style
        if not match and self.params.doc.filename.endswith(".md"):
            match = re.search(r"```{([a-z]+)} ([\w\s]+)", self.lines[line_number - 1])

        if match:
            matched_title = match.group(2)
            if matched_title:
                id_from_title = matched_title.rstrip().replace(" ", "_").lower()
        else:
            # check if previous line is empty, which means it's not used in directives
            if not self.lines[line_number - 1]:
                id_from_title = "ID"

        return id_from_title


def generate_need_id(
    ls: NeedlsFeatures, params: CompletionContext, lines: List[str], need_type: Optional[str] = None
) -> str:
    """Generate a need ID."""

    # check custom id from conf.py
    if isinstance(ls.rst, SphinxLanguageServer) and ls.rst.app:
        custom_snippets_id = ls.rst.app.config.needs_ide_snippets_id

    if not custom_snippets_id:
        # default to generate random need ID
        custom_snippets_id = "{{random()}}"

    # handled by jinja
    templ = Environment(loader=BaseLoader()).from_string(custom_snippets_id)

    jinja_util = JinjaHelperFunction(ls, params, lines, need_type)
    data = {"random": jinja_util.random, "from_title": jinja_util.from_title}
    need_id = templ.render(**data)

    return need_id


def found_eval_rst_block(lines: List[str], params: CompletionContext) -> bool:
    # check if current line inside {eval-rst} block
    # ```{eval-rst}
    #
    # ```
    found_eval_rst = False
    # check if used in MyST/Markdown file
    if not params.doc.filename.endswith(".md"):
        return found_eval_rst

    curr_line_no = params.position.line
    if curr_line_no > 0:
        # check if open block {eval-rst} exits
        cnt_block_eval_rst = 0
        cnt = 0
        for line in lines[:curr_line_no]:
            if line.startswith("```"):
                cnt += 1
            if line.startswith("```{eval-rst}"):
                cnt_block_eval_rst += 1

        # check if opened block {eval-rst} exists
        if cnt % 2 != 0 and cnt_block_eval_rst % 2 != 0:
            found_eval_rst = True

    return found_eval_rst


def calc_snippets_completion_item_text_edit(params: CompletionContext, lines: List[str], word: str) -> TextEdit:
    line_number = params.position.line
    substitution = word[word.find("..") :]
    start_char = lines[line_number].find(substitution)

    text_edit = TextEdit(
        range=Range(
            start=Position(line=line_number, character=start_char),
            end=Position(
                line=line_number,
                character=start_char + len(substitution),
            ),
        ),
        new_text="",
    )
    return text_edit


def complete_directive(
    ls: NeedlsFeatures, params: CompletionContext, lines: List[str], word: str
) -> List[CompletionItem]:
    # need_type ~ req, work, act, ...
    items = []

    # calculate completion item text edits
    text_edit = calc_snippets_completion_item_text_edit(params, lines, word)

    # check custom directive snippets from conf.py
    if isinstance(ls.rst, SphinxLanguageServer) and ls.rst.app:
        custom_directive_snippets = ls.rst.app.config.needs_ide_directive_snippets

    for need_type, title in ls.needs_store.declared_types.items():
        # calculate directive snippets completion label
        label = f".. {need_type}::"
        if params.doc.filename.endswith(".md") and not found_eval_rst_block(lines, params):
            # adapte label for MyST/Markdwon
            label = f"md:.. {need_type}::"

        if custom_directive_snippets and need_type in custom_directive_snippets:
            # use custom snippets
            custom_text = custom_directive_snippets[need_type]
            items.append(
                CompletionItem(
                    label=label,
                    detail=title,
                    insert_text=custom_text,
                    insert_text_format=InsertTextFormat.Snippet,
                    kind=CompletionItemKind.Snippet,
                    additional_text_edits=[text_edit],
                )
            )
        elif params.doc.filename.endswith(".md") and not found_eval_rst_block(lines, params):
            # support for MySt/Markdown file
            md_text = (
                "```{" + need_type + "} " + "${1:title}\n"
                ":id: ${2:" + generate_need_id(ls, params, lines, need_type=need_type) + "}\n"
                ":status: open\n\n"
                "${3:content}.\n"
                "```$0"
            )
            md_detail = "Markdown directive snippet"
            items.append(
                CompletionItem(
                    label=label,
                    detail=md_detail,
                    insert_text=md_text,
                    insert_text_format=InsertTextFormat.Snippet,
                    kind=CompletionItemKind.Snippet,
                    additional_text_edits=[text_edit],
                )
            )
        else:
            text = (
                " " + need_type + ":: ${1:title}\n"
                "\t:id: ${2:" + generate_need_id(ls, params, lines, need_type=need_type) + "}\n"
                "\t:status: open\n\n"
                "\t${3:content}.\n$0"
            )
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


def complete_role_or_option(
    ls: NeedlsFeatures, params: CompletionContext, lines: List[str], word: str
) -> List[CompletionItem]:
    # Calculate need role snippet for MySt/Markdown and rst
    if params.doc.filename.endswith(".md"):
        # support MyST/Markdown
        # in MySz/Markdowm file, role looks like, e.g. {need}`content`
        # triggered like noraml rst by :, replaced with markdown style
        line_number = params.position.line
        substitution = word[word.find(":") :]
        start_char = lines[line_number].find(substitution)
        need_role_item = CompletionItem(
            label="md::need:",
            detail="Markdown need role",
            insert_text="{need}`${1:ID}`$0",
            insert_text_format=InsertTextFormat.Snippet,
            kind=CompletionItemKind.Snippet,
            additional_text_edits=[
                TextEdit(
                    range=Range(
                        start=Position(line=line_number, character=start_char),
                        end=Position(
                            line=line_number,
                            character=start_char + len(substitution),
                        ),
                    ),
                    new_text="",
                )
            ],
        )
    else:
        need_role_item = CompletionItem(
            label=":need:",
            detail="need role",
            insert_text="need:`${1:ID}` $0",
            insert_text_format=InsertTextFormat.Snippet,
            kind=CompletionItemKind.Snippet,
        )

    return [
        CompletionItem(
            label=":id:",
            detail="needs option",
            insert_text="id: ${1:" + generate_need_id(ls, params, lines) + "}\n$0",
            insert_text_format=InsertTextFormat.Snippet,
            kind=CompletionItemKind.Snippet,
        ),
        need_role_item,
    ]


def esbonio_setup(rst: SphinxLanguageServer) -> None:
    rst.logger.debug("Starting register Sphinx-Needs language features...")
    needls_features = NeedlsFeatures(rst)
    rst.add_feature(needls_features)
