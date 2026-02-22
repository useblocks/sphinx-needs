from __future__ import annotations

import html
import os
import time
from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, TypedDict

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective

from sphinx_needs._jinja import render_template_string
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.diagrams_common import calculate_link
from sphinx_needs.directives.needflow._plantuml import make_entity_name
from sphinx_needs.filter_common import filter_needs_view
from sphinx_needs.logging import log_warning
from sphinx_needs.need_item import NeedItem, NeedPartItem
from sphinx_needs.roles.need_ref import value_to_string
from sphinx_needs.utils import add_doc, logger, split_need_id

if TYPE_CHECKING:
    from sphinxcontrib.plantuml import plantuml


class ProcessedDataType(TypedDict):
    art: str
    key: None | str
    arguments: dict[str, Any]


ProcessedNeedsType = dict[str, list[ProcessedDataType]]


class Needuml(nodes.General, nodes.Element):
    pass


class NeedumlDirective(SphinxDirective):
    """
    Directive to get flow charts.
    """

    has_content = True
    optional_arguments = 1
    final_argument_whitespace = True
    option_spec = {
        "align": directives.unchanged_required,
        "scale": directives.unchanged_required,
        "debug": directives.flag,
        "config": directives.unchanged_required,
        "extra": directives.unchanged_required,
        "key": directives.unchanged_required,
        "save": directives.unchanged_required,
    }

    def run(self) -> Sequence[nodes.Node]:
        env = self.env

        if self.name == "needarch":
            targetid = "needarch-{docname}-{id}".format(
                docname=env.docname, id=env.new_serialno("needarch")
            )
            is_arch = True
        else:
            targetid = "needuml-{docname}-{id}".format(
                docname=env.docname, id=env.new_serialno("needuml")
            )
            is_arch = False

        targetnode = nodes.target("", "", ids=[targetid])

        scale = self.options.get("scale", "").replace("%", "")
        align = self.options.get("align", "center")

        title = None
        if self.arguments:
            title = self.arguments[0]

        content = "\n".join(self.content)

        config_names = self.options.get("config")
        configs = []
        flow_configs = NeedsSphinxConfig(env.config).flow_configs
        if config_names:
            for config_name in config_names.split(","):
                config_name = config_name.strip()
                if config_name and config_name in flow_configs:
                    configs.append(flow_configs[config_name])

        extra_dict = {}
        extras = self.options.get("extra")
        if extras:
            extras = extras.split(",")
            for extra in extras:
                key, value = extra.split(":")
                extra_dict[key] = value

        key_name = self.options.get("key")
        if key_name == "diagram":
            raise NeedumlException(f"Needuml option key name can't be: {key_name}")

        save_path = self.options.get("save")
        plantuml_code_out_path = None
        if save_path:
            if PurePosixPath(save_path).is_absolute():
                raise NeedumlException(
                    f"Given save path: {save_path}, is not a relative posix path."
                )
            else:
                plantuml_code_out_path = save_path

        SphinxNeedsData(env).get_or_create_umls()[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "caption": title,
            "content": content,
            "scale": scale,
            "align": align,
            "config_names": config_names,
            "config": "\n".join(configs),
            "debug": "debug" in self.options,
            "extra": extra_dict,
            "key": key_name,
            "save": plantuml_code_out_path,
            "is_arch": is_arch,
            "content_calculated": "",
            "process_time": 0,
        }

        add_doc(env, env.docname)

        node = Needuml(targetid)
        self.set_source_info(node)

        return [targetnode, node]


class NeedarchDirective(NeedumlDirective):
    """
    Directive inherits from Needuml, but works only inside a need object.
    """

    def run(self) -> Sequence[nodes.Node]:
        return NeedumlDirective.run(self)


