from __future__ import annotations

import re
from typing import Any

from docutils import nodes

from sphinx_needs.data import NeedsFilteredBaseType
from sphinx_needs.defaults import TITLE_REGEX
from sphinx_needs.logging import get_logger, log_warning

LOGGER = get_logger(__name__)


def no_needs_found_paragraph(message: str | None) -> nodes.paragraph:
    nothing_found = "No needs passed the filters" if message is None else message
    para = nodes.paragraph()
    para["classes"].append("needs_filter_warning")
    nothing_found_node = nodes.Text(nothing_found)
    para += nothing_found_node
    return para


def used_filter_paragraph(current_needfilter: NeedsFilteredBaseType) -> nodes.paragraph:
    para = nodes.paragraph()
    filter_text = "Used filter:"
    filter_text += (
        " status({})".format(" OR ".join(current_needfilter["status"]))
        if len(current_needfilter["status"]) > 0
        else ""
    )
    if len(current_needfilter["status"]) > 0 and len(current_needfilter["tags"]) > 0:
        filter_text += " AND "
    filter_text += (
        " tags({})".format(" OR ".join(current_needfilter["tags"]))
        if len(current_needfilter["tags"]) > 0
        else ""
    )
    if (
        len(current_needfilter["status"]) > 0 or len(current_needfilter["tags"]) > 0
    ) and len(current_needfilter["types"]) > 0:
        filter_text += " AND "
    filter_text += (
        " types({})".format(" OR ".join(current_needfilter["types"]))
        if len(current_needfilter["types"]) > 0
        else ""
    )

    filter_node = nodes.emphasis(filter_text, filter_text)
    para += filter_node
    return para


def max_items_paragraph(shown: int, total: int, unit: str = "needs") -> nodes.paragraph:
    """Create the notice shown when a view was truncated by ``max_items``.

    :param shown: the number of items that are rendered.
    :param total: the number of items the view would have rendered without a limit.
    :param unit: the name of the items being counted.

    :return: the notice paragraph.
    """
    para = nodes.paragraph()
    para["classes"].append("needs_max_items_notice")
    text = (
        f"Showing the first {shown} of {total} {unit};"
        " refine the filter or set :max_items: (0 for all)."
    )
    para += nodes.emphasis(text, text)
    return para


def report_max_items(
    shown: int,
    total: int,
    /,
    *,
    origin: str,
    location: nodes.Element,
    unit: str = "needs",
) -> nodes.paragraph:
    """Report that a view was truncated, both in the document and in the build log.

    The two go together: the notice tells whoever reads the page, and the warning tells
    whoever runs the build, who would otherwise have to read every page to find out that
    anything was dropped. The warning has its own sub-type, so a project that caps
    deliberately can silence it with ``suppress_warnings = ["needs.max_items"]``.

    :param shown: the number of items that are rendered.
    :param total: the number of items the view would have rendered without a limit.
    :param origin: the name of the directive, for the warning message.
    :param location: the view node, so that the warning carries its source location.
    :param unit: the name of the items being counted.

    :return: the notice paragraph, to be added to the document.
    """
    log_warning(
        LOGGER,
        f"{origin}: showing the first {shown} of {total} {unit},"
        " due to the max_items limit.",
        "max_items",
        location=location,
    )
    return max_items_paragraph(shown, total, unit)


def get_title(option_string: str) -> tuple[str, str]:
    """
    Returns a tuple of uppercase option and calculated title of given option string.

    :param option_string:
    :return: string
    """
    if option_string.upper() == "ID":
        return "ID", "ID"
    match = re.search(TITLE_REGEX, option_string)
    if not match:
        return option_string.upper(), option_string.title().replace("_", " ")

    option_name = match.group(1)
    title = match.group(2)

    return option_name.upper(), title


def get_option_list(options: dict[str, Any], name: str) -> list[str]:
    """
    Gets and creates a list of a given directive option value in a safe way
    :param options: List of options
    :param name: Name of the option
    :return: List with strings
    """
    values = str(options.get(name, ""))
    values_list = []
    if isinstance(values, str):
        values_list = [value.strip() for value in re.split("[;,]", values)]

    return values_list


class SphinxNeedsLinkTypeException(BaseException):
    """Raised if problems with link types happen"""
