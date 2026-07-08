from __future__ import annotations

import contextlib
import re
from collections.abc import Iterable
from typing import Any

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util.nodes import make_refnode

from sphinx_needs._jinja import compile_template
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.errors import NoUri
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedLink
from sphinx_needs.utils import check_and_calc_base_url_rel_path

log = get_logger(__name__)

# Markers that unambiguously identify a Jinja template.
_JINJA_MARKERS = ("{{", "{%", "{#")
# A ``str.format``-style field reference, e.g. ``{id}`` or ``{title:*^20s}``.
_LEGACY_FORMAT_FIELD = re.compile(r"\{[^{}]*\}")


def _is_legacy_format_template(template: str) -> bool:
    """Heuristically detect a legacy ``str.format``-style template.

    Before Jinja support, ``needs_role_need_template`` was rendered with
    ``str.format`` (``{field}`` placeholders).  Such a template renders as
    literal text under Jinja (``{id}`` stays ``{id}``), which would silently
    change existing users' output.  To keep them working, we detect the old
    syntax and render it the old way, emitting a deprecation warning.

    A template is treated as legacy when it contains a ``{field}`` reference
    but none of the Jinja markers ``{{``, ``{%`` or ``{#``.
    """
    if any(marker in template for marker in _JINJA_MARKERS):
        return False
    return bool(_LEGACY_FORMAT_FIELD.search(template))


def _build_template_context(
    dict_need: dict[str, str], *, is_part: bool
) -> dict[str, Any]:
    """Build the Jinja context for rendering a need role template.

    Exposes each need field both as a top-level variable (e.g. ``{{ title }}``)
    and via a ``need`` object (e.g. ``{{ need.title }}``), plus the ``is_need``
    / ``is_part`` boolean flags for conditionals.
    """
    flags: dict[str, Any] = {"is_need": not is_part, "is_part": is_part}
    return {"need": {**dict_need, **flags}, **dict_need, **flags}


class NeedRef(nodes.Inline, nodes.Element):
    pass


def transform_need_to_dict(need: NeedItem) -> dict[str, str]:
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
        dict_need[element] = value_to_string(value)

    return dict_need


def value_to_string(value: Any) -> str:
    if isinstance(value, str):
        # As string are iterable, we have to handle strings first.
        return value
    elif isinstance(value, dict):
        return ";".join([str(i) for i in value.items()])
    elif isinstance(value, Iterable | list | tuple):
        return ";".join([str(i) for i in value])

    return str(value)


def process_need_ref(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    builder = app.builder
    env = app.env
    needs_config = NeedsSphinxConfig(env.config)
    all_needs = SphinxNeedsData(env).get_needs_view()

    # Compile the configured role template once (rendered per reference below).
    # Templates using the legacy ``str.format`` syntax are still rendered with
    # ``str.format`` (with a deprecation warning) so existing configs keep
    # working; everything else is rendered with Jinja.
    role_template_str = needs_config.role_need_template
    role_is_legacy = _is_legacy_format_template(role_template_str)
    role_template = None
    if role_is_legacy:
        log_warning(
            log,
            "needs_role_need_template uses the deprecated str.format syntax; "
            "migrate '{field}' placeholders to Jinja '{{ field }}' "
            "(this will be rendered with str.format for now, but support will "
            "be removed in a future release)",
            "deprecated",
            location=None,
        )
    else:
        try:
            role_template = compile_template(role_template_str, autoescape=False)
        except Exception as exc:
            log_warning(
                log,
                f"needs_role_need_template could not be compiled as a Jinja template: {exc}",
                "link_text",
                location=None,
            )

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

        need_link: NeedLink = node_need_ref["need_link"]
        need_id_full = node_need_ref["reftarget"]
        need_id_main = need_link.id
        need_id_part = need_link.part
        need_id_complete = need_link.to_link_string()

        if need_id_main not in all_needs:
            log_warning(
                log,
                f"linked need {node_need_ref['reftarget']} not found",
                "link_ref",
                location=node_need_ref,
            )
        elif (
            need_id_part is not None
            and need_id_part not in all_needs[need_id_main]["parts"]
        ):
            log_warning(
                log,
                f"linked need part {node_need_ref['reftarget']} not found",
                "link_ref",
                location=node_need_ref,
            )
        else:
            target_need = all_needs[need_id_main]

            dict_need = transform_need_to_dict(
                target_need
            )  # Transform a dict in a dict of {str, str}

            is_part = need_id_part is not None

            dict_need["id_part"] = need_id_part or ""
            if need_id_part:
                dict_need["id_complete"] = need_id_complete

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

            link_text = ""
            if ref_name and prefix in ref_name and postfix in ref_name:
                # An explicit inline template was given via the role text.
                # It uses ``[[``/``]]`` (instead of Jinja's ``{{``/``}}``) as
                # variable delimiters, so we compile it with those delimiters
                # rather than rewriting the string.
                try:
                    inline_template = compile_template(
                        str(ref_name),
                        autoescape=False,
                        variable_start_string=prefix,
                        variable_end_string=postfix,
                    )
                    link_text = inline_template.render(
                        _build_template_context(dict_need, is_part=is_part)
                    )
                except Exception as exc:
                    log_warning(
                        log,
                        f"inline need role template for need {node_need_ref['reftarget']} "
                        f"is invalid: {exc}",
                        "link_text",
                        location=node_need_ref,
                    )
            else:
                if ref_name:
                    # If ref_name differs from the need id, we treat the "ref_name content" as title.
                    dict_need["title"] = ref_name
                if role_is_legacy:
                    # Backwards-compatible str.format rendering (deprecated,
                    # warned about once above).
                    try:
                        link_text = role_template_str.format(**dict_need)
                    except (KeyError, IndexError, ValueError) as exc:
                        log_warning(
                            log,
                            "the config parameter needs_role_need_template uses "
                            f"unsupported str.format placeholders: {exc}",
                            "link_text",
                            location=node_need_ref,
                        )
                        link_text = f"{dict_need['title']} ({dict_need['id']})"
                elif role_template is None:
                    # Compilation failed above; fall back to the default text.
                    link_text = f"{dict_need['title']} ({dict_need['id']})"
                else:
                    try:
                        # Build the context after any title override via
                        # ref_name so templates see the latest values.
                        link_text = role_template.render(
                            _build_template_context(dict_need, is_part=is_part)
                        )
                    except Exception as exc:
                        log_warning(
                            log,
                            "the config parameter needs_role_need_template uses "
                            f"invalid Jinja syntax or variables: {exc}",
                            "link_text",
                            location=node_need_ref,
                        )
                        link_text = f"{dict_need['title']} ({dict_need['id']})"

            node_need_ref[0].children[0] = nodes.Text(link_text)  # type: ignore[index]

            with contextlib.suppress(NoUri):
                if not target_need["is_external"] and (
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
                    assert target_need["external_url"] is not None, (
                        "external_url must be set for external needs"
                    )
                    new_node_ref = nodes.reference(target_need["id"], target_need["id"])
                    new_node_ref["refuri"] = check_and_calc_base_url_rel_path(
                        target_need["external_url"], fromdocname
                    )
                    new_node_ref["classes"].append(target_need["external_css"])

        node_need_ref.replace_self(new_node_ref)
