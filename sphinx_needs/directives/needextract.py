from __future__ import annotations

import re
from typing import Sequence, cast

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.transforms.references import Substitutions
from sphinx.application import Sphinx
from sphinx.environment.collectors.asset import DownloadFileCollector, ImageCollector

from sphinx_needs.api.exceptions import NeedsInvalidFilter
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsExtractType, SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.directives.utils import (
    no_needs_found_paragraph,
    used_filter_paragraph,
)
from sphinx_needs.filter_common import FilterBase, process_filters
from sphinx_needs.layout import SphinxNeedLayoutException, build_need
from sphinx_needs.utils import add_doc, remove_node_from_tree


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

    for node in found_nodes:
        if not needs_config.include_needs:
            remove_node_from_tree(node)
            continue

        current_needextract: NeedsExtractType = node.attributes
        all_needs = SphinxNeedsData(env).get_or_create_needs()
        content: list[nodes.Element] = []

        # check if filter argument and option filter both exist
        need_filter_arg = current_needextract["filter_arg"]
        if need_filter_arg and current_needextract["filter"]:
            raise NeedsInvalidFilter(
                "Needextract can't have filter arguments and option filter at the same time."
            )
        elif need_filter_arg:
            # check if given filter argument is need-id
            if need_filter_arg in all_needs:
                need_filter_arg = f'id == "{need_filter_arg}"'
            elif re.fullmatch(needs_config.id_regex, need_filter_arg):
                # check if given filter argument is need-id, but not exists
                raise NeedsInvalidFilter(
                    f"Provided id {need_filter_arg} for needextract does not exist."
                )
            current_needextract["filter"] = need_filter_arg

        found_needs = process_filters(
            app,
            all_needs.values(),
            current_needextract,
            origin="needextract",
            location=f"{node.source}:{node.line}",
        )

        for need_info in found_needs:
            # filter out need_part from found_needs, in order to generate
            # copies of filtered needs with custom layout and style
            if need_info["is_need"] and not need_info["is_part"]:
                need_extract = _build_needextract(
                    need_info["id"],
                    app,
                    layout=current_needextract["layout"],
                    style=current_needextract["style"],
                    docname=current_needextract["docname"],
                )

                # Add lineno to node
                need_extract.line = current_needextract["lineno"]

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
    need_id: str,
    app: Sphinx,
    layout: str | None = None,
    style: str | None = None,
    docname: str | None = None,
) -> nodes.container:
    """
    Creates a new need-node for a given layout.

    Need must already exist in internal dictionary.
    This creates a new representation only.
    :param need_id: need id
    :param app: sphinx application
    :param layout: layout to use, overrides layout set by need itself
    :param style: style to use, overrides styles set by need itself
    :param docname: Needed for calculating references
    :return:
    """
    env = app.env
    needs = SphinxNeedsData(env).get_or_create_needs()

    if need_id not in needs.keys():
        raise SphinxNeedLayoutException(f"Given need id {need_id} does not exist.")

    need_data = needs[need_id]

    # Resolve internal references.
    # This is done for original need content automatically.
    # But as we are working on  a copy, we have to trigger this on our own.
    if docname is None:
        # needed to calculate relative references
        # TODO ideally we should not cast here:
        # the docname can still be None, if the need is external, although practically these are not rendered
        docname = cast(str, needs[need_id]["docname"])

    node_container = nodes.container()
    # node_container += needs[need_id]["need_node"].children

    node_inner = SphinxNeedsData(env).get_need_node(need_id)
    assert node_inner is not None, f"Need {need_id} has no content node."

    # Rerun some important Sphinx collectors for need-content coming from "needsexternal".
    # This is needed, as Sphinx needs to know images and download paths.
    # Normally this gets done much earlier in the process, so that for the copied need-content this
    # handling was and will not be done by Sphinx itself anymore.

    # Overwrite the docname, which must be the original one from the reused need, as all used paths are relative
    # to the original location, not to the current document.
    env.temp_data["docname"] = need_data[
        "docname"
    ]  # Dirty, as in this phase normally no docname is set anymore in env
    ImageCollector().process_doc(app, node_inner)  # type: ignore[arg-type]
    DownloadFileCollector().process_doc(app, node_inner)  # type: ignore[arg-type]

    del env.temp_data["docname"]  # Be sure our env is as it was before

    node_container.append(node_inner)

    # resolve_references() ignores the given docname and takes the docname from the pending_xref node.
    # Therefore, we need to manipulate this first, before we can ask Sphinx to perform the normal
    # reference handling for us.
    _replace_pending_xref_refdoc(node_container, docname)
    env.resolve_references(node_container, docname, env.app.builder)  # type: ignore[arg-type]

    node_container.attributes["ids"].append(need_id)

    needs_config = NeedsSphinxConfig(app.config)
    layout = layout or need_data["layout"] or needs_config.default_layout
    style = style or need_data["style"] or needs_config.default_style

    build_need(layout, node_container, app, style, docname)

    # set the layout and style for the new need
    node_container[0].attributes = node_container.parent.children[0].attributes  # type: ignore
    node_container[0].children[0].attributes = (  # type: ignore
        node_container.parent.children[0].children[0].attributes  # type: ignore
    )

    node_container.attributes["ids"] = []

    return node_container


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
