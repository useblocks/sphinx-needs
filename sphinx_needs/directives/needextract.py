from __future__ import annotations

import re
from collections.abc import Sequence

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.transforms.references import Substitutions
from sphinx.application import Sphinx
from sphinx.environment.collectors.asset import DownloadFileCollector, ImageCollector
from sphinx.util.logging import getLogger

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsExtractType, NeedsInfoType, SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.directives.utils import (
    no_needs_found_paragraph,
    used_filter_paragraph,
)
from sphinx_needs.filter_common import FilterBase, process_filters
from sphinx_needs.functions.functions import find_and_replace_node_content
from sphinx_needs.layout import build_need_repr
from sphinx_needs.logging import log_warning
from sphinx_needs.utils import add_doc, remove_node_from_tree

LOGGER = getLogger(__name__)


class Needextract(nodes.General, nodes.Element):
    pass


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
    need_data: NeedsInfoType,
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

    find_and_replace_node_content(dummy_need, env, need_data)

    # resolve_references() ignores the given docname and takes the docname from the pending_xref node.
    # Therefore, we need to manipulate this first, before we can ask Sphinx to perform the normal
    # reference handling for us.
    _replace_pending_xref_refdoc(dummy_need, extract_data["docname"])
    env.resolve_references(dummy_need, extract_data["docname"], app.builder)  # type: ignore[arg-type]

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