def transform_uml_to_plantuml_node(
    app: Sphinx,
    uml_content: str,
    parent_need_id: None | str,
    key: None | str,
    kwargs: dict[str, Any],
    config: str,
) -> plantuml:
    try:
        if "sphinxcontrib.plantuml" not in app.extensions:
            raise ImportError
        from sphinxcontrib.plantuml import plantuml
    except ImportError:
        error_node = nodes.error()
        para = nodes.paragraph()
        text = nodes.Text("PlantUML is not available!")
        para += text
        error_node.append(para)
        return error_node

    # Create basic uml node
    plantuml_block_text = ".. plantuml::\n\n   @startuml\n   @enduml"
    puml_node = plantuml(plantuml_block_text)

    # Add needuml specific content
    puml_node["uml"] = "@startuml\n"

    # Adding config
    if config:
        puml_node["uml"] += "\n' Config\n\n"
        puml_node["uml"] += config
        puml_node["uml"] += "\n\n"

    # jinja2uml to translate jinja statements to uml text
    (uml_content_return, _) = jinja2uml(
        app=app,
        fromdocname=None,
        uml_content=uml_content,
        parent_need_id=parent_need_id,
        key=key,
        processed_need_ids={},
        kwargs=kwargs,
    )

    puml_node["uml"] += f"\n{uml_content_return}"
    puml_node["uml"] += "\n@enduml\n"
    return puml_node


def get_debug_node_from_puml_node(puml_node: plantuml) -> nodes.container:
    if isinstance(puml_node, nodes.figure):
        data = puml_node.children[0]["uml"]  # type: ignore[index]
    data = puml_node.get("uml", "")
    data = "\n".join([html.escape(line) for line in data.split("\n")])
    debug_para = nodes.raw("", f"<pre>{data}</pre>", format="html")
    debug_container = nodes.container()
    debug_container += debug_para
    return debug_container


def jinja2uml(
    app: Sphinx,
    fromdocname: None | str,
    uml_content: str,
    parent_need_id: None | str,
    key: None | str,
    processed_need_ids: ProcessedNeedsType,
    kwargs: dict[str, Any],
    jinja_utils: JinjaFunctions | None = None,
) -> tuple[str, ProcessedNeedsType]:
    """Render Jinja template content into PlantUML syntax.

    Processes ``uml_content`` by stripping ``@startuml``/``@enduml`` markers
    and rendering the remainder as a Jinja template with access to all needs
    data and helper functions (``uml``, ``flow``, ``filter``, ``import``,
    ``ref``, ``need``).

    A single :class:`JinjaFunctions` instance is created on the first call
    and reused across recursive invocations (triggered by ``{{ uml("ID") }}``
    calls in templates) to avoid redundant object creation.

    :param app: The Sphinx application instance.
    :param fromdocname: The source document name, used for link calculation.
    :param uml_content: The raw Jinja/PlantUML template string to render.
    :param parent_need_id: The need ID that owns this diagram content,
        or ``None`` for top-level ``needuml`` directives.
    :param key: The arch key name, or ``None`` for the default ``diagram`` key.
    :param processed_need_ids: Tracks already-rendered needs to prevent
        infinite recursion in cyclic references.
    :param kwargs: Extra keyword arguments passed from ``{{ uml(...) }}``
        calls, made available as template variables.
    :param jinja_utils: An existing :class:`JinjaFunctions` instance to reuse
        across recursion.  ``None`` on the initial call (a new instance is
        created); passed automatically on recursive calls.
    :return: A tuple of the rendered PlantUML string and the updated
        processed-needs mapping.
    """
    # 1. Remove @startuml and @enduml
    uml_content = uml_content.replace("@startuml", "").replace("@enduml", "")

    # 2. Get or reuse a JinjaFunctions instance (reused across recursion)
    if jinja_utils is None:
        jinja_utils = JinjaFunctions(
            app, fromdocname, parent_need_id, processed_need_ids
        )
    else:
        # Update parent_need_id for this recursion level
        jinja_utils.set_parent_need_id(parent_need_id)

    # 3. Append need_id to processed_need_ids, so it will not been processed again
    if parent_need_id:
        jinja_utils.append_need_to_processed_needs(
            need_id=parent_need_id, art="uml", key=key, kwargs=kwargs
        )

    # 4. Get data for the jinja processing
    data: dict[str, Any] = {}
    # 4.1 Set default config to data
    data.update(**jinja_utils.needs_config.render_context)
    # 4.2 Set uml() kwargs to data and maybe overwrite default settings
    data.update(kwargs)
    # 4.3 Add needs as data (dict-like mapping), not as a function
    data["needs"] = jinja_utils.needs
    # 4.4 Add helper functions as callable context values
    # (passed via context, not as registered functions, to avoid FFI overhead)
    data["need"] = jinja_utils.need
    data["uml"] = jinja_utils.uml_from_need
    data["flow"] = jinja_utils.flow
    data["filter"] = jinja_utils.filter
    data["import"] = jinja_utils.imports
    data["ref"] = jinja_utils.ref

    # 5. Render the uml content with the fetched data.
    # new_env=True is required because template callbacks (uml, flow, etc.)
    # may call render_template_string again, and MiniJinja's Environment
    # holds a non-reentrant lock during render_str.
    uml = render_template_string(uml_content, data, autoescape=False, new_env=True)

    # 6. Get processed need ids
    processed_need_ids_return = jinja_utils.get_processed_need_ids()

    return (uml, processed_need_ids_return)


