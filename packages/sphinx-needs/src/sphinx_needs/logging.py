from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from docutils.nodes import Node
from sphinx import version_info
from sphinx.util import logging
from sphinx.util.logging import SphinxLoggerAdapter

if TYPE_CHECKING:
    from sphinx.application import Sphinx
    from sphinx.config import Config


def get_logger(name: str) -> SphinxLoggerAdapter:
    return logging.getLogger(name)


# --- Sphinx 7 only; remove with the Sphinx 8 floor -----------------------------------
# Sphinx renders a warning's ``[type.subtype]`` itself when ``show_warning_types`` is on
# (its default from 8.0). Before 8.0 the helpers below append it where Sphinx will not.
_sphinx_renders_types = version_info >= (8,)


def configure_warning_types(_app: Sphinx, config: Config) -> None:
    global _sphinx_renders_types
    _sphinx_renders_types = version_info >= (8,) or bool(config.show_warning_types)


# ------------------------------------------------------------------------------------


# keep below 2 dicts sorted to spot missing items
WarningSubTypes = Literal[
    "beta",
    "card_layout",
    "choose",
    "config",
    "constraint",
    "create_need",
    "delete_need",
    "deprecated",
    "derive_authored",
    "derive_cycle",
    "derive_invalid",
    "derive_scope",
    "derive_unique",
    "diagram_scale",
    "directive",
    "duplicate_id",
    "duplicate_part_id",
    "dynamic_function",
    "external_link_outgoing",
    "filter_func",
    "filter",
    "github",
    "if",
    "import_doctype",
    "import_need",
    "json_load",
    "layout",
    "link_condition_failed",
    "link_condition_invalid",
    "link_outgoing",
    "link_ref",
    "link_text",
    "load_external_need",
    "load_service_need",
    "max_items",
    "mistyped_external_values",
    "mistyped_import_values",
    "mpl",
    "needextend",
    "needextract",
    "needflow",
    "needgantt",
    "needimport",
    "needreport",
    "needsequence",
    "needuml",
    "part",
    "string_link",
    "title",
    "uml",
    "unknown_external_keys",
    "unknown_import_keys",
    "variant",
    "variant_data_location",
    "variants_unknown_key",
    "warnings",
]

WarningSubTypeDescription: dict[WarningSubTypes, str] = {
    "beta": "Beta feature, subject to change",
    "card_layout": "Invalid ``needs_card_layouts`` specification",
    "choose": "Error in processing choose/when/otherwise directive",
    "config": "Invalid configuration",
    "constraint": "Constraint violation",
    "create_need": "Creation of a need from directive failed",
    "delete_need": "Deletion of a need failed",
    "deprecated": "Deprecated feature",
    "derive_authored": "A derived field is set in a need or by a needextend; the value is ignored",
    "derive_cycle": "A dynamic function or variant is on a cycle of computed values; the field is not computed",
    "derive_invalid": "A derive rule of needs_fields or needs_links cannot be read, or a default is given beside it",
    "derive_scope": "A dynamic function, variant or needextend filter reads a value that cannot be computed before it",
    "derive_unique": 'A derived copy with select = "unique" finds several needs that set the field; the lowest id is copied',
    "diagram_scale": "Failed to process diagram scale option",
    "directive": "Error in processing a need directive",
    "duplicate_id": "Duplicate need ID found when merging needs from parallel processes",
    "duplicate_part_id": "Duplicate part ID found when parsing need content",
    "dynamic_function": "Failed to load/execute dynamic function",
    "external_link_outgoing": "Unknown outgoing link in external need",
    "filter_func": "Error loading needs filter function",
    "filter": "Error processing needs filter",
    "github": "Error in processing GitHub service directive",
    "if": "Error in processing if directive",
    "import_doctype": "Imported need content declares a doctype the project cannot parse; parsed as the page's markup",
    "import_need": "Failed to import a need",
    "layout": "Error occurred during layout rendering of a need",
    "link_condition_failed": "Link condition not satisfied by targeted need",
    "link_condition_invalid": "Link condition has invalid filter syntax",
    "link_outgoing": "Unknown outgoing link in standard need",
    "link_ref": "Need could not be referenced",
    "link_text": "Reference text could not be generated",
    "load_external_need": "Failed to load an external need",
    "load_service_need": "Failed to load a service need",
    "max_items": "View truncated by a max_items limit",
    "mistyped_external_values": "Unexpected value types found in external need data",
    "mistyped_import_values": "Unexpected value types found in imported need data",
    "mpl": "Matplotlib required but not installed",
    "needextend": "Error processing needextend directive",
    "needextract": "Error processing needextract directive",
    "needflow": "Error processing needflow directive",
    "needgantt": "Error processing needgantt directive",
    "needimport": "Error processing needimport directive",
    "needreport": "Error processing needreport directive",
    "needsequence": "Error processing needsequence directive",
    "needuml": "Error processing needuml/needarch directive",
    "part": "Error processing need part",
    "string_link": "Invalid ``needs_string_links`` configuration",
    "title": "Error creating need title",
    "uml": "Error in processing of UML diagram",
    "unknown_external_keys": "Unknown keys found in external need data",
    "unknown_import_keys": "Unknown keys found in imported need data",
    "variant": "Error processing variant in need field",
    "variant_data_location": "Variant data set in both ``[variants]`` and ``[needs]``; the ``[needs]`` keys are ignored",
    "variants_unknown_key": "Unknown key in the ``[variants]`` table",
    "warnings": "Need warning check failed for one or more needs",
}


def log_warning(
    logger: SphinxLoggerAdapter,
    message: str,
    subtype: WarningSubTypes,
    /,
    location: str | tuple[str | None, int | None] | Node | None,
    *,
    color: str | None = None,
    once: bool = False,
    type: str = "needs",
) -> None:
    if not _sphinx_renders_types:
        message += f" [{type}.{subtype}]"

    logger.warning(
        message,
        type=type,
        subtype=subtype,
        location=location,
        color=color,
        once=once,
    )


def log_error(
    logger: SphinxLoggerAdapter,
    message: str,
    subtype: WarningSubTypes,
    /,
    location: str | tuple[str | None, int | None] | Node | None,
    *,
    color: str | None = None,
    once: bool = False,
    type: str = "needs",
) -> None:
    if not _sphinx_renders_types:
        message += f" [{type}.{subtype}]"

    logger.error(
        message,
        type=type,
        subtype=subtype,
        location=location,
        color=color,
        once=once,
    )
