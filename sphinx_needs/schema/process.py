import time
from collections.abc import Mapping
from itertools import chain

from sphinx.application import Sphinx
from sphinx.builders import Builder
from sphinx.util import logging

from sphinx_needs.api import get_needs_view
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.logging import log_error, log_warning
from sphinx_needs.needsfile import generate_needs_schema
from sphinx_needs.schema.config import NeedFieldsSchemaType, SchemasRootType
from sphinx_needs.schema.core import (
    NeedFieldProperties,
    validate_link_options,
    validate_option_fields,
    validate_type_schema,
)
from sphinx_needs.schema.reporting import (
    OntologyWarning,
    clear_debug_dir,
    generate_json_schema_validation_report,
    get_formatted_warnings,
)

logger = logging.getLogger(__name__)


def process_schemas(app: Sphinx, builder: Builder) -> None:
    """
    Validate all needs in a loop.

    Warnings and errors are emitted at the end.
    """
    config = NeedsSphinxConfig(app.config)

    if not config.schema_validation_enabled:
        return

    schema = SphinxNeedsData(app.env).get_schema()

    fields_schema: NeedFieldsSchemaType = {
        "type": "object",
        "properties": {
            field.name: field.schema
            for field in chain(schema.iter_core_fields(), schema.iter_extra_fields())
        },
    }
    links_schema: NeedFieldsSchemaType = {
        "type": "object",
        "properties": {link.name: link.schema for link in schema.iter_link_fields()},
    }

    schema = SphinxNeedsData(app.env).get_schema()
    field_properties: Mapping[str, NeedFieldProperties] = generate_needs_schema(schema)[
        "properties"
    ]

    if config.schema_debug_active:
        clear_debug_dir(config)

    # Start timer before validation loop
    start_time = time.perf_counter()

    needs = get_needs_view(app)

    need_2_warnings: dict[str, list[OntologyWarning]] = {}

    if fields_schema["properties"]:
        extra_warnings = validate_option_fields(
            config, fields_schema, field_properties, needs
        )
        for key, warnings in extra_warnings.items():
            need_2_warnings.setdefault(key, []).extend(warnings)

    if links_schema["properties"]:
        link_warnings = validate_link_options(
            config, links_schema, field_properties, needs
        )
        for key, warnings in link_warnings.items():
            need_2_warnings.setdefault(key, []).extend(warnings)

    type_schemas: list[SchemasRootType] = []
    if config.schema_definitions and "schemas" in config.schema_definitions:
        type_schemas = config.schema_definitions["schemas"]
    for type_schema in type_schemas:
        type_warnings = validate_type_schema(
            config, type_schema, needs, field_properties
        )
        for key, warnings in type_warnings.items():
            need_2_warnings.setdefault(key, []).extend(warnings)

    # Stop timer after validation loop
    end_time = time.perf_counter()

    formatted_warnings = get_formatted_warnings(need_2_warnings)
    for warning in formatted_warnings:
        if warning["log_lvl"] == "warning":
            log_warning(
                logger,
                warning["message"],
                warning["subtype"],  # type: ignore[arg-type]
                None,
                type=warning["type"],
            )
        elif warning["log_lvl"] == "error":
            log_error(
                logger,
                warning["message"],
                warning["subtype"],  # type: ignore[arg-type]
                None,
                type=warning["type"],
            )

    duration = end_time - start_time
    validated_needs_count = len(needs)
    validated_rate = (
        round(validated_needs_count / duration) if duration > 0 else float("inf")
    )
    generate_json_schema_validation_report(
        duration=duration,
        need_2_warnings=need_2_warnings,
        report_file_path=app.outdir / "schema_violations.json",
        validated_needs_count=validated_needs_count,
        validated_rate=validated_rate,
    )
    logger.info(
        f"Schema validation completed with {len(formatted_warnings)} warning(s) in {duration:.3f} seconds. Validated {validated_rate} needs/s."
    )
