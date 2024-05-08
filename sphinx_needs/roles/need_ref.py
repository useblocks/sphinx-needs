from __future__ import annotations

import contextlib
from collections.abc import Iterable

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util.nodes import make_refnode

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType, SphinxNeedsData
from sphinx_needs.errors import NoUri
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import check_and_calc_base_url_rel_path, split_need_id

log = get_logger(__name__)


class NeedRef(nodes.Inline, nodes.Element):
    pass


def transform_need_to_dict(need: NeedsInfoType) -> dict[str, str]:
    """
    The function will transform a need in a dictionary of strings. Used to
    be given e.g. to a python format string.

    Parameters
    ----------
    need : need
        A need object.

    Returns
    -------
    dict : dictionary of strings
        Can be easily used for python format strings, or other use cases
    """
    dict_need = {}

    for element, value in need.items():
        if isinstance(value, str):
            # As string are iterable, we have to handle strings first.
            dict_need[element] = value
        elif isinstance(value, dict):
            dict_need[element] = ";".join([str(i) for i in value.items()])
        elif isinstance(value, (Iterable, list, tuple)):
            dict_need[element] = ";".join([str(i) for i in value])
        else:
            dict_need[element] = str(value)

    return dict_need


def process_need_ref(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    builder = app.builder
    env = app.env
    needs_config = NeedsSphinxConfig(env.config)
    all_needs = SphinxNeedsData(env).get_or_create_needs()
    # for node_need_ref in doctree.findall(NeedRef):
    for node_need_ref in found_nodes:
        # Let's create a dummy node, for the case we will not be able to create a real reference
        new_node_ref = make_refnode(
            builder,
            fromdocname,
            fromdocname,
            "Unknown need",
            node_need_ref[0].deepcopy(),
            node_need_ref["reftarget"] + "?",
        )

        # It is possible to change the prefix / postfix easily here.
        prefix = "[["
        postfix = "]]"

        need_id_full = node_need_ref["reftarget"]
        need_id_main, need_id_part = split_need_id(need_id_full)

        if need_id_main in all_needs:
            target_need = all_needs[need_id_main]

            dict_need = transform_need_to_dict(
                target_need
            )  # Transform a dict in a dict of {str, str}

            # We set the id to the complete id maintained in node_need_ref["reftarget"]
            dict_need["id"] = need_id_full

            if need_id_part:
                # If part_id, we have to fetch the title from the content.
                dict_need["title"] = target_need["parts"][need_id_part]["content"]

            # Shorten title, if necessary
            max_length = needs_config.role_need_max_title_length
            if 3 < max_length < len(dict_need["title"]):
                title = dict_need["title"]
                title = f"{title[: max_length - 3]}..."
                dict_need["title"] = title

            ref_name: None | str | nodes.Text = node_need_ref.children[0].children[0]  # type: ignore[assignment]
            # Only use ref_name, if it differs from ref_id
            if str(need_id_full) == str(ref_name):
                ref_name = None

            if ref_name and prefix in ref_name and postfix in ref_name:
                # if ref_name is set and has prefix to process, we will do so.
                ref_name = ref_name.replace(prefix, "{").replace(postfix, "}")
                try:
                    link_text = ref_name.format(**dict_need)
                except KeyError as e:
                    log.warning(
                        f"option placeholder {e} for need {node_need_ref['reftarget']} not found [needs]",
                        type="needs",
                        location=node_need_ref,
                    )
            else:
                if ref_name:
                    # If ref_name differs from the need id, we treat the "ref_name content" as title.
                    dict_need["title"] = ref_name
                try:
                    link_text = needs_config.role_need_template.format(**dict_need)
                except KeyError as e:
                    link_text = f'"the config parameter needs_role_need_template uses not supported placeholders: {e} "'
                    log.warning(link_text + " [needs]", type="needs")

            node_need_ref[0].children[0] = nodes.Text(link_text)  # type: ignore[index]

            with contextlib.suppress(NoUri):
                if not target_need.get("is_external", False) and (
                    _docname := target_need["docname"]
                ):
                    new_node_ref = make_refnode(
                        builder,
                        fromdocname,
                        _docname,
                        node_need_ref["reftarget"],
                        node_need_ref[0].deepcopy(),
                        node_need_ref["reftarget"],
                    )
                else:
                    assert (
                        target_need["external_url"] is not None
                    ), "external_url must be set for external needs"
                    new_node_ref = nodes.reference(target_need["id"], target_need["id"])
                    new_node_ref["refuri"] = check_and_calc_base_url_rel_path(
                        target_need["external_url"], fromdocname
                    )
                    new_node_ref["classes"].append(target_need["external_css"])

        else:
            log.warning(
                f"linked need {node_need_ref['reftarget']} not found [needs.link_ref]",
                type="needs",
                subtype="link_ref",
                location=node_need_ref,
            )

        node_need_ref.replace_self(new_node_ref)
