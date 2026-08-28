from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Final

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.transforms.references import Substitutions
from sphinx.application import Sphinx
from sphinx.environment.collectors.asset import DownloadFileCollector, ImageCollector
from sphinx.transforms import SphinxTransformer
from sphinx.util.logging import getLogger

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsExtractType, SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.directives.needbar import Needbar
from sphinx_needs.directives.needpie import Needpie
from sphinx_needs.directives.needtable import Needtable
from sphinx_needs.directives.needuml import Needuml
from sphinx_needs.directives.utils import (
    no_needs_found_paragraph,
    used_filter_paragraph,
)
from sphinx_needs.filter_common import FilterBase, process_filters
from sphinx_needs.functions.functions import find_and_replace_node_content
from sphinx_needs.layout import build_need_repr
from sphinx_needs.logging import log_warning
from sphinx_needs.need_item import NeedItem, NeedPartItem
from sphinx_needs.utils import add_doc, remove_node_from_tree

LOGGER = getLogger(__name__)


class Needextract(nodes.General, nodes.Element):
    pass


#: View directives that an extract cannot render, and so drops from its copy.
#:
#: A need's content is snapshotted while its directive runs, which is before
#: docutils' ``PropagateTargets`` transform has moved the id of the target
#: preceding each of these nodes onto the node itself -- and each of the four
#: view directives reads that id when it renders, as ``node["ids"][0]``.
#: ``Needextract`` is unrenderable for a different reason: a copy is spliced into
#: the document *after* ``process_needextract`` has walked it, so no listener ever
#: reaches a nested one and it arrives at the writer instead.  Every one of the
#: five used to end the build.
_UNRENDERABLE_IN_EXTRACT: Final = (Needbar, Needextract, Needpie, Needtable, Needuml)


class NeedextractDirective(FilterBase):
    """
    Directive to filter needs and present them as normal needs with given layout and style.
    """

    optional_arguments = 1
    final_argument_whitespace = True

    option_spec = {
        "layout": directives.unchanged_required,
        "style": directives.unchanged_required,
        "show_filters": directives.flag,
    }
    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def run(self) -> Sequence[nodes.Node]:
        env = self.env

        targetid = "needextract-{docname}-{id}".format(
            docname=env.docname, id=env.new_serialno("needextract")
        )
        targetnode = nodes.target("", "", ids=[targetid])

        filter_arg = self.arguments[0] if self.arguments else None

        attributes: NeedsExtractType = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "layout": self.options.get("layout"),
            "style": self.options.get("style"),
            "show_filters": "show_filters" in self.options,
            "filter_arg": filter_arg,
            **self.collect_filter_attributes(),
        }
        node = Needextract("", **attributes)
        self.set_source_info(node)

        add_doc(env, env.docname, "needextract")

        return [targetnode, node]


