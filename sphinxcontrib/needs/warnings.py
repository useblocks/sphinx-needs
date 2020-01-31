"""
Cares about handling and execution warnings.

"""
from pkg_resources import parse_version
import sphinx
from sphinxcontrib.needs.filter_common import filter_needs

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging

logger = logging.getLogger(__name__)


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
    if exception is not None:
        return

    env = app.env
    # If no needs were defined, we do not need to do anything
    if not hasattr(env, "needs_all_needs"):
        return

    # Check if warnings already got executed.
    # Needed because the used event gets executed multiple times, but warnings need to be checked only
    # on first execution
    if hasattr(env, "needs_warnings_executed") and env.needs_warnings_executed is True:
        return

    env.needs_warnings_executed = True

    needs = env.needs_all_needs

    warnings = getattr(app.config, 'needs_warnings', {})

    with logging.pending_logging():
        logger.info('\nChecking sphinx-needs warnings')
        warning_raised = False
        for warning_name, warning_filter in warnings.items():
            result = filter_needs(needs.values(), warning_filter)
            if len(result) == 0:
                logger.info('  {}: passed'.format(warning_name))
            else:
                need_ids = [x['id'] for x in result]
                logger.info('  {}: failed'.format(warning_name))
                logger.info('  \t\tfailed needs: {} ({})'.format(len(need_ids), ', '.join(need_ids)))
                logger.info('  \t\tused filter: {}'.format(warning_filter))
                warning_raised = True

        if warning_raised:
            logger.warning('Sphinx-Needs warnings were raised. See console / log output for details.')



