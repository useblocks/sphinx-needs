from typing import Any, Dict

from sphinx.application import Sphinx

from sphinx_needs.api.exceptions import NeedsConstraintFailed, NeedsConstraintNotAllowed
from sphinx_needs.filter_common import filter_single_need
from sphinx_needs.logging import get_logger

logger = get_logger(__name__)


def process_constraints(app: Sphinx, need: Dict[str, Any]) -> None:
    """
    Finally creates the need-node in the docurils node-tree.

    :param app: sphinx app for access to config files
    :param need: need object to process
    """

    config_constraints = app.config.needs_constraints

    need_id = need["id"]

    constraints = need["constraints"]

    for constraint in constraints:
        # check if constraint is defined in config
        if constraint not in config_constraints.keys():
            raise NeedsConstraintNotAllowed(
                f"Constraint {constraint} of need id {need_id} is not allowed by config value 'needs_constraints'."
            )
        else:
            # access constraints defined in conf.py
            executable_constraints = config_constraints[constraint]

            # lazily gather all results to determine results_passed later
            results_list = []

            # name is check_0, check_1, ...
            for name, cmd in executable_constraints.items():
                # compile constraint and check single need if it fulfills constraint
                if name != "severity":
                    # check current need if it meets constraint given in check_0, check_1 in conf.py ...
                    constraint_passed = filter_single_need(app, need, cmd)
                    results_list.append(constraint_passed)

                    if not constraint_passed:
                        # prepare structure per name
                        if constraint not in need["constraints_results"].keys():
                            need["constraints_results"][constraint] = {}

                        # defines what to do if a constraint is not fulfilled. from conf.py
                        constraint_failed_options = app.config.needs_constraint_failed_options

                        # prepare structure for check_0, check_1 ...
                        if name not in need["constraints_results"][constraint].keys():
                            need["constraints_results"][constraint][name] = {}

                        need["constraints_results"][constraint][name] = False

                        # severity of failed constraint
                        severity = executable_constraints["severity"]

                        # configurable force of constraint failed style
                        force_style = constraint_failed_options[severity]["force_style"]

                        actions_on_fail = constraint_failed_options[severity]["on_fail"]
                        style_on_fail = constraint_failed_options[severity]["style"]

                        if "warn" in actions_on_fail:
                            logger.warning(
                                f"Constraint {cmd} for need {need_id} FAILED! severity: {severity}", color="red"
                            )

                        if "break" in actions_on_fail:
                            raise NeedsConstraintFailed(
                                f"FAILED a breaking constraint: >> {cmd} << for need "
                                f"{need_id} FAILED! breaking build process"
                            )

                        old_style = need["style"]

                        # append to style if present
                        if old_style and len(old_style) > 0:
                            new_styles = "".join(", " + x for x in style_on_fail)
                        else:
                            old_style = ""
                            new_styles = "".join(x + "," for x in style_on_fail)

                        if force_style:
                            need["style"] = new_styles.strip(", ")
                        else:
                            constraint_failed_style = old_style + new_styles
                            need["style"] = constraint_failed_style

                    else:
                        # constraint is met, fill corresponding need attributes

                        # prepare structure
                        if constraint not in need["constraints_results"].keys():
                            need["constraints_results"][constraint] = {}
                        need["constraints_results"][constraint][name] = constraint_passed

            # access all previous results, if one check failed, set constraints_passed to False for easy filtering
            if False in results_list:
                need["constraints_passed"] = False
            else:
                need["constraints_passed"] = True
