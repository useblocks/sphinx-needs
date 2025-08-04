from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from docutils import nodes
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api.need import _split_list_with_dyn_funcs
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import ExtendType, NeedsExtendType, NeedsMutable, SphinxNeedsData
from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs.filter_common import filter_needs_mutable
from sphinx_needs.logging import WarningSubTypes, get_logger, log_warning
from sphinx_needs.utils import DummyOptionSpec, add_doc, coersce_to_boolean

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

    option_spec: Final[DummyOptionSpec] = DummyOptionSpec()

    options: dict[str, str | None]

    def _log_warning(
        self, message: str, code: WarningSubTypes = "needextend", /
    ) -> None:
        """Log a warning with the given message and code."""
        log_warning(
            logger,
            message,
            code,
            location=self.get_location(),
        )

    def run(self) -> Sequence[nodes.Node]:
        # throughout this function, we gradually pop values from self.options
        # so that we can warn about unknown options at the end
        options: dict[str, str | None] = self.options

        needs_config = NeedsSphinxConfig(self.env.app.config)

        try:
            # override global needextend_strict if user set it in the directive
            strict = (
                coersce_to_boolean(options.pop("strict"))
                if "strict" in options
                else needs_config.needextend_strict
            )
        except ValueError as err:
            self._log_warning(f"Invalid value for 'strict' option: {err}")
            return []

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
            self._log_warning("Empty ID/filter argument in needextend directive.")
            return []

        modifications: list[tuple[str, ExtendType, None | str | bool]] = []
        link_keys = {li["option"] for li in needs_config.extra_links}

        while options:
            key, value = options.popitem()

            if key.startswith("-"):
                key = key[1:]
                etype = ExtendType.DELETE
                # TODO check key is ok and value was None
                modifications.append((key, etype, None))
                continue

            if key.startswith("+"):
                key = key[1:]
                etype = ExtendType.APPEND
            else:
                etype = ExtendType.REPLACE
            coersced_value: None | str | bool = None
            try:
                match key:
                    case "collapse" | "hide":
                        coersced_value = coersce_to_boolean(value)
                    case "status" | "tags" | "style" | "layout" | "constraints":
                        assert value, f"'{etype}{key}' must not be empty"
                        coersced_value = value
                    case key if key in needs_config.extra_options:
                        coersced_value = value or ""
                    case key if key in link_keys:
                        coersced_value = value or ""
                    case _:
                        self._log_warning(f"Unknown option '{etype}{key}'")
            except (AssertionError, ValueError) as err:
                self._log_warning(f"Invalid value for '{etype}{key}' option: {err}")
                return []
            modifications.append((key, etype, coersced_value))

        id = self.env.new_serialno("needextend")
        targetid = f"needextend-{self.env.docname}-{id}"
        targetnode = nodes.target("", "", ids=[targetid])

        data = SphinxNeedsData(self.env).get_or_create_extends()
        data[targetid] = {
            "docname": self.env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "filter": extend_filter,
            "filter_is_id": filter_is_id,
            "modifications": modifications,
            "strict": strict,
        }

        add_doc(self.env, self.env.docname)

        node = Needextend("")
        self.set_source_info(node)

        return [targetnode, node]


def extend_needs_data(
    all_needs: NeedsMutable,
    extends: dict[str, NeedsExtendType],
    needs_config: NeedsSphinxConfig,
) -> None:
    """Use data gathered from needextend directives to modify fields of existing needs."""

    list_values = ["tags"] + [x["option"] for x in needs_config.extra_links]
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

            for option_name, etype, value in current_needextend["modifications"]:
                if etype == ExtendType.APPEND:
                    if option_name in link_names:
                        assert not isinstance(value, bool)
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
                        assert not isinstance(value, bool)
                        for item, _ in _split_list_with_dyn_funcs(value, location):
                            if item not in need[option_name]:
                                need[option_name].append(item)
                    else:
                        if need[option_name]:
                            # If content is already stored, we need to add some whitespace
                            need[option_name] += " "
                        need[option_name] += value

                elif etype == ExtendType.DELETE:
                    if option_name in link_names:
                        need[option_name] = []
                    if option_name in list_values:
                        need[option_name] = []
                    else:
                        need[option_name] = ""
                elif etype == ExtendType.REPLACE:
                    if option_name in link_names:
                        need[option_name] = []
                        assert not isinstance(value, bool)
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
                            need[option_name].append(item)
                    elif option_name in list_values:
                        assert not isinstance(value, bool)
                        for item, _ in _split_list_with_dyn_funcs(value, location):
                            need[option_name].append(item)
                    else:
                        need[option_name] = value
                else:
                    raise ValueError(f"Unknown extend type {etype} for {option_name}")
