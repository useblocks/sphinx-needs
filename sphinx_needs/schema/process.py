import time
from collections.abc import Mapping

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
    validate_extra_options,
    validate_link_options,
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

    extra_option_schema: NeedFieldsSchemaType = {
        "type": "object",
        "properties": {
            name: option.schema
            for name, option in config.extra_options.items()
            if option.schema is not None
        },
    }
    extra_link_schema: NeedFieldsSchemaType = {
        "type": "object",
        "properties": {
            link["option"]: link["schema"]
            for link in config.extra_links
            if "schema" in link and link["schema"] is not None
        },
    }

    if not (
        extra_option_schema["properties"]
        or extra_link_schema["properties"]
        or (config.schema_definitions.get("schemas"))
    ):
        # nothing to validate but always generate report file
        generate_json_schema_validation_report(
            duration=0.00,
            need_2_warnings={},
            report_file_path=app.outdir / "schema_violations.json",
            validated_needs_count=0,
            validated_rate=0,
        )
        return

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

    if extra_option_schema["properties"]:
        extra_warnings = validate_extra_options(
            config, extra_option_schema, field_properties, needs
        )
        for key, warnings in extra_warnings.items():
            need_2_warnings.setdefault(key, []).extend(warnings)

    if extra_link_schema["properties"]:
        link_warnings = validate_link_options(
            config, extra_link_schema, field_properties, needs
        )
        for key, warnings in link_warnings.items():
            need_2_warnings.setdefault(key, []).extend(warnings)

    type_schemas: list[SchemasRootType] = []
    if config.schema_definitions and "schemas" in config.schema_definitions:
        type_schemas = config.schema_definitions["schemas"]
    for type_schema in type_schemas:
        type_warnings = validate_type_schema(
            config=config,
            needs=needs,
            field_properties=field_properties,
            type_schema=type_schema,
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
