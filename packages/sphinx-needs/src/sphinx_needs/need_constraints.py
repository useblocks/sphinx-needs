from __future__ import annotations

from collections.abc import Callable

from sphinx_needs._jinja import render_template_string
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsMutable
from sphinx_needs.exceptions import NeedsConstraintFailed
from sphinx_needs.filter_common import _need_by_need
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedConstraintResults, NeedItem, NeedPartItem

logger = get_logger(__name__)


def _report_tail(
    constraint: str, check: str
) -> Callable[[NeedItem | NeedPartItem], str]:
    """What the report of a failing check ends with: the constraint, the check, and the
    first need the check fails on."""
    return lambda need: (
        f"(from constraint {constraint!r}, check {check!r}, "
        f"first on need {need['id']!r})"
    )


def process_constraints(needs: NeedsMutable, config: NeedsSphinxConfig) -> None:
    """Analyse constraints of all needs,
    and set corresponding fields on the need data item:
    ``constraints_passed`` and ``constraints_results``.

    The ``style`` field may also be changed, if a constraint fails
    (depending on the config value ``constraint_failed_options``)

    A check whose filter fails on a need (it is no Python, names what the need does
    not have, raises, or is a constant) is reported once for the check, however many
    needs it fails on, naming the first of them, and is not evaluated on that need: it
    neither passes nor fails, and the need stores what it would have stored had the
    check not been declared.
    """
    config_constraints = config.constraints
    #: each check's filter, by constraint and check name: one report for each
    checks: dict[tuple[str, str], Callable[[NeedItem | NeedPartItem], bool | None]] = {}

    for need in needs.values():
        need_id = need["id"]

        results: dict[str, tuple[tuple[str, bool, str | None], ...]] = {}

        for constraint in need["constraints"]:
            results[constraint] = ()

            try:
                executable_constraints = config_constraints[constraint]
            except KeyError:
                # Note, this is already checked for in add_need
                continue

            # name is check_0, check_1, ...
            for name, cmd in executable_constraints.items():
                if name in ("severity", "error_message"):
                    # special keys, that are not a check
                    continue

                # compile constraint and check if need fulfils it
                if (check := checks.get((constraint, name))) is None:
                    check = checks[(constraint, name)] = _need_by_need(
                        cmd,
                        config,
                        # a constraint has no location: its report names the need
                        # the check fails on first
                        append_warning=_report_tail(constraint, name),
                    )
                if (constraint_passed := check(need)) is None:
                    # the check cannot be evaluated on the need: it is reported, and
                    # the need is left as if the check were not declared
                    continue

                error_msg: str | None = None
                if not constraint_passed:
                    if "error_message" in executable_constraints:
                        msg = str(executable_constraints["error_message"])
                        error_msg = render_template_string(
                            msg,
                            dict(need.items()),
                            autoescape=False,
                        )

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
                        log_warning(
                            logger,
                            f"Constraint {cmd} for need {need_id} FAILED! severity: {severity} {need.get('constraints_error', '')}",
                            "constraint",
                            location=(need["docname"], need["lineno"]),
                            color="red",
                        )
                    if "break" in failed_options.get("on_fail", []):
                        raise NeedsConstraintFailed(
                            f"FAILED a breaking constraint: >> {cmd} << for need "
                            f"{need_id} FAILED! breaking build process"
                        )

                    # set styles
                    old_style = need["style"]
                    if old_style and len(old_style) > 0:
                        new_styles = "".join(
                            ", " + x for x in failed_options.get("style", [])
                        )
                    else:
                        old_style = ""
                        new_styles = "".join(
                            x + "," for x in failed_options.get("style", [])
                        )

                    if failed_options.get("force_style", False):
                        need["style"] = new_styles.strip(", ")
                    else:
                        constraint_failed_style = old_style + new_styles
                        need["style"] = constraint_failed_style

                results[constraint] += ((name, constraint_passed, error_msg),)

        need.set_constraint_results(NeedConstraintResults(results))
