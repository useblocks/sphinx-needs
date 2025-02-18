from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Callable

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api.exceptions import NeedsInvalidFilter
from sphinx_needs.api.need import _split_list_with_dyn_funcs
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsExtendType, NeedsMutable, SphinxNeedsData
from sphinx_needs.filter_common import filter_needs_mutable
from sphinx_needs.logging import get_logger, log_warning
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

    option_spec: dict[str, Callable[[str], Any]] = {
        "strict": directives.unchanged_required,
    }

    def run(self) -> Sequence[nodes.Node]:
        env = self.env

        needs_config = NeedsSphinxConfig(self.env.app.config)
        strict = needs_config.needextend_strict
        strict_option: str = self.options.get("strict", "").upper()
        if strict_option == "TRUE":
            strict = True
        elif strict_option == "FALSE":
            strict = False

        modifications = self.options.copy()
        modifications.pop("strict", None)

        extend_filter = (self.arguments[0] if self.arguments else "").strip()
        if extend_filter.startswith("<") and extend_filter.endswith(">"):
            filter_is_id = True
            extend_filter = extend_filter[1:-1]
        elif extend_filter.startswith('"') and extend_filter.endswith('"'):
            filter_is_id = False
            extend_filter = extend_filter[1:-1]
        elif len(extend_filter.split()) == 1:
            filter_is_id = True
        else:
            filter_is_id = False

        if not extend_filter:
            log_warning(
                logger,
                "Empty ID/filter argument in needextend directive.",
                "needextend",
                location=self.get_location(),
            )
            return []

        id = env.new_serialno("needextend")
        targetid = f"needextend-{env.docname}-{id}"
        targetnode = nodes.target("", "", ids=[targetid])

        data = SphinxNeedsData(env).get_or_create_extends()
        data[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "filter": extend_filter,
            "filter_is_id": filter_is_id,
            "modifications": modifications,
            "strict": strict,
        }

        add_doc(env, env.docname)

        node = Needextend("")
        self.set_source_info(node)

        return [targetnode, node]


def extend_needs_data(
    all_needs: NeedsMutable,
    extends: dict[str, NeedsExtendType],
    needs_config: NeedsSphinxConfig,
) -> None:
    """Use data gathered from needextend directives to modify fields of existing needs."""

    list_values = ["tags", "links"] + [x["option"] for x in needs_config.extra_links]
    link_names = [x["option"] for x in needs_config.extra_links]

    for current_needextend in extends.values():
        need_filter = current_needextend["filter"]
        location = (current_needextend["docname"], current_needextend["lineno"])
        if current_needextend["filter_is_id"]:
            try:
                found_needs = [all_needs[need_filter]]
            except KeyError:
                error = f"Provided id {need_filter!r} for needextend does not exist."
                if current_needextend["strict"]:
                    raise NeedsInvalidFilter(error)
                else:
                    log_warning(logger, error, "needextend", location=location)
                continue
        else:
            try:
                found_needs = filter_needs_mutable(
                    all_needs,
                    needs_config,
                    need_filter,
                    location=location,
                    origin_docname=current_needextend["docname"],
                )
            except Exception as e:
                log_warning(
                    logger,
                    f"Invalid filter {need_filter!r}: {e}",
                    "needextend",
                    location=location,
                )
                continue

        for found_need in found_needs:
            # Work in the stored needs, not on the search result
            need = all_needs[found_need["id"]]
            need["is_modified"] = True
            need["modifications"] += 1

            location = (
                current_needextend["docname"],
                current_needextend["lineno"],
            )

            for option, value in current_needextend["modifications"].items():
                if option.startswith("+"):
                    option_name = option[1:]
                    if option_name in link_names:
                        for item, has_function in _split_list_with_dyn_funcs(
                            value, location
                        ):
                            if (not has_function) and (item not in all_needs):
                                log_warning(
                                    logger,
                                    f"Provided link id {item} for needextend does not exist.",
                                    "needextend",
                                    location=location,
                                )
                                continue
                            if item not in need[option_name]:
                                need[option_name].append(item)
                    elif option_name in list_values:
                        for item, _ in _split_list_with_dyn_funcs(value, location):
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
                        for item, has_function in _split_list_with_dyn_funcs(
                            value, location
                        ):
                            if (not has_function) and (item not in all_needs):
                                log_warning(
                                    logger,
                                    f"Provided link id {item} for needextend does not exist.",
                                    "needextend",
                                    location=location,
                                )
                                continue
                            need[option].append(item)
                    elif option in list_values:
                        for item, _ in _split_list_with_dyn_funcs(value, location):
                            need[option].append(item)
                    else:
                        need[option] = value