class JinjaFunctions:
    """
    Contains Jinja helper functions

    Provides access to sphinx-app and all Needs objects.
    """

    def __init__(
        self,
        app: Sphinx,
        fromdocname: None | str,
        parent_need_id: None | str,
        processed_need_ids: ProcessedNeedsType,
    ) -> None:
        self.needs = SphinxNeedsData(app.env).get_needs_view()
        self.app = app
        self.fromdocname = fromdocname
        self.parent_need_id = parent_need_id
        if parent_need_id and parent_need_id not in self.needs:
            raise NeedumlException(
                f"JinjaFunctions initialized with undefined parent_need_id: '{parent_need_id}'"
            )
        self.processed_need_ids = processed_need_ids
        self.needs_config = NeedsSphinxConfig(app.config)

    def set_parent_need_id(self, parent_need_id: None | str) -> None:
        """Update the parent need ID for a new recursion level."""
        if parent_need_id and parent_need_id not in self.needs:
            raise NeedumlException(
                f"JinjaFunctions set with undefined parent_need_id: '{parent_need_id}'"
            )
        self.parent_need_id = parent_need_id

    def need_to_processed_data(
        self, art: str, key: None | str, kwargs: dict[str, Any]
    ) -> ProcessedDataType:
        d: ProcessedDataType = {
            "art": art,
            "key": key,
            "arguments": kwargs,
        }
        return d

    def append_need_to_processed_needs(
        self, need_id: str, art: str, key: None | str, kwargs: dict[str, Any]
    ) -> None:
        data = self.need_to_processed_data(art=art, key=key, kwargs=kwargs)
        if need_id not in self.processed_need_ids:
            self.processed_need_ids[need_id] = []
        if data not in self.processed_need_ids[need_id]:
            self.processed_need_ids[need_id].append(data)

    def append_needs_to_processed_needs(
        self, processed_needs_data: ProcessedNeedsType
    ) -> None:
        for k, v in processed_needs_data.items():
            if k not in self.processed_need_ids:
                self.processed_need_ids[k] = []
            for d in v:
                if d not in self.processed_need_ids[k]:
                    self.processed_need_ids[k].append(d)

    def data_in_processed_data(
        self, need_id: str, art: str, key: str, kwargs: dict[str, Any]
    ) -> bool:
        data = self.need_to_processed_data(art=art, key=key, kwargs=kwargs)
        return (need_id in self.processed_need_ids) and (
            data in self.processed_need_ids[need_id]
        )

    def get_processed_need_ids(self) -> ProcessedNeedsType:
        return self.processed_need_ids

    def uml_from_need(self, need_id: str, key: str = "diagram", **kwargs: Any) -> str:
        if need_id not in self.needs:
            raise NeedumlException(
                f"Jinja function uml() is called with undefined need_id: '{need_id}'."
            )

        if self.data_in_processed_data(
            need_id=need_id, art="uml", key=key, kwargs=kwargs
        ):
            return ""

        need_info = self.needs[need_id]

        if key != "diagram":
            if need_info["arch"][key]:
                uml_content = need_info["arch"][key]
            else:
                raise NeedumlException(
                    f"Option key name: {key} does not exist in need {need_id}."
                )
        else:
            if "diagram" in need_info["arch"] and need_info["arch"]["diagram"]:
                uml_content = need_info["arch"]["diagram"]
            else:
                return self.flow(need_id)

        # We need to re-render the fetched content, as it may contain also Jinja statements.
        # Reuse this JinjaFunctions instance to avoid repeated object creation.
        # Save and restore parent_need_id since jinja2uml will mutate it.
        saved_parent_need_id = self.parent_need_id
        try:
            (uml, processed_need_ids_return) = jinja2uml(
                app=self.app,
                fromdocname=self.fromdocname,
                uml_content=uml_content,
                parent_need_id=need_id,
                key=key,
                processed_need_ids=self.processed_need_ids,
                kwargs=kwargs,
                jinja_utils=self,
            )
        finally:
            self.parent_need_id = saved_parent_need_id

        # Append processed needs to current proccessing
        self.append_needs_to_processed_needs(processed_need_ids_return)

        return uml

    def flow(self, need_id: str) -> str:
        if need_id not in self.needs:
            raise NeedumlException(
                f"Jinja function flow is called with undefined need_id: '{need_id}'."
            )

        if self.data_in_processed_data(need_id=need_id, art="flow", key="", kwargs={}):
            return ""

        # append need_id to processed_need_ids, so it will not been processed again
        self.append_need_to_processed_needs(
            need_id=need_id, art="flow", key="", kwargs={}
        )

        need_info = self.needs[need_id]
        link = calculate_link(self.app, need_info, self.fromdocname)

        node_text = render_template_string(
            self.needs_config.diagram_template,
            {**need_info, **self.needs_config.render_context},
            autoescape=False,
        )

        need_uml = '{style} "{node_text}" as {id} [[{link}]] #{color}'.format(
            id=make_entity_name(need_id),
            node_text=node_text,
            link=link,
            color=need_info["type_color"].replace("#", ""),
            style=need_info["type_style"],
        )

        return need_uml

    def ref(
        self, need_id: str, option: None | str = None, text: None | str = None
    ) -> str:
        need_id_main, need_id_part = split_need_id(need_id)

        if need_id_main not in self.needs:
            raise NeedumlException(
                f"Jinja function ref is called with undefined need_id: '{need_id_main}'."
            )
        if (option and text) and (not option and not text):
            raise NeedumlException(
                "Jinja function ref requires exactly one entry 'option' or 'text'"
            )

        need = self.needs[need_id_main]

        need_or_part: NeedItem | NeedPartItem

        if need_id_part:
            if (part := need.get_part_item(need_id_part)) is None:
                raise NeedumlException(
                    f"Jinja function ref is called with undefined need_id part: '{need_id}'."
                )
            need_or_part = part
        else:
            need_or_part = need

        link = calculate_link(self.app, need_or_part, self.fromdocname)
        link_text = (
            value_to_string(need_or_part.get(option, "")) if option else str(text or "")
        ).strip()

        return f"[[{link}{' ' if link_text else ''}{link_text}]]"

    def filter(self, filter_string: str) -> list[NeedItem]:
        """
        Return a list of found needs that pass the given filter string.
        """
        return filter_needs_view(
            self.needs, self.needs_config, filter_string=filter_string
        )

    def imports(self, *args: str) -> str:
        if not self.parent_need_id:
            raise NeedumlException(
                "Jinja function 'import()' is not supported in needuml directive."
            )
        # gets all need ids from need links and wrap into jinja function uml()
        need_info = self.needs[self.parent_need_id]
        uml_ids = []
        for option_name in args:
            # check if link option_name exists in current need object
            if option_value := need_info.get(option_name):
                try:
                    iterable_value = list(option_value)
                except TypeError:
                    raise NeedumlException(
                        f"Option value for {option_name!r} is not iterable."
                    )
                for id in iterable_value:
                    uml_ids.append(id)
        umls = ""
        if uml_ids:
            for uml_id in uml_ids:
                local_uml_from_need = self.uml_from_need(uml_id)
                if not local_uml_from_need.endswith("\n"):
                    local_uml_from_need += "\n"
                umls += local_uml_from_need
        return umls

    def need(self) -> NeedItem:
        if not self.parent_need_id:
            raise NeedumlException(
                "Jinja function 'need()' is not supported in needuml directive."
            )
        return self.needs[self.parent_need_id]


