from __future__ import annotations

from typing import Literal

from docutils.nodes import Node
from sphinx import version_info
from sphinx.util import logging
from sphinx.util.logging import SphinxLoggerAdapter


def get_logger(name: str) -> SphinxLoggerAdapter:
    return logging.getLogger(name)


WarningSubTypes = Literal[
    "config",
    "constraint",
    "create_need",
    "delete_need",
    "deprecated",
    "diagram_scale",
    "duplicate_id",
    "duplicate_part_id",
    "dynamic_function",
    "external_link_outgoing",
    "needextend",
    "needextract",
    "needflow",
    "needgantt",
    "needimport",
    "needreport",
    "needsequence",
    "filter",
    "filter_func",
    "github",
    "import_need",
    "json_load",
    "layout",
    "link_outgoing",
    "link_ref",
    "link_text",
    "load_external_need",
    "load_service_need",
    "mpl",
    "title",
    "uml",
    "unknown_external_keys",
    "mistyped_external_values",
    "unknown_import_keys",
    "mistyped_import_values",
    "variant",
    "warnings",
]

WarningSubTypeDescription: dict[WarningSubTypes, str] = {
    "config": "Invalid configuration",
    "constraint": "Constraint violation",
    "create_need": "Creation of a need from directive failed",
    "delete_need": "Deletion of a need failed",
    "deprecated": "Deprecated feature",
    "diagram_scale": "Failed to process diagram scale option",
    "duplicate_id": "Duplicate need ID found when merging needs from parallel processes",
    "duplicate_part_id": "Duplicate part ID found when parsing need content",
    "dynamic_function": "Failed to load/execute dynamic function",
    "needextend": "Error processing needextend directive",
    "needextract": "Error processing needextract directive",
    "needflow": "Error processing needflow directive",
    "needgantt": "Error processing needgantt directive",
    "needimport": "Error processing needimport directive",
    "needreport": "Error processing needreport directive",
    "needsequence": "Error processing needsequence directive",
    "filter": "Error processing needs filter",
    "filter_func": "Error loading needs filter function",
    "github": "Error in processing GitHub service directive",
    "import_need": "Failed to import a need",
    "layout": "Error occurred during layout rendering of a need",
    "link_outgoing": "Unknown outgoing link in standard need",
    "external_link_outgoing": "Unknown outgoing link in external need",
    "link_ref": "Need could not be referenced",
    "link_text": "Reference text could not be generated",
    "load_external_need": "Failed to load an external need",
    "load_service_need": "Failed to load a service need",
    "mpl": "Matplotlib required but not installed",
    "title": "Error creating need title",
    "uml": "Error in processing of UML diagram",
    "unknown_external_keys": "Unknown keys found in external need data",
    "mistyped_external_values": "Unexpected value types found in external need data",
    "unknown_import_keys": "Unknown keys found in imported need data",
    "mistyped_import_values": "Unexpected value types found in imported need data",
    "variant": "Error processing variant in need field",
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
) -> None:
    # Since sphinx in v7.3, sphinx will show warning types if `show_warning_types=True` is set,
    # and in v8.0 this was made the default.
    if version_info < (8,):
        if subtype:
            message += f" [needs.{subtype}]"
        else:
            message += " [needs]"

    logger.warning(
        message,
        type="needs",
        subtype=subtype,
        location=location,
        color=color,
        once=once,
    )
