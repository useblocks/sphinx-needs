"""


"""
import re
from typing import Any, Callable, Dict, Sequence

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api.exceptions import NeedsInvalidFilter
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsExtendType, NeedsInfoType, SphinxNeedsData
from sphinx_needs.filter_common import filter_needs
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import add_doc

logger = get_logger(__name__)


class Needextend(nodes.General, nodes.Element):
    pass


class NeedextendDirective(SphinxDirective):
    """
    Directive to modify existing needs
    """

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True

    option_spec: Dict[str, Callable[[str], Any]] = {
        "strict": directives.unchanged_required,
    }

    def run(self) -> Sequence[nodes.Node]:
        env = self.env

        id = env.new_serialno("needextend")
        targetid = f"needextend-{env.docname}-{id}"
        targetnode = nodes.target("", "", ids=[targetid])

        extend_filter = self.arguments[0] if self.arguments else None
        if not extend_filter:
            raise NeedsInvalidFilter(f"Filter of needextend must be set. See {env.docname}:{self.lineno}")

        strict_option = self.options.get("strict", str(NeedsSphinxConfig(self.env.app.config).needextend_strict))
        strict = True
        if strict_option.upper() == "TRUE":
            strict = True
        elif strict_option.upper() == "FALSE":
            strict = False

        data = SphinxNeedsData(env).get_or_create_extends()
        data[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "filter": self.arguments[0] if self.arguments else None,
            "modifications": self.options,
            "strict": strict,
        }

        add_doc(env, env.docname)

        return [targetnode, Needextend("")]


def extend_needs_data(
    all_needs: Dict[str, NeedsInfoType], extends: Dict[str, NeedsExtendType], needs_config: NeedsSphinxConfig
) -> None:
    """Use data gathered from needextend directives to modify fields of existing needs."""

    list_values = ["tags", "links"] + [x["option"] for x in needs_config.extra_links]
    link_names = [x["option"] for x in needs_config.extra_links]

    for current_needextend in extends.values():
        need_filter = current_needextend["filter"]
        if need_filter in all_needs:
            # a single known ID
            found_needs = [all_needs[need_filter]]
        elif need_filter is not None and re.fullmatch(needs_config.id_regex, need_filter):
            # an unknown ID
            error = f"Provided id {need_filter} for needextend does not exist."
            if current_needextend["strict"]:
                raise NeedsInvalidFilter(error)
            else:
                logger.info(error)
                continue
        else:
            # a filter string
            try:
                found_needs = filter_needs(all_needs.values(), needs_config, need_filter)
            except NeedsInvalidFilter as e:
                raise NeedsInvalidFilter(
                    f"Filter not valid for needextend on page {current_needextend['docname']}:\n{e}"
                )

        for found_need in found_needs:
            # Work in the stored needs, not on the search result
            need = all_needs[found_need["id"]]
            need["is_modified"] = True
            need["modifications"] += 1

            for option, value in current_needextend["modifications"].items():
                if option.startswith("+"):
                    option_name = option[1:]
                    if option_name in link_names:
                        if value.strip().startswith("[[") and value.strip().endswith("]]"):  # dynamic function
                            need[option_name].append(value)
                        else:
                            for ref_need in [i.strip() for i in re.split(";|,", value)]:
                                if ref_need not in all_needs:
                                    logger.warning(
                                        f"Provided link id {ref_need} for needextend does not exist. [needs]",
                                        type="needs",
                                        location=(current_needextend["docname"], current_needextend["lineno"]),
                                    )
                                    continue
                                if ref_need not in need[option_name]:
                                    need[option_name].append(ref_need)
                    elif option_name in list_values:
                        if value.strip().startswith("[[") and value.strip().endswith("]]"):  # dynamic function
                            need[option_name].append(value)
                        else:
                            for item in [i.strip() for i in re.split(";|,", value)]:
                                if item not in need[option_name]:
                                    need[option_name].append(item)
                    else:
                        if need[option_name]:
                            # If content is already stored, we need to add some whitespace
                            need[option_name] += " "
                        need[option_name] += value

                elif option.startswith("-"):
                    option_name = option[1:]
                    if option_name in link_names:
                        need[option_name] = []
                    if option_name in list_values:
                        need[option_name] = []
                    else:
                        need[option_name] = ""
                else:
                    if option in link_names:
                        need[option] = []
                        if value.strip().startswith("[[") and value.strip().endswith("]]"):  # dynamic function
                            need[option].append(value)
                        else:
                            for ref_need in [i.strip() for i in re.split(";|,", value)]:
                                if ref_need not in all_needs:
                                    logger.warning(
                                        f"Provided link id {ref_need} for needextend does not exist. [needs]",
                                        type="needs",
                                        location=(current_needextend["docname"], current_needextend["lineno"]),
                                    )
                                    continue
                                need[option].append(ref_need)
                    elif option in list_values:
                        if value.strip().startswith("[[") and value.strip().endswith("]]"):  # dynamic function
                            need[option].append(value)
                        else:
                            need[option] = [i.strip() for i in re.split(";|,", value)]
                    else:
                        need[option] = value