def process_needextract(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    """
    Replace all needextract nodes with a list of the collected needs.
    """
    env = app.env
    needs_config = NeedsSphinxConfig(app.config)

    # Initialised here, because every node in the loop below can take an early exit
    # before the filter is run, and the value is read once after the loop.
    found_needs: list[NeedItem | NeedPartItem] = []

    node: Needextract
    for node in found_nodes:  # type: ignore[assignment]
        if not needs_config.include_needs:
            remove_node_from_tree(node)
            continue

        current_needextract: NeedsExtractType = node.attributes
        all_needs = SphinxNeedsData(env).get_needs_view()
        content = nodes.container()
        content.attributes["ids"] = [current_needextract["target_id"]]

        # check if filter argument and option filter both exist
        need_filter_arg = current_needextract["filter_arg"]
        if need_filter_arg and current_needextract["filter"]:
            log_warning(
                LOGGER,
                "filter arguments and option filter at the same time are disallowed.",
                "needextract",
                location=node,
            )
            remove_node_from_tree(node)
            continue
        elif need_filter_arg:
            # check if given filter argument is need-id
            if need_filter_arg in all_needs:
                need_filter_arg = f'id == "{need_filter_arg}"'
            elif re.fullmatch(needs_config.id_regex, need_filter_arg):
                # check if given filter argument is need-id, but not exists
                log_warning(
                    LOGGER,
                    f"Requested need {need_filter_arg!r} not found.",
                    "needextract",
                    location=node,
                )
                remove_node_from_tree(node)
                continue
            current_needextract["filter"] = need_filter_arg

        found_needs = process_filters(
            app,
            all_needs,
            current_needextract,
            origin="needextract",
            location=node,
        )

        for need_info in found_needs:
            # filter out need_part from found_needs, in order to generate
            # copies of filtered needs with custom layout and style
            if (
                need_info["is_need"]
                and not need_info["is_part"]
                and isinstance(need_info, NeedItem)
                and (
                    need_extract := _build_needextract(
                        app, node, need_info, current_needextract
                    )
                )
            ):
                content.append(need_extract)

        if len(content) == 0:
            content.append(
                no_needs_found_paragraph(current_needextract.get("filter_warning"))
            )

        if current_needextract["show_filters"]:
            content.append(used_filter_paragraph(current_needextract))

        node.replace_self(content)

    if found_needs:
        # Run docutils/sphinx transformers for the by needextract added nodes.
        # Transformers use the complete document (doctree), so we perform this action once per
        # needextract. No matter if one or multiple needs got copied
        Substitutions(doctree).apply()  # type: ignore[no-untyped-call]


@measure_time("build_needextract")
def _build_needextract(
    app: Sphinx,
    extract_node: Needextract,
    need_data: NeedItem,
    extract_data: NeedsExtractType,
) -> nodes.container | None:
    """Creates a new need representation."""
    env = app.env

    if (need_node := SphinxNeedsData(env).get_need_node(need_data["id"])) is None:
        if need_data["is_external"]:
            message = f"External needs cannot be used as targets by needextract (ID {need_data['id']!r})."
        else:
            message = f"Content for requested need {need_data['id']!r} not found."
        log_warning(LOGGER, message, "needextract", location=extract_node)
        return None

    dummy_need = nodes.container()
    dummy_need.source, dummy_need.line = extract_node.source, extract_node.line

    # Try to implement Sphinx transforms that would have already been done if the need was in the original document.
    # Note, this is very hacky and can not possibly account for all transforms.
    env.temp_data["docname"] = need_data[
        "docname"
    ]  # this is normally set in the read phase
    ImageCollector().process_doc(app, need_node)  # type: ignore[arg-type]
    DownloadFileCollector().process_doc(app, need_node)  # type: ignore[arg-type]
    del env.temp_data["docname"]  # Be sure our env is as it was before

    dummy_need.extend(need_node.children)

    _drop_unrenderable_nodes(dummy_need, need_data, extract_node)

    find_and_replace_node_content(dummy_need, env, need_data)

    # resolve_references() ignores the given docname and takes the docname from the pending_xref node.
    # Therefore, we need to manipulate this first, before we can ask Sphinx to perform the normal
    # reference handling for us.
    _replace_pending_xref_refdoc(dummy_need, extract_data["docname"])
    _apply_post_transforms(app, dummy_need, extract_data["docname"])

    dummy_need.attributes["ids"].append(need_data["id"])
    rendered_node = build_need_repr(
        dummy_need,  # type: ignore[arg-type]
        need_data,
        app,
        layout=extract_data["layout"],
        style=extract_data["style"],
        docname=extract_data["docname"],
    )

    return rendered_node


def _drop_unrenderable_nodes(
    node: nodes.Element, need_data: NeedItem, extract_node: Needextract
) -> None:
    """Remove the copied nodes an extract cannot render, and report each one.

    See :data:`_UNRENDERABLE_IN_EXTRACT` for what cannot be rendered, and why.

    :param node: The copy of the need's content
    :param need_data: The need being extracted
    :param extract_node: The needextract node the copy is being built for
    """
    for child in list(node.findall(lambda n: isinstance(n, _UNRENDERABLE_IN_EXTRACT))):
        log_warning(
            LOGGER,
            f"A {type(child).__name__.lower()!r} directive in the content of need "
            f"{need_data['id']!r} cannot be rendered by needextract, and is omitted.",
            "needextract",
            location=extract_node,
        )
        child.parent.remove(child)


def _apply_post_transforms(app: Sphinx, node: nodes.Element, docname: str) -> None:
    """Run Sphinx's post-transforms over a detached node, resolving its references.

    This is ``BuildEnvironment.apply_post_transforms`` without its closing
    ``doctree-resolved`` emission.  ``env.resolve_references()`` was called here
    instead, and it goes through that emission -- with the detached
    ``nodes.container`` this function is given standing in for a document.  Every
    listener of the event was therefore run a second time, on a node that is not
    a document and holds one need's copied content: Sphinx-Needs' own listeners
    included, and so this function's own caller.  Content holding any node one of
    them handles ended the build rather than rendering: a ``needtable`` in an
    extracted need with ``list index out of range``, a nested ``needextract``
    with ``'container' object has no attribute 'settings'``.

    :param app: Sphinx application
    :param node: The detached node whose references are to be resolved
    :param docname: The document the node is about to be inserted into
    """
    env = app.env
    # what a post-transform reads as "the document being processed"; ``temp_data``
    # is Sphinx's own compatibility alias for it, and is what the collectors above
    # are given too
    previous_docname = env.temp_data.get("docname")
    env.temp_data["docname"] = docname
    try:
        transformer = SphinxTransformer(node)  # type: ignore[arg-type]
        transformer.set_environment(env)
        transformer.add_transforms(app.registry.get_post_transforms())
        transformer.apply_transforms()
    finally:
        if previous_docname is None:
            del env.temp_data["docname"]
        else:
            env.temp_data["docname"] = previous_docname


def _replace_pending_xref_refdoc(node: nodes.Element, new_refdoc: str) -> None:
    """
    Overwrites the refdoc attribute of all pending_xref nodes.
    This is needed, if a doctree with references gets copied used somewhereelse in the documentation.
    What is the normal case when using needextract.
    :param node: doctree
    :param new_refdoc: string, should be an existing docname
    :return: None
    """
    from sphinx.addnodes import pending_xref

    if isinstance(node, pending_xref):
        node.attributes["refdoc"] = new_refdoc
    else:
        for child in node.children:
            _replace_pending_xref_refdoc(child, new_refdoc)  # type: ignore[arg-type]
