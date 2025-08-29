import json
import time
from pathlib import Path
from typing import TypedDict

from sphinx.application import Sphinx
from sphinx.builders import Builder
from sphinx.util import logging

from sphinx_needs.api import get_needs_view
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.needsfile import generate_needs_schema
from sphinx_needs.schema.config import SchemasRootType
from sphinx_needs.schema.core import (
    _needs_schema,
    merge_static_schemas,
    validate_need,
)
from sphinx_needs.schema.reporting import (
    JSONFormattedWarning,
    OntologyWarning,
    clear_debug_dir,
    get_formatted_warnings,
    get_json_formatted_warnings,
)

logger = logging.getLogger(__name__)


class OntologyReportJSON(TypedDict):
    validation_summary: str
    validated_rate: int | float
    validated_needs_count: int
    validation_warnings: dict[str, list[JSONFormattedWarning]]


def process_schemas(app: Sphinx, builder: Builder) -> None:
    """
    Validate all needs in a loop.

    Warnings and errors are emitted at the end.
    """
    needs = get_needs_view(app)
    config = NeedsSphinxConfig(app.config)

    # upfront work
    any_static_found = merge_static_schemas(config)

    if not (any_static_found or (config.schema_definitions.get("schemas"))):
        # nothing to validate
        return

    # store the SN generated schema in a global variable
    needs_schema = generate_needs_schema(config)["properties"]
    _needs_schema.update(needs_schema)

    orig_debug_path = Path(config.schema_debug_path)
    if not orig_debug_path.is_absolute():
        # make it relative to confdir
        config.schema_debug_path = str((Path(app.confdir) / orig_debug_path).resolve())

    if config.schema_debug_active:
        clear_debug_dir(config)

    # Start timer before validation loop
    start_time = time.perf_counter()

    need_2_warnings: dict[str, list[OntologyWarning]] = {}

    # validate needs
    type_schemas: list[SchemasRootType] = []
    if config.schema_definitions and "schemas" in config.schema_definitions:
        type_schemas = config.schema_definitions["schemas"]
    for need in needs.values():
        nested_warnings = validate_need(
            config=config,
            need=need,
            needs=needs,
            type_schemas=type_schemas,
        )
        if nested_warnings:
            need_2_warnings[need["id"]] = nested_warnings

    # Stop timer after validation loop
    end_time = time.perf_counter()

    formatted_warnings = get_formatted_warnings(need_2_warnings)
    for warning in formatted_warnings:
        if warning["log_lvl"] == "warning":
            logger.warning(
                warning["message"], type=warning["type"], subtype=warning["subtype"]
            )
        elif warning["log_lvl"] == "error":
            logger.error(
                warning["message"], type=warning["type"], subtype=warning["subtype"]
            )

    duration = end_time - start_time
    validated_needs_count = len(needs)
    validated_rate = (
        round(validated_needs_count / duration) if duration > 0 else float("inf")
    )
    json_formatted_warnings = get_json_formatted_warnings(need_2_warnings)
    ontology_report: OntologyReportJSON = {
        "validation_summary": (
            f"Schema validation completed with {len(json_formatted_warnings)} warning(s) in {duration:.3f} seconds. "
            f"Validated {validated_rate} needs/s."
        ),
        "validated_rate": validated_rate,
        "validated_needs_count": validated_needs_count,
        "validation_warnings": json_formatted_warnings,
    }
    ontology_filename = config.needs_ontology
    ontology_filename = (
        f"{ontology_filename}.json"
        if not ontology_filename.endswith(".json")
        else ontology_filename
    )
    # Store ontology report in JSON file
    with (app.outdir.joinpath(ontology_filename)).open("w") as fp:
        json.dump(ontology_report, fp, indent=2)
    logger.info(
        f"Schema validation completed with {len(formatted_warnings)} warning(s) in {duration:.3f} seconds. Validated {validated_rate} needs/s."
    )
