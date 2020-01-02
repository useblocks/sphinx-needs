"""
Cares about handling and execution constraints.

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


def process_constraints(app, env):
    # If no needs were defined, we do not need to do anything
    if not hasattr(env, "needs_all_needs"):
        return

    needs = env.needs_all_needs

    constraints = getattr(app.config, 'needs_constraints', {})

    with logging.pending_logging():
        logger.info('\nChecking sphinx-needs constraints')
        const_raised = False
        for constraint_name, constraint_filter in constraints.items():
            result = filter_needs(needs.values(), constraint_filter)
            if len(result) == 0:
                logger.info('  {}: passed'.format(constraint_name))
            else:
                need_ids = [x['id'] for x in result]
                logger.info('  {}: failed'.format(constraint_name))
                logger.info('  \t\tfailed needs: {} ({})'.format(len(need_ids), ', '.join(need_ids)))
                logger.info('  \t\tused filter: {}'.format(constraint_filter))
                const_raised = True

        if const_raised:
            logger.warning('Sphinx-Needs constraints were raised. See console / log output for details.')



