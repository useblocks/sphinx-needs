import time
from pathlib import Path

from sphinx.application import Sphinx
from sphinx.builders import Builder
from sphinx.util import logging

from sphinx_needs.api import get_needs_view
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.needsfile import generate_needs_schema
from sphinx_needs.schema.core import (
    ContextEnum,
    _needs_schema,
    merge_static_schemas,
    validate_need,
)
from sphinx_needs.schema.reporting import (
    OntologyWarning,
    clear_debug_dir,
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

    needs_schema = generate_needs_schema(config)["properties"]

    orig_debug_path = Path(config.schemas_debug_path)
    if not orig_debug_path.is_absolute():
        # make it relative to confdir
        config.schemas_debug_path = str((Path(app.confdir) / orig_debug_path).resolve())

    # upfront work
    any_static_found = merge_static_schemas(config)

    if not (any_static_found or config.schemas):
        return

    _needs_schema.update(needs_schema)

    # set idx on each schema to track index in the list for reporting
    for idx, schema in enumerate(config.schemas):
        schema["idx"] = idx

    if config.schemas_debug_active:
        clear_debug_dir(config)

    # Start timer before validation loop
    start_time = time.perf_counter()

    need_2_warnings: dict[str, list[OntologyWarning]] = {}
    for need in needs.values():
        need_path = [need["id"]]
        schema_path: list[str] = []
        warnings = validate_need(
            config=config,
            need=dict(need),  # conversion as the need gets reduced in the process
            needs=needs,
            all_type_schemas=config.schemas,
            type_schemas=config.schemas,
            need_path=need_path,
            schema_path=schema_path,
            context=ContextEnum.PRIMARY,
        )
        if warnings:
            need_2_warnings[need["id"]] = warnings

    # Stop timer after validation loop
    end_time = time.perf_counter()

    formatted_warnings = get_formatted_warnings(config, need_2_warnings)
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
    logger.info(
        f"Schema validation completed in {duration:.3f} seconds. Validated {validated_rate} needs/s."
    )
