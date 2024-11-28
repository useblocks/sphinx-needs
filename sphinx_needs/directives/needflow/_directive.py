from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.ext.graphviz import (
    figure_wrapper,
)

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import (
    GraphvizStyleType,
    NeedsFlowType,
)
from sphinx_needs.debug import measure_time
from sphinx_needs.filter_common import FilterBase
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.utils import (
    add_doc,
    get_scale,
    split_link_types,
)

LOGGER = get_logger(__name__)

if TYPE_CHECKING:
    from typing_extensions import Unpack


class NeedflowDirective(FilterBase):
    """
    Directive to get flow charts.
    """

    optional_arguments = 1  # the caption
    final_argument_whitespace = True
    option_spec = {
        "engine": lambda c: directives.choice(c, ("graphviz", "plantuml")),
        # basic options
        "alt": directives.unchanged,
        "scale": directives.unchanged_required,
        "align": lambda c: directives.choice(c, ("left", "center", "right")),
        "class": directives.class_option,
        "name": directives.unchanged,
        # initial filtering
        "root_id": directives.unchanged_required,
        "root_direction": lambda c: directives.choice(
            c, ("both", "incoming", "outgoing")
        ),
        "root_depth": directives.nonnegative_int,
        "link_types": directives.unchanged_required,
        # debug; render the graph code in the document
        "debug": directives.flag,
        # formatting
        "highlight": directives.unchanged_required,
        "border_color": directives.unchanged_required,
        "show_legend": directives.flag,
        "show_filters": directives.flag,
        "show_link_names": directives.flag,
        "config": directives.unchanged_required,
    }

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    @measure_time("needflow")
    def run(self) -> Sequence[nodes.Node]:
        needs_config = NeedsSphinxConfig(self.env.config)
        location = (self.env.docname, self.lineno)

        id = self.env.new_serialno("needflow")
        targetid = f"needflow-{self.env.docname}-{id}"

        all_link_types = ",".join(x["option"] for x in needs_config.extra_links)
        link_types = split_link_types(
            self.options.get("link_types", all_link_types), location
        )

        engine = self.options.get("engine", needs_config.flow_engine)
        assert engine in ["graphviz", "plantuml"], f"Unknown needflow engine '{engine}'"

        config_names: str = self.options.get("config", "")
        config = ""
        graphviz_style: GraphvizStyleType = {}
        if engine == "plantuml":
            _configs = []
            for config_name in config_names.split(","):
                config_name = config_name.strip()
                if config_name and config_name in needs_config.flow_configs:
                    _configs.append(needs_config.flow_configs[config_name])
                elif config_name:
                    log_warning(
                        LOGGER,
                        f"config key {config_name!r} not in 'need_flows_configs'",
                        "needflow",
                        location=self.get_location(),
                    )
            config = "\n".join(_configs)
        else:
            config_names = config_names if config_names else "default"
            for config_name in config_names.split(","):
                config_name = config_name.strip()
                try:
                    if config_name and config_name in needs_config.graphviz_styles:
                        for key, value in needs_config.graphviz_styles[
                            config_name
                        ].items():
                            if key in graphviz_style:
                                graphviz_style[key].update(value)  # type: ignore[literal-required]
                            else:
                                graphviz_style[key] = value  # type: ignore[literal-required]
                    elif config_name:
                        log_warning(
                            LOGGER,
                            f"config key {config_name!r} not in 'needs_graphviz_styles'",
                            "needflow",
                            location=self.get_location(),
                        )
                except Exception as err:
                    if config_name:
                        log_warning(
                            LOGGER,
                            f"malformed config {config_name!r} in 'needs_graphviz_styles': {err}",
                            "needflow",
                            location=self.get_location(),
                        )

        add_doc(self.env, self.env.docname)

        attributes: NeedsFlowType = {
            "docname": self.env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "root_id": self.options.get("root_id"),
            "root_direction": self.options.get("root_direction", "all"),
            "root_depth": self.options.get("root_depth", None),
            "show_legend": "show_legend" in self.options,
            "show_filters": "show_filters" in self.options,
            "show_link_names": "show_link_names" in self.options,
            "link_types": link_types,
            "config_names": config_names,
            "config": config,
            "graphviz_style": graphviz_style,
            "scale": get_scale(self.options, self.get_location()),
            "highlight": self.options.get("highlight", ""),
            "border_color": self.options.get("border_color", None),
            "align": self.options.get("align", "center"),
            "debug": "debug" in self.options,
            "caption": self.arguments[0] if self.arguments else None,
            "classes": self.options.get("class", []),
            "alt": self.options.get("alt", ""),
            **self.collect_filter_attributes(),
        }

        # TODO currently the engines handle captions differently
        # I think plantuml should use the same "standard" approach as graphviz

        if engine == "plantuml":
            pnode = NeedflowPlantuml("", **attributes)
            self.set_source_info(pnode)
            self.add_name(pnode)
            return [nodes.target("", "", ids=[targetid]), pnode]

        elif engine == "graphviz":
            gnode = NeedflowGraphiz("", **attributes)
            self.set_source_info(gnode)

            if not self.arguments:
                figure = nodes.figure("", gnode)
                if "align" in gnode:
                    figure["align"] = gnode.attributes.pop("align")  # type: ignore[misc]
                figure["ids"] = [targetid]
                self.add_name(gnode)
                return [figure]
            else:
                figure = figure_wrapper(self, gnode, self.arguments[0])  # type: ignore[arg-type]
                figure["ids"] = [targetid]
                self.add_name(figure)
                return [figure]

        raise ValueError(f"Unknown needflow engine '{engine}'")


class NeedflowPlantuml(nodes.General, nodes.Element):
    if TYPE_CHECKING:

        def __init__(
            self,
            rawsource: str,
            /,
            **kwargs: Unpack[NeedsFlowType],
        ) -> None: ...

        attributes: NeedsFlowType


class NeedflowGraphiz(nodes.General, nodes.Element):
    if TYPE_CHECKING:

        def __init__(
            self,
            rawsource: str,
            /,
            **kwargs: Unpack[NeedsFlowType],
        ) -> None: ...

        attributes: NeedsFlowType
