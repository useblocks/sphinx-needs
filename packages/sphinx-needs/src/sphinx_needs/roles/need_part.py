"""
NeedPart module
---------------
Provides the ability to mark specific parts of a need with an own id.

"""

from __future__ import annotations

import hashlib
import re
from typing import Final

from docutils import nodes
from sphinx import addnodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.docutils import SphinxRole
from sphinx.util.nodes import make_refnode

from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedPartData
from sphinx_needs.nodes import Need

LOGGER = get_logger(__name__)


class NeedPart(nodes.Inline, nodes.Element):
    @property
    def title(self) -> str:
        """Return the title of the part."""
        return self.attributes["title"]

    @property
    def part_id(self) -> str:
        """Return the ID of the part."""
        return self.attributes["part_id"]

    @property
    def need_id(self) -> str | None:
        """Return the ID of the need this part belongs to."""
        return self.attributes["need_id"]

    @need_id.setter
    def need_id(self, value: str) -> None:
        """Set the ID of the need this part belongs to."""
        self.attributes["need_id"] = value


_PART_PATTERN = re.compile(r"\(([\w-]+)\)(.*)", re.DOTALL)

#: The white space an ``(id)`` part's text loses at its ends: the 25 code points of
#: Unicode's ``White_Space`` property (``design/parts-contract.md`` section 1). Not
#: ``str.strip()``'s default set, which also holds U+001C to U+001F.
_PART_TEXT_WHITE_SPACE: Final = (
    "\t\n\x0b\x0c\r \x85\xa0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)


class NeedPartRole(SphinxRole):
    """
    Role for need parts, which are sub-needs of a need.
    It is used to mark parts of a need with an own id.
    """

    def run(self) -> tuple[list[nodes.Node], list[nodes.system_message]]:
        # note self.text is the content of the role, with backslash escapes removed
        # TODO perhaps in a future change we should allow escaping parentheses in the part id?
        result = _PART_PATTERN.match(self.text)
        if result:
            id_ = result.group(1)
            title = result.group(2).strip(_PART_TEXT_WHITE_SPACE)
        else:
            id_ = hashlib.sha1(self.text.encode("UTF-8")).hexdigest().upper()[:3]
            title = self.text
        part = NeedPart(title=title, part_id=id_, need_id=None)
        self.set_source_info(part)
        return [part], []


def process_need_part(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    # note this is called after needs have been processed and parts collected.
    for node in found_nodes:
        assert isinstance(node, NeedPart), "Expected NeedPart node"
        if node.need_id is None:
            log_warning(
                LOGGER,
                "Need part not associated with a need.",
                "part",
                node,
            )


#: The builder formats whose writer anchors a ``target`` node and no ``inline``'s ids:
#: LaTeX writes no ``\label`` for an inline, and texinfo no ``@anchor`` (it writes one
#: for an address it was given no anchor for at the end of the output file). A part in a
#: caption gets no target in them, because the LaTeX writer writes one there as
#: ``\phantomsection\label``, which stops ``pdflatex``.
_FORMATS_ANCHORING_TARGETS: Final = frozenset({"latex", "texinfo"})


def unwrap_need_parts(app: Sphinx, doctree: nodes.document, docname: str) -> None:
    """Replace every ``NeedPart`` in a resolved doctree by what a reader sees of it.

    The node only marks where a part is while needs are collected and resolved; what a
    reader sees of a part is its ``inline`` (the part's text, with its id and its link).
    A role that made no part -- one repeating a part id of its need, or one outside
    every need -- is its text, with no id. Removing the wrapper before a writer runs
    means a writer, of Sphinx or of another extension, need not know the node for a
    part in a page's body.

    The html family keeps the part's id on its ``inline``, as it was written there; for
    LaTeX and texinfo the id moves to a ``target`` at the start of the inline, which is
    what those writers anchor in place. Those builders resolve every page of an output
    file in one tree, and name a label or an anchor by the page (the source document) a
    node is on, so an address is anchored once per page, at its first occurrence there,
    as a browser takes the first of an id a page holds twice: a later one on the same
    page, such as a ``needextract`` copy of the need there, keeps its text and its id
    link and carries no target and no id. A copy on another page is anchored on that
    page, under its name. A part in a caption (of a figure, a code block, a
    ``literalinclude``) is given no target and keeps its ids, as before, because the
    LaTeX writer writes a target there as ``\\phantomsection\\label``, which stops
    ``pdflatex`` inside the caption's argument: the anchor at its text is given up,
    not the build.

    Connected late to ``doctree-resolved``, after the handlers that still read the node,
    and for every document: a part on a page holding no need is in the tree too. A role
    in a section title is reached here in the page's heading, but not in the copies of
    the title Sphinx made for its tables of contents when the page was read: the html
    writer still meets the node there, which its ``html`` visitor is kept for. The
    heading's own node is left without text on purpose (``_in_section_title``), so that
    the heading reads as those entries do.
    """
    anchor_with_target = app.builder.format in _FORMATS_ANCHORING_TARGETS
    anchored: set[tuple[str, str]] = set()
    for node, source in _parts_by_source_document(doctree, docname):
        if node.children:
            shown = list(node.children)
            if anchor_with_target and not _in_caption(node):
                for child in shown:
                    if isinstance(child, nodes.Element) and child["ids"]:
                        ids = [i for i in child["ids"] if (source, i) not in anchored]
                        if ids:
                            child.insert(0, nodes.target(ids=ids))
                            anchored.update((source, i) for i in ids)
                        child["ids"] = []
        elif _in_section_title(node):
            shown = []
        else:
            shown = [nodes.Text(node.title)]
        node.replace_self(shown)


def _parts_by_source_document(
    doctree: nodes.document, docname: str
) -> list[tuple[NeedPart, str]]:
    """Every ``NeedPart`` of a resolved tree, in document order, with the name of the
    source document it is from: the name the LaTeX and texinfo writers put before an id
    in its label or anchor.

    A tree those builders assemble from several documents marks each included one with
    a ``start_of_file`` (and an appendix as a ``document``) holding its name, and the
    writers take the nearest one around a node, but for what LaTeX moves after the
    appendices (the bibliography), which it names by the last appendix: its writer does
    not leave an appendix's name at the appendix's end. The tree is walked from its
    root, as the writers walk it: the assembly gives a ``start_of_file`` the children
    of the included document without making it their ``parent``.
    """
    found: list[tuple[NeedPart, str]] = []
    stack: list[tuple[nodes.Node, str]] = [(doctree, docname)]
    while stack:
        node, source = stack.pop()
        if isinstance(node, NeedPart):
            found.append((node, source))
            continue
        if isinstance(node, addnodes.start_of_file) or (
            isinstance(node, nodes.document) and node is not doctree
        ):
            source = node.get("docname", "")
        if isinstance(node, nodes.Element):
            stack.extend((child, source) for child in reversed(node.children))
    return found


def _in_caption(node: nodes.Element) -> bool:
    """Whether the node is in a caption: of a figure, a code block, a
    ``literalinclude``."""
    parent = node.parent
    while parent is not None:
        if isinstance(parent, nodes.caption):
            return True
        parent = parent.parent
    return False


def _in_section_title(node: nodes.Element) -> bool:
    """Whether the node is in the title of a section."""
    parent = node.parent
    while parent is not None:
        if isinstance(parent, nodes.title):
            return isinstance(parent.parent, nodes.section)
        parent = parent.parent
    return False


def update_need_with_parts(
    env: BuildEnvironment, need: NeedItem, part_nodes: list[NeedPart]
) -> None:
    app = env.app
    parts = {}
    for part_node in part_nodes:
        part_id = part_node.part_id

        if part_id in parts:
            log_warning(
                LOGGER,
                f"Need '{need['id']}' already has a part '{part_id}': the first role "
                "of an id marks the part, this one is shown as plain text.",
                "duplicate_part_id",
                part_node,
            )
            # the first part of an id is kept and this one makes no part: it holds no
            # node, and is shown as its text alone (`unwrap_need_parts`). It is in the
            # need: recorded so, it is not also reported as outside every need
            part_node.need_id = need["id"]
            continue

        parts[part_id] = NeedPartData(
            id=part_id,
            content=part_node.title,
            backlinks={name: [] for name in need.iter_links_keys()},
        )

        part_node.need_id = need["id"]
        part_id_ref = "{}.{}".format(need["id"], part_id)
        part_node["reftarget"] = part_id_ref

        node_need_part_line = nodes.inline(ids=[part_id_ref], classes=["need-part"])
        node_need_part_line.append(nodes.Text(part_node.title))

        if docname := need["docname"]:
            part_ref_node = make_refnode(
                app.builder, docname, docname, part_id_ref, nodes.Text(f" {part_id}")
            )
            part_ref_node["classes"] += ["needs-id"]
            node_need_part_line.append(part_ref_node)

        part_node.children = []
        part_node.append(node_need_part_line)

    need.set_parts(list(parts.values()))


def find_parts(node: nodes.Node) -> list[NeedPart]:
    found_nodes = []
    for child in node.children:
        if isinstance(child, NeedPart):
            found_nodes.append(child)
        elif not isinstance(child, Need):  # parts in nested needs should be ignored
            found_nodes += find_parts(child)
    return found_nodes
