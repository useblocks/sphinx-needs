"""A shorthand format for specifying needs, in a field list."""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from typing import Final, TypedDict

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.environment import BuildEnvironment
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api.exceptions import InvalidNeedException
from sphinx_needs.api.need import add_arch, generate_need
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.defaults import string_to_boolean
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.nodes import Need
from sphinx_needs.roles.need_part import find_parts, update_need_with_parts
from sphinx_needs.utils import add_doc

LOGGER = get_logger(__name__)


class ListNeedsDirective(SphinxDirective):
    """A shorthand format for specifying needs, in a field list."""

    directive_name = "list-needs"

    required_arguments = 0
    optional_arguments = 0
    has_content = True
    option_spec = {
        "defaults": directives.unchanged_required,
        "maxdepth": directives.nonnegative_int,
        "flatten": directives.flag,
        "links-up": directives.unchanged_required,
        "links-down": directives.unchanged_required,
    }

    def run(self) -> Sequence[nodes.Node]:
        content = self.parse_content_to_nodes()

        if len(content) != 1 or not isinstance(content[0], nodes.field_list):
            log_warning(
                LOGGER,
                "list-needs directive must contain exactly one field list.",
                "list-needs",
                location=self.get_location(),
            )
            return []

        needs_config = NeedsSphinxConfig(self.env.config)
        needs_data = SphinxNeedsData(self.env)
        docname = self.env.docname
        doctype = os.path.splitext(self.env.doc2path(docname))[1]

        defaults: dict[str, str] = {}
        if "defaults" in self.options:
            try:
                defaults = _field_list_to_dict(self.options["defaults"])
            except _KnownError as e:
                log_warning(
                    LOGGER,
                    f"Error parsing defaults: {e}",
                    "list-needs",
                    location=self.get_location(),
                )
                return []

        links_up = [
            li.strip()
            for li in self.options.get("links-up", "").split(",")
            if li.strip()
        ]
        links_up_diff = set(links_up) - {x["option"] for x in needs_config.extra_links}
        if links_up_diff:
            log_warning(
                LOGGER,
                f"Unknown links-up link type(s): {links_up_diff}",
                "list-needs",
                location=self.get_location(),
            )
            links_up = []

        links_down = [
            li.strip()
            for li in self.options.get("links-down", "").split(",")
            if li.strip()
        ]
        links_down_diff = set(links_down) - {
            x["option"] for x in needs_config.extra_links
        }
        if links_down_diff:
            log_warning(
                LOGGER,
                f"Unknown links-down link type(s): {links_down_diff}",
                "list-needs",
                location=self.get_location(),
            )
            links_down = []

        return_nodes, _ = _parse_field_list(
            content[0],
            defaults,
            needs_config,
            needs_data,
            self.env,
            docname,
            doctype,
            0,
            self.options.get("maxdepth"),
            "flatten" in self.options,
            links_up,
            links_down,
            None,
        )

        add_doc(self.env, self.env.docname)

        return return_nodes


