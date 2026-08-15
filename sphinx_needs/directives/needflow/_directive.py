from __future__ import annotations

from collections.abc import Mapping, Sequence
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
    SphinxNeedsData,
)
from sphinx_needs.debug import measure_time
from sphinx_needs.directives.needflow._options import (
    direction_option,
    graphviz_config_direction,
    legend_option,
    link_labels_option,
    plantuml_config_direction,
    resolve_engine,
)
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
        # portable formatting vocabulary
        "direction": direction_option,
        "link_labels": link_labels_option,
        "legend": legend_option,
        "styles": directives.unchanged_required,
        # formatting
        "highlight": directives.unchanged_required,
        "border_color": directives.unchanged_required,
        "show_legend": directives.flag,
        "show_filters": directives.flag,
        "show_link_names": directives.flag,
        "config": directives.unchanged_required,
        "engine_config": directives.unchanged_required,
        "max_items": directives.nonnegative_int,
        # ubCode compatibility: accepted and ignored by Sphinx-Needs.
        "cypher": directives.unchanged,
        "width": directives.unchanged,
        "height": directives.unchanged,
    }

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def _warn_deprecated(self, option: str, replacement: str) -> None:
        """Report that a used option has a replacement, without withdrawing it.

        A deprecated option keeps being honoured -- indefinitely, as every other
        Sphinx-Needs deprecation is -- so the warning fires only when the option is
        actually used, and never for a document that has already moved on.

        :param option: The name of the deprecated option.
        :param replacement: What to say the author should write instead.
        """
        log_warning(
            LOGGER,
            f"The 'needflow' {option!r} option is deprecated. {replacement}",
            "deprecated",
            location=self.get_location(),
        )

    def _engine_config_entry(
        self, name: str, engine: str, needs_config: NeedsSphinxConfig
    ) -> object | None:
        """Look one engine config name up, in the new registry and then the old one.

        The registries are a rename, not a redesign: ``needs_flow_engine_config`` is
        the engine-keyed home of what ``needs_flow_configs`` and
        ``needs_graphviz_styles`` hold today, and existing values transfer verbatim.
        The old ones are therefore still read, so that no project has to move its
        blobs in order to upgrade.

        :param name: The name the directive selected.
        :param engine: The engine the diagram is drawn with.
        :param needs_config: The Sphinx-Needs configuration.
        :return: The entry, or ``None`` if no registry holds that name.
        """
        registry = needs_config.flow_engine_config.get(engine)
        if isinstance(registry, Mapping) and name in registry:
            entry: object = registry[name]
            return entry
        legacy = (
            needs_config.flow_configs
            if engine == "plantuml"
            else needs_config.graphviz_styles
        )
        if isinstance(legacy, Mapping) and name in legacy:
            return legacy[name]
        return None

    def _unknown_engine_config(self, name: str, engine: str) -> None:
        """Report an engine config name that no registry holds.

        :param name: The name the directive selected.
        :param engine: The engine the diagram is drawn with.
        """
        legacy = (
            "needs_flow_configs" if engine == "plantuml" else "needs_graphviz_styles"
        )
        log_warning(
            LOGGER,
            f"config key {name!r} not in 'needs_flow_engine_config[{engine}]' "
            f"or {legacy!r}",
            "needflow",
            location=self.get_location(),
        )

    def _plantuml_engine_config(
        self, config_names: str, needs_config: NeedsSphinxConfig
    ) -> str:
        """Resolve the named plantuml customisations into one preamble.

        :param config_names: The comma separated names the directive selected.
        :param needs_config: The Sphinx-Needs configuration.
        :return: The preamble text, empty if nothing was selected.
        """
        blobs: list[str] = []
        for raw in config_names.split(","):
            if not (name := raw.strip()):
                continue
            entry = self._engine_config_entry(name, "plantuml", needs_config)
            if entry is None:
                self._unknown_engine_config(name, "plantuml")
            else:
                blobs.append(str(entry))
        return "\n".join(blobs)

    def _graphviz_engine_config(
        self, config_names: str, needs_config: NeedsSphinxConfig
    ) -> GraphvizStyleType:
        """Resolve the named graphviz customisations into one style mapping.

        The result is validated here rather than trusted downstream: a value that is
        not a mapping of attributes used to reach the emitter and fail the whole build
        with ``'str' object has no attribute 'items'``. Bad configuration is worth a
        warning, never a broken build, so the offending entry is dropped and the
        diagram is drawn without it.

        :param config_names: The comma separated names the directive selected.
        :param needs_config: The Sphinx-Needs configuration.
        :return: The merged style, only ever holding mappings of attributes.
        """
        style: GraphvizStyleType = {}
        for raw in config_names.split(","):
            if not (name := raw.strip()):
                continue
            entry = self._engine_config_entry(name, "graphviz", needs_config)
            if entry is None:
                self._unknown_engine_config(name, "graphviz")
                continue
            if not isinstance(entry, Mapping):
                log_warning(
                    LOGGER,
                    f"malformed engine config {name!r} for the graphviz engine: "
                    f"must be a mapping of element types to attributes, "
                    f"but is {type(entry).__name__}",
                    "needflow",
                    location=self.get_location(),
                )
                continue
            for key, value in entry.items():
                if not isinstance(value, Mapping):
                    log_warning(
                        LOGGER,
                        f"malformed engine config {name!r} for the graphviz engine: "
                        f"{key!r} must be a mapping of attributes, "
                        f"but is {type(value).__name__}",
                        "needflow",
                        location=self.get_location(),
                    )
                    continue
                if key in style:
                    style[key].update(value)  # type: ignore[literal-required]
                else:
                    style[key] = dict(value)  # type: ignore[literal-required]
        return style

    @measure_time("needflow")
    def run(self) -> Sequence[nodes.Node]:
        needs_config = NeedsSphinxConfig(self.env.config)
        location = (self.env.docname, self.lineno)

        if "show_link_names" in self.options:
            self._warn_deprecated(
                "show_link_names", "Please use ':link_labels: outgoing' instead."
            )
        if "show_legend" in self.options:
            self._warn_deprecated(
                "show_legend",
                "Please use ':legend: types' instead, which draws the same legend on "
                "every engine, as a table beside the diagram.",
            )
        if "highlight" in self.options:
            self._warn_deprecated(
                "highlight",
                "Please use ':styles: [<filter>]:highlight' instead, "
                "which draws the same outline.",
            )
        if "border_color" in self.options:
            self._warn_deprecated(
                "border_color",
                "Please use ':styles:' with a class setting 'border' instead.",
            )
        if "scale" in self.options:
            # deprecated without a like-for-like replacement: it sizes a raster image,
            # which the graphviz engine has always silently ignored
            self._warn_deprecated(
                "scale",
                "It sizes a raster image, so it has no effect on every engine. "
                "Please use ':width:' / ':height:' instead.",
            )

        id = self.env.new_serialno("needflow")
        targetid = f"needflow-{self.env.docname}-{id}"

        needs_schema = SphinxNeedsData(self.env).get_schema()
        all_link_types = ",".join(link.name for link in needs_schema.iter_link_fields())
        link_types = split_link_types(
            self.options.get("link_types", all_link_types), location
        )

        engine = resolve_engine(
            self.options.get("engine"),
            needs_config.flow_engine,
            location=self.get_location(),
        )

        if "config" in self.options:
            self._warn_deprecated(
                "config",
                "Please use ':engine_config:' instead, which reads the same "
                "configuration and any 'needs_flow_engine_config' entries.",
            )
        config_names: str = self.options.get(
            "engine_config", self.options.get("config", "")
        )
        config = ""
        graphviz_style: GraphvizStyleType = {}
        if engine == "plantuml":
            config = self._plantuml_engine_config(config_names, needs_config)
        else:
            # note a graphviz needflow without an engine config silently gets the
            # "default" style, so it is never unstyled the way a plantuml one is, and
            # naming any config replaces that default rather than adding to it;
            # it is kept as is
            config_names = config_names if config_names else "default"
            graphviz_style = self._graphviz_engine_config(config_names, needs_config)

        # the engine is still known here, so the direction a config blob sets is
        # detected now and the model is spared having to know one engine from another
        config_direction = (
            plantuml_config_direction(config)
            if engine == "plantuml"
            else graphviz_config_direction(graphviz_style)
        )

        add_doc(self.env, self.env.docname)

        attributes: NeedsFlowType = {
            "docname": self.env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "root_id": self.options.get("root_id"),
            "root_direction": self.options.get("root_direction", "both"),
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
            # None means the option was not given, so that an engine can tell it apart
            # from an explicitly empty value, i.e. a deliberately undescribed diagram
            "alt": self.options.get("alt"),
            "max_items": self.options.get("max_items"),
            # None means the option was not given, so that the configuration is only
            # consulted when the author did not say (the `max_items` precedent)
            "direction": self.options.get("direction"),
            "config_direction": config_direction,
            "link_labels": self.options.get("link_labels"),
            "legend": self.options.get("legend"),
            "styles": self.options.get("styles", ""),
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
