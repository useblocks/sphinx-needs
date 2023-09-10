from sphinx_needs.api.exceptions import NeedsConstraintFailed, NeedsConstraintNotAllowed
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.filter_common import filter_single_need
from sphinx_needs.logging import get_logger

logger = get_logger(__name__)


def process_constraints(data: SphinxNeedsData, config: NeedsSphinxConfig) -> None:
    """Analyse constraints of all needs,
    and set corresponding fields on the need data item:
    ``constraints_passed`` and ``constraints_results``.

    The ``style`` field may also be changed, if a constraint fails
    (depending on the config value ``constraint_failed_options``)
    """
    config_constraints = config.constraints
    for need in data.get_or_create_needs().values():
        need_id = need["id"]
        constraints = need["constraints"]

        # flag that is set to False if any check fails
        need["constraints_passed"] = True

        for constraint in constraints:
            try:
                executable_constraints = config_constraints[constraint]
            except KeyError:
                # Note, this is already checked for in add_need
                raise NeedsConstraintNotAllowed(
                    f"Constraint {constraint} of need id {need_id} is not allowed by config value 'needs_constraints'."
                )

            # name is check_0, check_1, ...
            for name, cmd in executable_constraints.items():
                if name == "severity":
                    # special key, that is not a check
                    continue

                # compile constraint and check if need fulfils it
                constraint_passed = filter_single_need(config, need, cmd)

                if constraint_passed:
                    need["constraints_results"].setdefault(constraint, {})[name] = True
                else:
                    need["constraints_results"].setdefault(constraint, {})[name] = False
                    need["constraints_passed"] = False

                    if "severity" not in executable_constraints:
                        raise NeedsConstraintFailed(
                            f"'severity' key not set for constraint {constraint!r} in config 'needs_constraints'"
                        )
                    severity = executable_constraints["severity"]
                    if severity not in config.constraint_failed_options:
                        raise NeedsConstraintFailed(
                            f"Severity {severity!r} not set in config 'needs_constraint_failed_options'"
                        )
                    failed_options = config.constraint_failed_options[severity]

                    # log/except if needed
                    if "warn" in failed_options.get("on_fail", []):
                        logger.warning(
                            f"Constraint {cmd} for need {need_id} FAILED! severity: {severity} [needs.constraint]",
                            type="needs",
                            subtype="constraint",
                            color="red",
                            location=(need["docname"], need["lineno"]),
                        )
                    if "break" in failed_options.get("on_fail", []):
                        raise NeedsConstraintFailed(
                            f"FAILED a breaking constraint: >> {cmd} << for need "
                            f"{need_id} FAILED! breaking build process"
                        )

                    # set styles
                    old_style = need["style"]
                    if old_style and len(old_style) > 0:
                        new_styles = "".join(", " + x for x in failed_options.get("style", []))
                    else:
                        old_style = ""
                        new_styles = "".join(x + "," for x in failed_options.get("style", []))

                    if failed_options.get("force_style", False):
                        need["style"] = new_styles.strip(", ")
                    else:
                        constraint_failed_style = old_style + new_styles
                        need["style"] = constraint_failed_style