def _parse_field_list(
    field_list: nodes.field_list,
    defaults: dict[str, str],
    needs_config: NeedsSphinxConfig,
    needs_data: SphinxNeedsData,
    env: BuildEnvironment,
    docname: str,
    doctype: str,
    current_depth: int,
    max_depth: int | None,
    flatten: bool,
    links_up: list[str],
    links_down: list[str],
    parent_id: str | None,
) -> tuple[list[nodes.Node], list[str]]:
    return_nodes: list[nodes.Node] = []
    node_ids: list[str] = []
    for field_item in field_list:
        if (
            not isinstance(field_item, nodes.field)
            or len(field_item) != 2
            or not isinstance(field_item[0], nodes.field_name)
            or not isinstance(field_item[1], nodes.field_body)
        ):
            log_warning(
                LOGGER,
                "field list does not contain the expected structure.",
                "list-needs",
                location=field_item,
            )
            continue

        field_name: str = field_item[0].astext()
        field_body: nodes.field_body = field_item[1]

        try:
            kwargs = {**defaults, **_field_name_to_kwargs(field_name)}
        except _KnownError as e:
            log_warning(
                LOGGER,
                f"Error parsing field name {field_name!r} :{e}",
                "list-needs",
                location=field_item,
            )
            continue

        try:
            need_type, need_params, unknown = _kwargs_to_need_params(
                kwargs, needs_config
            )
        except Exception as e:
            log_warning(
                LOGGER,
                f"Error parsing field name {field_name!r} :{e}",
                "list-needs",
                location=field_item,
            )
            continue

        if unknown:
            log_warning(
                LOGGER,
                f"Unknown need parameter(s): {unknown}",
                "list-needs",
                location=field_item,
            )

        if "title" not in need_params:
            if field_body.children and isinstance(
                field_body.children[0], nodes.paragraph
            ):
                title = field_body.children[0].rawsource
                need_content = field_body.children[1:]
            else:
                log_warning(
                    LOGGER,
                    "Title not given and first content block is not a paragraph.",
                    "list-needs",
                    location=field_item,
                )
                continue
        else:
            title = need_params.pop("title")
            need_content = field_body.children

        try:
            needs_info = generate_need(  # type: ignore[misc]
                needs_config,
                need_type,
                title,
                **need_params,  # type: ignore[arg-type]
                docname=docname,
                doctype=doctype,
                lineno=field_item.line,
                lineno_content=field_item.line,  # note this should be the field_body line, but appears to always be None
                content=field_body.rawsource,
            )
        except InvalidNeedException as err:
            log_warning(
                LOGGER,
                f"Need could not be created: {err.message}",
                "list-needs",
                location=field_item,
            )
            continue

        if needs_data.has_need(needs_info["id"]):
            if "id" not in need_params:
                # this is a generated ID
                message = f"Unique ID could not be generated for need with title {needs_info['title']!r}."
            else:
                message = f"A need with ID {needs_info['id']!r} already exists."
            log_warning(
                LOGGER,
                message,
                "list-needs",
                location=field_item,
            )
            continue

        if parent_id is not None:
            try:
                link_type = links_up[current_depth - 1]
                needs_info.setdefault(link_type, []).append(parent_id)  # type: ignore[misc]
            except IndexError:
                pass

        needs_data.add_need(needs_info)
        node_ids.append(needs_info["id"])

        # create need node
        node_need = Need(
            "",
            classes=[
                "need",
                f"need-{needs_info['type'].lower()}",
                *([needs_info["style"]] if needs_info["style"] else []),
            ],
            ids=[needs_info["id"]],
            refid=needs_info["id"],
        )
        node_need.source, node_need.line = field_item.source, field_item.line

        post_nodes: list[nodes.Node] = []
        if max_depth is None or current_depth < (max_depth - 1):
            for sub_node in need_content:
                if isinstance(sub_node, nodes.field_list):
                    _nodes, _child_ids = _parse_field_list(
                        sub_node,
                        defaults,
                        needs_config,
                        needs_data,
                        env,
                        docname,
                        doctype,
                        current_depth + 1,
                        max_depth,
                        flatten,
                        links_up,
                        links_down,
                        needs_info["id"],
                    )
                    if flatten:
                        post_nodes.extend(_nodes)
                    else:
                        node_need.extend(_nodes)
                    if _child_ids:
                        try:
                            link_type = links_down[current_depth]
                            needs_info.setdefault(link_type, []).extend(_child_ids)  # type: ignore[misc]
                        except IndexError:
                            pass
                else:
                    node_need.append(sub_node)
        else:
            node_need.extend(need_content)

        if needs_info["hide"]:
            node_need["hidden"] = True
            return_nodes.extend((node_need, *post_nodes))
            continue

        return_nodes.append(
            nodes.target(
                "", "", ids=[needs_info["id"]], refid=needs_info["id"], anonymous=""
            )
        )
        return_nodes.extend((node_need, *post_nodes))

        add_arch(needs_info, node_need, needs_data)

        need_parts = find_parts(node_need)
        update_need_with_parts(env, needs_info, need_parts)

        needs_data.set_need_node(needs_info["id"], node_need)

    return return_nodes, node_ids


class _KnownError(Exception): ...


