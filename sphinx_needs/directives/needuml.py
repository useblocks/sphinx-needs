from __future__ import annotations

import html
import os
from typing import TYPE_CHECKING, Any, Dict, List, Sequence, TypedDict

from docutils import nodes
from docutils.parsers.rst import directives
from jinja2 import BaseLoader, Environment, Template
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType, SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.diagrams_common import calculate_link
from sphinx_needs.directives.needflow import make_entity_name
from sphinx_needs.filter_common import filter_needs
from sphinx_needs.utils import add_doc

if TYPE_CHECKING:
    from sphinxcontrib.plantuml import plantuml


class ProcessedDataType(TypedDict):
    art: str
    key: None | str
    arguments: dict[str, Any]


ProcessedNeedsType = Dict[str, List[ProcessedDataType]]


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
            if os.path.isabs(save_path):
                raise NeedumlException(
                    f"Given save path: {save_path}, is not a relative path."
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
        }

        add_doc(env, env.docname)

        return [targetnode] + [Needuml(targetid)]


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
        if "sphinxcontrib.plantuml" not in app.config.extensions:
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
) -> tuple[str, ProcessedNeedsType]:
    # Let's render jinja templates with uml content template to 'plantuml syntax' uml
    # 1. Remove @startuml and @enduml
    uml_content = uml_content.replace("@startuml", "").replace("@enduml", "")

    # 2. Prepare jinja template
    mem_template = Environment(loader=BaseLoader()).from_string(uml_content)

    # 3. Get a new instance of Jinja Helper Functions
    jinja_utils = JinjaFunctions(app, fromdocname, parent_need_id, processed_need_ids)

    # 4. Append need_id to processed_need_ids, so it will not been processed again
    if parent_need_id:
        jinja_utils.append_need_to_processed_needs(
            need_id=parent_need_id, art="uml", key=key, kwargs=kwargs
        )

    # 5. Get data for the jinja processing
    data: dict[str, Any] = {}
    # 5.1 Set default config to data
    data.update(**NeedsSphinxConfig(app.config).render_context)
    # 5.2 Set uml() kwargs to data and maybe overwrite default settings
    data.update(kwargs)
    # 5.3 Make the helpers available during rendering and overwrite maybe wrongly default and uml() kwargs settings
    data.update(
        {
            "needs": jinja_utils.needs,
            "need": jinja_utils.need,
            "uml": jinja_utils.uml_from_need,
            "flow": jinja_utils.flow,
            "filter": jinja_utils.filter,
            "import": jinja_utils.imports,
            "ref": jinja_utils.ref,
        }
    )

    # 6. Render the uml content with the fetched data
    uml = mem_template.render(**data)

    # 7. Get processed need ids
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
        self.needs = SphinxNeedsData(app.env).get_or_create_needs()
        self.app = app
        self.fromdocname = fromdocname
        self.parent_need_id = parent_need_id
        if parent_need_id and parent_need_id not in self.needs:
            raise NeedumlException(
                f"JinjaFunctions initialized with undefined parent_need_id: '{parent_need_id}'"
            )
        self.processed_need_ids = processed_need_ids

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
        # use jinja2uml to render the current uml content
        (uml, processed_need_ids_return) = jinja2uml(
            app=self.app,
            fromdocname=self.fromdocname,
            uml_content=uml_content,
            parent_need_id=need_id,
            key=key,
            processed_need_ids=self.processed_need_ids,
            kwargs=kwargs,
        )

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

        needs_config = NeedsSphinxConfig(self.app.config)
        diagram_template = Template(needs_config.diagram_template)
        node_text = diagram_template.render(**need_info, **needs_config.render_context)

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
        if need_id not in self.needs:
            raise NeedumlException(
                f"Jinja function ref is called with undefined need_id: '{need_id}'."
            )
        if (option and text) and (not option and not text):
            raise NeedumlException(
                "Jinja function ref requires exactly one entry 'option' or 'text'"
            )

        need_info = self.needs[need_id]
        link = calculate_link(self.app, need_info, self.fromdocname)

        need_uml = " [[{link} {content}]]".format(
            link=link,
            content=need_info.get(option, "") if option else text,
        )

        return need_uml

    def filter(self, filter_string: str) -> list[NeedsInfoType]:
        """
        Return a list of found needs that pass the given filter string.
        """
        needs_config = NeedsSphinxConfig(self.app.config)

        return filter_needs(
            list(self.needs.values()), needs_config, filter_string=filter_string
        )

    def imports(self, *args: str) -> str:
        if not self.parent_need_id:
            raise NeedumlException(
                "Jinja function 'import()' is not supported in needuml directive."
            )
        # gets all need ids from need links/extra_links options and wrap into jinja function uml()
        need_info = self.needs[self.parent_need_id]
        uml_ids = []
        for option_name in args:
            # check if link option_name exists in current need object
            if option_value := need_info.get(option_name):
                try:
                    iterable_value = list(option_value)  # type: ignore
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

    def need(self) -> NeedsInfoType:
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

    # for node in doctree.findall(Needuml):
    for node in found_nodes:
        id = node.attributes["ids"][0]
        current_needuml = SphinxNeedsData(env).get_or_create_umls()[id]

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

        puml_node = transform_uml_to_plantuml_node(
            app=app,
            uml_content=current_needuml["content"],
            parent_need_id=parent_need_id,
            key=current_needuml["key"],
            kwargs=current_needuml["extra"],
            config=config,
        )

        # Add source origin
        puml_node.line = current_needuml["lineno"]
        puml_node.source = env.doc2path(current_needuml["docname"])

        # Add calculated needuml content
        current_needuml["content_calculated"] = puml_node["uml"]

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
