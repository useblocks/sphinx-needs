import time
from pathlib import Path

from sphinx.application import Sphinx
from sphinx.builders import Builder
from sphinx.util import logging

from sphinx_needs.api import get_needs_view
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.logging import log_warning
from sphinx_needs.needsfile import generate_needs_schema
from sphinx_needs.schema.config import SchemasRootType
from sphinx_needs.schema.core import (
    _needs_schema,
    merge_static_schemas,
    validate_need,
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
    needs = get_needs_view(app)
    config = NeedsSphinxConfig(app.config)

    # upfront work
    any_static_found = merge_static_schemas(config)

    if not (any_static_found or (config.schema_definitions.get("schemas"))):
        # nothing to validate but always generate report file
        generate_json_schema_validation_report(
            duration=0.00,
            need_2_warnings={},
            report_file_path=app.outdir / "schema_violations.json",
            validated_needs_count=0,
            validated_rate=0,
        )
        return

    # store the SN generated schema in a global variable
    schema = SphinxNeedsData(app.env).get_schema()
    needs_schema = generate_needs_schema(schema)["properties"]
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
            log_warning(
                logger,
                warning["message"],
                warning["subtype"],  # type: ignore[arg-type]
                None,
                type=warning["type"],
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
