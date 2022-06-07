from docutils import nodes
from sphinx.application import Sphinx

from sphinx_needs.api.exceptions import NeedsConstraintFailed, NeedsConstraintNotAllowed
from sphinx_needs.config import NEEDS_CONFIG
from sphinx_needs.filter_common import filter_single_need
from sphinx_needs.logging import get_logger
from sphinx_needs.nodes import Need
from sphinx_needs.utils import profile

logger = get_logger(__name__)


def process_constraints(app, need) -> None:
    """
    Finally creates the need-node in the docurils node-tree.

    :param app:
    :param doctree:
    :param fromdocname:
    :return:
    """

    # TODO fix initial value for constraints_passed

    config_constraints = app.config.needs_constraints

    need_id = need["id"]

    constraints = need["constraints"]

    for constraint in constraints:

        if constraint not in [x for x in config_constraints.keys()]:
            raise NeedsConstraintNotAllowed(
                f"Constraint {constraint} of need id {need_id} is not allowed " "by config value 'needs_constraints'."
            )
        else:

            # access constraints defined in conf.py
            executable_constraints = config_constraints[constraint]

            for name, cmd in executable_constraints.items():
                # compile constraint and check single need if it fulfills constraint
                if name != "severity":

                    # check current need if it meets constraint given in check_0, check_1 in conf.py ...
                    constraint_passed = filter_single_need(app, need, cmd)

                    if not constraint_passed:
                        # prepare structure
                        if constraint not in need["constraints_results"].keys():
                            need["constraints_results"][constraint] = {}

                        # defines what to do if a constraint is not fulfilled. from conf.py
                        constraint_failed_options = app.config.needs_constraint_failed_options

                        if name not in need["constraints_results"][constraint].keys():
                            need["constraints_results"][constraint][name] = {}

                        need["constraints_results"][constraint][name] = False

                        # severity of failed constraint
                        severity = executable_constraints["severity"]

                        actions_on_fail = constraint_failed_options[severity]

                        if "warn" in actions_on_fail:
                            logger.warning(
                                f"Constraint {cmd} for need {need_id} FAILED! severity: {severity}", color="red"
                            )

                        if "break" in actions_on_fail:

                            raise NeedsConstraintFailed(
                                f"CRITICAL constraint: >> {cmd} << for need "
                                f"{need_id} FAILED! breaking build process"
                            )

                        if "mark" in actions_on_fail:

                            need["style"] = app.config.needs_constraints_failed_color

                    else:
                        need["constraints_results"][name] = constraint_passed

            # access all previous results, if one check failed, set constraints_passed to False for easy filtering
            results = [x[1] for x in need["constraints_results"].items()]

            if False in results:
                need["constraints_passed"] = False
            else:
                need["constraints_passed"] = True

    return
