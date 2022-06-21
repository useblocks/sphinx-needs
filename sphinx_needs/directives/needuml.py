import html
import os
from typing import Sequence

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from jinja2 import BaseLoader, Environment, Template

from sphinx_needs.diagrams_common import calculate_link
from sphinx_needs.directives.needflow import make_entity_name


class Needuml(nodes.General, nodes.Element):
    pass


class NeedumlDirective(Directive):
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
    }

    def run(self) -> Sequence[nodes.Node]:
        env = self.state.document.settings.env
        if not hasattr(env, "need_all_needumls"):
            env.need_all_needumls = {}

        targetid = "needuml-{docname}-{id}".format(docname=env.docname, id=env.new_serialno("needuml"))
        targetnode = nodes.target("", "", ids=[targetid])

        scale = self.options.get("scale", "").replace("%", "")
        align = self.options.get("align", "center")

        title = None
        if self.arguments:
            title = self.arguments[0]

        content = "\n".join(self.content)

        config_names = self.options.get("config", None)
        configs = []
        if config_names:
            for config_name in config_names.split(","):
                config_name = config_name.strip()
                if config_name and config_name in env.config.needs_flow_configs:
                    configs.append(env.config.needs_flow_configs[config_name])

        extra_dict = {}
        extras = self.options.get("extra", None)
        if extras:
            extras = extras.split(",")
            for extra in extras:
                key, value = extra.split(":")
                extra_dict[key] = value

        env.need_all_needumls[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_node": targetnode,
            "caption": title,
            "content": content,
            "scale": scale,
            "align": align,
            "config_names": config_names,
            "config": "\n".join(configs),
            "debug": "debug" in self.options,
            "extra": extra_dict,
        }

        return [targetnode] + [Needuml("")]


class JinjaFunctions:
    """
    Contains Jinja helper functions

    Provides access to sphinx-app and all Needs objects.
    """

    def __init__(self, app, fromdocname):
        self.needs = app.builder.env.needs_all_needs
        self.app = app
        self.fromdocname = fromdocname

    def uml(self, need_id, **kwargs):
        need_info = self.needs[need_id]
        if need_info["type_content"] == "plantuml":
            uml_content = need_info["content"]

            # We need to rerender the fetched content, as it may contain also Jinja statements.
            mem_template = Environment(loader=BaseLoader).from_string(uml_content)
            data = {"needs": self.needs, "uml": self.uml, "need": self.need}
            data.update(kwargs)
            uml = mem_template.render(**data)
        else:
            uml = self.need(need_id)
        return uml

    def need(self, need_id):
        need_info = self.needs[need_id]
        link = calculate_link(self.app, need_info, self.fromdocname)

        diagram_template = Template(self.app.builder.env.config.needs_diagram_template)
        node_text = diagram_template.render(**need_info)

        need_uml = '{style} "{node_text}" as {id} [[{link}]] #{color}\n'.format(
            id=make_entity_name(need_id),
            node_text=node_text,
            link=link,
            color=need_info["type_color"].replace("#", ""),
            style=need_info["type_style"],
        )

        return need_uml

# why does we have to have app, fromdocname as parameters here?
# Reason jinja and importer check. I would say, encapsulation is worngly used in the solution and shall be refactored.
def generate_plantuml_image_from_uml_text(app, fromdocname, content: str = '', docname: str = '', caption: str = '',
scale: str = '', align: str = None, extra: dict = None, config: list = None, debug: bool = False, disable_jinja: bool = False) -> list:

    env = app.builder.env
    all_needs = env.needs_all_needs

    new_node_content = []

    # todo: this is really ugly, could we generate a "one time warning" and return in all other cases nothing?
    try:
        if "sphinxcontrib.plantuml" not in app.config.extensions:
            raise ImportError
        from sphinxcontrib.plantuml import plantuml
    except ImportError:
        error_node = nodes.error()
        para = nodes.paragraph()
        text = nodes.Text("PlantUML is not available!", "PlantUML is not available!")
        para += text
        error_node.append(para)
        new_node_content.append(error_node)
        return new_node_content

    # Replace PlantUML entry-code, so that the uml-code is "clean"
    uml_content = content.replace("@startuml", "").replace("@enduml", "")
    if not disable_jinja:
        # Render uml content with jinja
        mem_template = Environment(loader=BaseLoader).from_string(uml_content)

        # Get all needed Jinja Helper Functions
        jinja_utils = JinjaFunctions(app, fromdocname)
        # Make the helpers available during rendering
        data = {"needs": all_needs, "uml": jinja_utils.uml, "need": jinja_utils.need}

        data.update(extra)

        uml_content = mem_template.render(**data)
    
    # Create basic uml node
    plantuml_block_text = ".. plantuml::\n\n   @startuml\n   @enduml"
    puml_node = plantuml(plantuml_block_text)

    try:
        scale = int(scale)
    except ValueError:
        scale = 100
    # if scale != 100:
    puml_node["scale"] = scale

    if align:
        puml_node["align"] = align
    else:
        puml_node["align"] = "center"
    
    # Add needuml specific content
    puml_node["uml"] = "@startuml\nallowmixing\n"

    # Adding config
    if config and len(config) >= 3:
        # Remove all empty lines
        config = "\n".join([line.strip() for line in config.split("\n") if line.strip()])
        puml_node["uml"] += "\n' Config\n\n"
        puml_node["uml"] += config
        puml_node["uml"] += "\n\n"

    puml_node["uml"] += f"\n{uml_content}"

    puml_node["uml"] += "\n@enduml\n"

    puml_node["incdir"] = os.path.dirname(docname)
    puml_node["filename"] = os.path.split(docname)[1]  # Needed for plantuml >= 0.9

    new_node_content.append(puml_node)

    if caption:
        title_text = caption
        title = nodes.title(title_text, "", nodes.Text(title_text))
        new_node_content.insert(0, title)

    if debug:
        debug_container = nodes.container()
        if isinstance(puml_node, nodes.figure):
            data = puml_node.children[0]["uml"]
        else:
            data = puml_node["uml"]
        data = "\n".join([html.escape(line) for line in data.split("\n")])
        debug_para = nodes.raw("", f"<pre>{data}</pre>", format="html")
        debug_container += debug_para
        new_node_content += debug_container

    return new_node_content

def process_needuml(app, doctree, fromdocname):
    env = app.builder.env
    all_needs = env.needs_all_needs

    for node in doctree.traverse(Needuml):

        id = node.attributes["ids"][0]
        current_needuml = env.need_all_needumls[id]

        content = generate_plantuml_image_from_uml_text(
            app = app,
            fromdocname = fromdocname,
            content = current_needuml["content"],
            docname = current_needuml["docname"],
            caption = current_needuml["caption"],
            scale = current_needuml["scale"],
            align = current_needuml["align"],
            extra = current_needuml["extra"],
            config = current_needuml["config"],
            debug = current_needuml["debug"]
            )

        node.replace_self(content)
