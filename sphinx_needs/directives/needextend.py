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
from sphinx_needs.utils import DummyOptionSpec, add_doc, coerce_to_boolean

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
                coerce_to_boolean(options.pop("strict"))
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

        modifications: list[
            tuple[str, ExtendType, str | bool | list[tuple[str, bool]]]
        ] = []
        link_keys = {li["option"] for li in needs_config.extra_links}

        while options:
            key, value = options.popitem()

            if key.startswith("-"):
                key = key[1:]
                etype = ExtendType.DELETE
                if value is not None:
                    self._log_warning(
                        f"delete option '{etype.value}{key}' should not have a value."
                    )
                match key:
                    case "collapse" | "hide":
                        modifications.append((key, etype, False))
                    case "status" | "style" | "layout":
                        modifications.append((key, etype, ""))
                    case key if key in needs_config.extra_options:
                        modifications.append((key, etype, ""))
                    case key if key in link_keys or key in ("constraints", "tags"):
                        modifications.append((key, etype, []))
                    case _:
                        self._log_warning(f"Unknown option '{etype.value}{key}'")
            else:
                if key.startswith("+"):
                    key = key[1:]
                    etype = ExtendType.APPEND
                else:
                    etype = ExtendType.REPLACE

                try:
                    match key:
                        case "collapse" | "hide":
                            if etype == ExtendType.APPEND:
                                self._log_warning(
                                    f"Cannot append to a boolean with '{etype.value}{key}', use '{key}' instead."
                                )
                            else:
                                modifications.append(
                                    (key, etype, coerce_to_boolean(value))
                                )
                        case "status" | "style" | "layout":
                            assert value, f"'{etype.value}{key}' must not be empty"
                            modifications.append((key, etype, value))
                        case key if key in needs_config.extra_options:
                            modifications.append((key, etype, value or ""))
                        case key if key in link_keys or key in ("constraints", "tags"):
                            modifications.append(
                                (
                                    key,
                                    etype,
                                    list(
                                        _split_list_with_dyn_funcs(
                                            value, self.get_source_info()
                                        )
                                    ),
                                )
                            )
                        case _:
                            self._log_warning(f"Unknown option '{etype.value}{key}'")
                except ValueError as err:
                    self._log_warning(
                        f"Invalid value for '{etype.value}{key}' option: {err}"
                    )

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

    link_names = {x["option"] for x in needs_config.extra_links}

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
                match etype:
                    case ExtendType.APPEND:
                        match value:
                            case str():
                                if need[option_name]:
                                    # If content is already stored, we add a space between the existing content and the new one
                                    need[option_name] += " "
                                need[option_name] += value
                            case list() if option_name in link_names:
                                for item, has_df in value:
                                    if not has_df and item not in all_needs:
                                        log_warning(
                                            logger,
                                            f"Provided link id '{item}' for needextend option '{etype.value}{option_name}' does not exist.",
                                            "needextend",
                                            location=location,
                                        )
                                need[option_name].extend(
                                    (
                                        item
                                        for item, has_df in value
                                        if item not in need[option_name]
                                        and (has_df or item in all_needs)
                                    )
                                )
                            case list():
                                need[option_name].extend(
                                    [
                                        item
                                        for item, _ in value
                                        if item not in need[option_name]
                                    ]
                                )
                            case other:
                                raise ValueError(
                                    f"Cannot append to {type(other)} value for {option_name}"
                                )
                    case ExtendType.REPLACE | ExtendType.DELETE:
                        match value:
                            case list() if option_name in link_names:
                                for item, has_df in value:
                                    if not has_df and item not in all_needs:
                                        log_warning(
                                            logger,
                                            f"Provided link id '{item}' for needextend option '{etype.value}{option_name}' does not exist.",
                                            "needextend",
                                            location=location,
                                        )
                                need[option_name] = [
                                    item
                                    for item, has_df in value
                                    if (has_df or item in all_needs)
                                ]
                            case list():
                                need[option_name] = [item for item, _ in value]
                            case _:
                                need[option_name] = value
                    case other:
                        raise ValueError(
                            f"Unknown extend type {other} for {option_name}"
                        )