def _field_name_to_kwargs(field_name: str) -> dict[str, str]:
    """Convert a field name to keyword arguments."""
    try:
        need_type, *rest = field_name.split(maxsplit=1)
    except ValueError:
        raise _KnownError("no need type specified")

    if not rest:
        return {"need_type": need_type}

    rest_str = rest[0]
    kwargs = {}
    while rest_str:
        # search for the first non-space character
        char, rest_str = rest_str[0], rest_str[1:]
        if char in (" ", "\n", "\r", "\t"):
            continue

        # the name is all chars upto a `=` or space character
        name = char
        has_value = False
        while rest_str:
            char, rest_str = rest_str[0], rest_str[1:]
            if char == "=":
                has_value = True
                break
            elif char == " ":
                break
            name += char

        if not has_value or not rest_str or rest_str[0] == " ":
            kwargs[name] = ""
            continue

        # the value can be enclosed by `"` or `'`, or is terminated by a space
        quote_char, rest_str = rest_str[0], rest_str[1:]
        if quote_char in ('"', "'"):
            terminal_char = quote_char
            value = ""
        else:
            value = quote_char
            terminal_char = " "
        while rest_str:
            char, rest_str = rest_str[0], rest_str[1:]
            if char == terminal_char:
                break
            value += char
        else:
            if terminal_char in ('"', "'"):
                raise _KnownError("no closing quote found for value")
        kwargs[name] = value

    return {"need_type": need_type, **kwargs}


class _NeedKwargs(TypedDict, total=False):
    id: str
    title: str
    status: str
    tags: str
    collapse: bool | None
    delete: bool | None
    hide: bool
    layout: str
    style: str
    constraints: str


def _kwargs_to_need_params(
    parsed: dict[str, str], config: NeedsSphinxConfig
) -> tuple[str, _NeedKwargs, list[str]]:
    """Convert keyword arguments to parameters that can be passed tp generate_need func."""
    if "need_type" not in parsed:
        raise _KnownError("no need type specified")
    need_type = parsed.pop("need_type")
    kwargs: _NeedKwargs = {}

    # common options
    if id_ := parsed.pop("id", None):
        kwargs["id"] = id_
    if "title" in parsed:
        kwargs["title"] = parsed.pop("title")
    if status := parsed.pop("status", None):
        kwargs["status"] = status
    if tags := parsed.pop("tags", None):
        kwargs["tags"] = tags
    if "collapse" in parsed:
        kwargs["collapse"] = string_to_boolean(parsed.pop("collapse"))
    if "delete" in parsed:
        kwargs["delete"] = string_to_boolean(parsed.pop("delete"))
    if "hide" in parsed:
        parsed.pop("hide")
        kwargs["hide"] = True
    if layout := parsed.pop("layout", None):
        kwargs["layout"] = layout
    if style := parsed.pop("style", None):
        kwargs["style"] = style
    if constraints := parsed.pop("constraints", None):
        kwargs["constraints"] = constraints

    # extra options
    for extra_name in config.extra_options:
        if extra_name in parsed:
            kwargs[extra_name] = parsed.pop(extra_name)  # type: ignore[literal-required]

    # link options
    for link in config.extra_links:
        link_name = link["option"]
        if link_name in parsed:
            kwargs[link_name] = parsed.pop(link_name)  # type: ignore[literal-required]

    return need_type, kwargs, list(parsed)


_RE_FIELD_MARKER: Final[str] = r"^:((?![: ])([^:\\]|\\.|:(?!([ `]|$)))*(?<! )):( +|$)"


def _field_list_to_dict(content: str) -> dict[str, str]:
    """Parse a field list into a dict, error if invalid."""
    content_lines = content.splitlines()
    defaults = {}
    while content_lines:
        if not content_lines[0].strip():
            content_lines.pop(0)
            continue
        if match := re.match(_RE_FIELD_MARKER, content_lines[0]):
            name = content_lines[0][match.start(1) : match.end(1)]
            body = [content_lines.pop(0)[match.end(0) :]]
            while content_lines and (
                not content_lines[0] or content_lines[0].startswith(" ")
            ):
                body.append(content_lines.pop(0))
            smallest_indent = min(
                [len(line) - len(line.lstrip()) for line in body if line.strip()] or [0]
            )
            defaults[name] = "\n".join(line[smallest_indent:] for line in body)
        else:
            raise _KnownError(f"Invalid field list line: {content_lines[0]!r}")
    return defaults