def is_element_of_need(node: nodes.Element) -> str:
    """
    Checks if a node is part of a need in the doctree.

    It does not search for Need-nodes, as they got transfomred already to docutils nodes.
    So tries to find a Table-Node, which has "need" in classes.

    :param node: docutils node object
    :returns: Need ID is string or an empty string

    """
    is_element_of = ""
    while not is_element_of:
        if isinstance(node, nodes.table) and "need" in node["classes"]:
            is_element_of = node["ids"][0]
            break
        else:
            if not node.parent:
                break
            node = node.parent

    return is_element_of


@measure_time("needuml")
def process_needuml(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    env = app.env
    needs_config = NeedsSphinxConfig(app.config)
    uml_data = SphinxNeedsData(env).get_or_create_umls()

    # for node in doctree.findall(Needuml):
    for node in found_nodes:
        id = node.attributes["ids"][0]
        current_needuml = uml_data[id]

        parent_need_id = None
        # Check if current needuml is needarch
        if current_needuml["is_arch"]:
            # Check if needarch is only used inside a need
            parent_need_id = is_element_of_need(node)
            if not parent_need_id:
                raise NeedArchException(
                    "Directive needarch can only be used inside a need."
                )
        content = []

        # Adding config
        config = current_needuml["config"]
        if config and len(config) >= 3:
            # Remove all empty lines
            config = "\n".join(
                [line.strip() for line in config.split("\n") if line.strip()]
            )

        start = time.perf_counter()
        puml_node = transform_uml_to_plantuml_node(
            app=app,
            uml_content=current_needuml["content"],
            parent_need_id=parent_need_id,
            key=current_needuml["key"],
            kwargs=current_needuml["extra"],
            config=config,
        )
        if "uml" not in puml_node:
            # An error node was returned
            node.replace_self(puml_node)
            continue

        duration = time.perf_counter() - start

        if (
            needs_config.uml_process_max_time is not None
            and duration > needs_config.uml_process_max_time
        ):
            log_warning(
                logger,
                f"Uml processing took {duration:.3f}s, which is longer than the configured maximum of {needs_config.uml_process_max_time}s.",
                "uml",
                location=node,
            )

        # Add source origin
        puml_node.line = current_needuml["lineno"]
        puml_node.source = env.doc2path(current_needuml["docname"])

        # Add calculated needuml content
        current_needuml["content_calculated"] = puml_node["uml"]
        current_needuml["process_time"] = duration

        try:
            scale = int(current_needuml["scale"])
        except ValueError:
            scale = 100
        # if scale != 100:
        puml_node["scale"] = scale

        if current_needuml["align"]:
            puml_node["align"] = current_needuml["align"]
        else:
            puml_node["align"] = "center"

        puml_node["incdir"] = os.path.dirname(current_needuml["docname"])
        puml_node["filename"] = os.path.split(current_needuml["docname"])[
            1
        ]  # Needed for plantuml >= 0.9

        content.append(puml_node)

        if current_needuml["caption"]:
            title_text = current_needuml["caption"]
            title = nodes.title(title_text, "", nodes.Text(title_text))
            content.insert(0, title)

        if current_needuml["debug"]:
            content += get_debug_node_from_puml_node(puml_node)

        node.replace_self(content)


class NeedumlException(BaseException):
    """Errors during Needuml handling."""


class NeedArchException(BaseException):
    """Errors during Needarch handling."""
