"""
Cares about handling and execution warnings.

"""
from sphinxcontrib.needs.filter_common import filter_needs
from sphinxcontrib.needs.logging import get_logger, logging

logger = get_logger(__name__)


def process_warnings(app, exception):
    """
    Checks the configured warnings.

    This func gets called by the latest sphinx-event, so that really everything is already done.

    :param app: application
    :param exception: raised exceptions
    :return:
    """

    # We cget called also if an exception occured during build
    # In this case the build is already broken and we do not need to check anything.
    if exception:
        return

    env = app.env
    # If no needs were defined, we do not need to do anything
    if not hasattr(env, "needs_all_needs"):
        return

    # Check if warnings already got executed.
    # Needed because the used event gets executed multiple times, but warnings need to be checked only
    # on first execution
    if hasattr(env, "needs_warnings_executed") and env.needs_warnings_executed:
        return

    env.needs_warnings_executed = True

    needs = env.needs_all_needs

    warnings = app.config.needs_warnings

    warnings_always_warn = app.config.needs_warnings_always_warn

    with logging.pending_logging():
        logger.info("\nChecking sphinx-needs warnings")
        warning_raised = False
        for warning_name, warning_filter in warnings.items():
            if isinstance(warning_filter, str):
                # filter string used
                result = filter_needs(needs.values(), warning_filter)
            elif hasattr(warning_filter, "__call__"):
                # custom defined filter code used from conf.py
                result = []
                for need in needs.values():
                    if warning_filter(need, logger):
                        result.append(need)
            else:
                logger.warning("Unknown needs warnings filter {}!".format(warning_filter))

            if len(result) == 0:
                logger.info("{}: passed".format(warning_name))
            else:
                need_ids = [x["id"] for x in result]
                if warnings_always_warn:
                    logger.warning(
                        "{}: failed\n\t\tfailed needs: {} ({})\n\t\tused filter: {}".format(
                            warning_name, len(need_ids), ", ".join(need_ids), warning_filter
                        )
                    )
                else:
                    logger.info(
                        "{}: failed\n\t\tfailed needs: {} ({})\n\t\tused filter: {}".format(
                            warning_name, len(need_ids), ", ".join(need_ids), warning_filter
                        )
                    )
                    warning_raised = True

        if warning_raised:
            logger.warning("Sphinx-Needs warnings were raised. See console / log output for details.")
