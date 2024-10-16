"""
Cares about handling and execution warnings.

"""

from __future__ import annotations

from sphinx.application import Sphinx
from sphinx.util import logging

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.filter_common import filter_needs_view
from sphinx_needs.logging import get_logger, log_warning

logger = get_logger(__name__)


def process_warnings(app: Sphinx, exception: Exception | None) -> None:
    """
    Checks the configured warnings.

    This func gets called by the latest sphinx-event, so that really everything is already done.

    :param app: application
    :param exception: raised exceptions
    :return:
    """

    # We get called also if an exception occured during build
    # In this case the build is already broken and we do not need to check anything.
    if exception:
        return

    needs_config = NeedsSphinxConfig(app.config)

    # If no warnings were defined, we do not need to do anything
    if not needs_config.warnings:
        return

    env = app.env
    needs_view = SphinxNeedsData(env).get_needs_view()
    # If no needs were defined, we do not need to do anything
    if not needs_view:
        return

    # Check if warnings already got executed.
    # Needed because the used event gets executed multiple times, but warnings need to be checked only
    # on first execution
    if hasattr(env, "_needs_warnings_executed") and env._needs_warnings_executed:
        return

    env._needs_warnings_executed = True  # type: ignore[attr-defined]

    # Exclude external needs for warnings check
    needs_view = needs_view.filter_is_external(False)

    needs_config = NeedsSphinxConfig(app.config)
    warnings_always_warn = needs_config.warnings_always_warn

    with logging.pending_logging():
        logger.info("\nChecking sphinx-needs warnings")
        warning_raised = False
        for warning_name, warning_filter in needs_config.warnings.items():
            if isinstance(warning_filter, str):
                # filter string used
                result = filter_needs_view(
                    needs_view,
                    needs_config,
                    warning_filter,
                    append_warning=f"(from warning filter {warning_name!r})",
                )
            elif callable(warning_filter):
                # custom defined filter code used from conf.py
                result = []
                for need in needs_view.values():
                    if warning_filter(need, logger):
                        result.append(need)
            else:
                log_warning(logger, f"Unknown needs warnings filter {warning_filter}!")

            if len(result) == 0:
                logger.info(f"{warning_name}: passed")
            else:
                need_ids = [x["id"] for x in result]

                # get the text for used filter, either from filter string or function name
                if callable(warning_filter):
                    warning_text = warning_filter.__name__
                elif isinstance(warning_filter, str):
                    warning_text = warning_filter

                if warnings_always_warn:
                    log_warning(
                        logger,
                        "{}: failed\n\t\tfailed needs: {} ({})\n\t\tused filter: {}".format(
                            warning_name,
                            len(need_ids),
                            ", ".join(need_ids),
                            warning_text,
                        ),
                        "warnings",
                        None,
                    )
                else:
                    logger.info(
                        "{}: failed\n\t\tfailed needs: {} ({})\n\t\tused filter: {}".format(
                            warning_name,
                            len(need_ids),
                            ", ".join(need_ids),
                            warning_text,
                        )
                    )
                    warning_raised = True

        if warning_raised:
            log_warning(
                logger,
                "warnings were raised. See console / log output for details.",
                "warnings",
                None,
            )
