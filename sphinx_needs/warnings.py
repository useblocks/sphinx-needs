"""
Cares about handling and execution warnings.

"""

from __future__ import annotations

from sphinx.application import Sphinx
from sphinx.util import logging

from sphinx_needs.config import NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType, SphinxNeedsData
from sphinx_needs.filter_common import filter_needs
from sphinx_needs.logging import get_logger

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

    env = app.env
    needs = SphinxNeedsData(env).get_or_create_needs()
    # If no needs were defined, we do not need to do anything
    if not needs:
        return

    # Check if warnings already got executed.
    # Needed because the used event gets executed multiple times, but warnings need to be checked only
    # on first execution
    if hasattr(env, "needs_warnings_executed") and env.needs_warnings_executed:
        return

    env.needs_warnings_executed = True  # type: ignore[attr-defined]

    # Exclude external needs for warnings check
    checked_needs: dict[str, NeedsInfoType] = {}
    for need_id, need in needs.items():
        if not need["is_external"]:
            checked_needs[need_id] = need

    needs_config = NeedsSphinxConfig(app.config)
    warnings_always_warn = needs_config.warnings_always_warn

    with logging.pending_logging():
        logger.info("\nChecking sphinx-needs warnings")
        warning_raised = False
        for warning_name, warning_filter in NEEDS_CONFIG.warnings.items():
            if isinstance(warning_filter, str):
                # filter string used
                result = filter_needs(
                    checked_needs.values(),
                    needs_config,
                    warning_filter,
                    append_warning=f"(from warning filter {warning_name!r})",
                )
            elif callable(warning_filter):
                # custom defined filter code used from conf.py
                result = []
                for need in checked_needs.values():
                    if warning_filter(need, logger):
                        result.append(need)
            else:
                logger.warning(
                    f"Unknown needs warnings filter {warning_filter}! [needs]",
                    type="needs",
                )

            if len(result) == 0:
                logger.info(f"{warning_name}: passed")
            else:
                need_ids = [x["id"] for x in result]

                # Set Sphinx statuscode to 1, only if -W is used with sphinx-build
                # Because Sphinx statuscode got calculated in very early build phase and based on warning_count
                # Sphinx-needs warnings check hasn't happened yet
                # see deatils in https://github.com/sphinx-doc/sphinx/blob/81a4fd973d4cfcb25d01a7b0be62cdb28f82406d/sphinx/application.py#L345
                # To be clear, app.keep_going = -W and --keep-going, and will overrite -W after
                # see details in https://github.com/sphinx-doc/sphinx/blob/4.x/sphinx/application.py#L182
                if app.statuscode == 0 and (app.keep_going or app.warningiserror):
                    app.statuscode = 1

                # get the text for used filter, either from filter string or function name
                if callable(warning_filter):
                    warning_text = warning_filter.__name__
                elif isinstance(warning_filter, str):
                    warning_text = warning_filter

                if warnings_always_warn:
                    logger.warning(
                        "{}: failed\n\t\tfailed needs: {} ({})\n\t\tused filter: {} [needs]".format(
                            warning_name,
                            len(need_ids),
                            ", ".join(need_ids),
                            warning_text,
                        ),
                        type="needs",
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
            logger.warning(
                "warnings were raised. See console / log output for details. [needs]",
                type="needs",
            )
