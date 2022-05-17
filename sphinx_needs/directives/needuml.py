import html
import os

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from jinja2 import BaseLoader, Environment


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
    }

    def run(self):
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
        }

        return [targetnode] + [Needuml("")]


class JinjaFunctions:
    """
    Contains Jinja helper functions

    Provides access to sphinx-app and all Needs objects.
    """

    def __init__(self, app):
        self.needs = app.builder.env.needs_all_needs

    def uml(self, need_id):
        need = self.needs[need_id]
        if need["type_content"] == "plantuml":
            uml_content = need["content"]

            # We need to rerender the fetched content, as it may contain also Jinja statements.
            mem_template = Environment(loader=BaseLoader).from_string(uml_content)
            data = {"needs": self.needs, "uml": self.uml}
            uml = mem_template.render(**data)
        else:
            uml = f'{need["type_style"]} "{need["title"][:20]}" as {need["id"]} {need["type_color"]}'

        return uml


def process_needuml(app, doctree, fromdocname):
    env = app.builder.env
    all_needs = env.needs_all_needs

    for node in doctree.traverse(Needuml):
        id = node.attributes["ids"][0]
        current_needuml = env.need_all_needumls[id]

        try:
            if "sphinxcontrib.plantuml" not in app.config.extensions:
                raise ImportError
            from sphinxcontrib.plantuml import plantuml
        except ImportError:
            content = nodes.error()
            para = nodes.paragraph()
            text = nodes.Text("PlantUML is not available!", "PlantUML is not available!")
            para += text
            content.append(para)
            node.replace_self(content)
            continue

        content = []

        # Create basic uml node
        plantuml_block_text = ".. plantuml::\n\n   @startuml\n   @enduml"
        puml_node = plantuml(plantuml_block_text)

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

        # Replace PlantUML entry-code, so that the uml-code is "clean"
        uml_content = current_needuml["content"].replace("@startuml", "").replace("@enduml", "")
        # Render uml content with jinja
        mem_template = Environment(loader=BaseLoader).from_string(uml_content)

        # Get all needed Jinja Helper Functions
        jinja_utils = JinjaFunctions(app)

        data = {"needs": all_needs, "uml": jinja_utils.uml}
        uml_content = mem_template.render(**data)
        # Add needuml specific content
        puml_node["uml"] = "@startuml\n"

        # Adding config
        config = current_needuml["config"]
        if config and len(config) >= 3:
            # Remove all empty lines
            config = "\n".join([line.strip() for line in config.split("\n") if line.strip()])
            puml_node["uml"] += "\n' Config\n\n"
            puml_node["uml"] += config
            puml_node["uml"] += "\n\n"

        puml_node["uml"] += f"\n{uml_content}"

        puml_node["uml"] += "\n@enduml\n"

        puml_node["incdir"] = os.path.dirname(current_needuml["docname"])
        puml_node["filename"] = os.path.split(current_needuml["docname"])[1]  # Needed for plantuml >= 0.9

        content.append(puml_node)

        if current_needuml["caption"]:
            title_text = current_needuml["caption"]
            title = nodes.title(title_text, "", nodes.Text(title_text))
            content.insert(0, title)

        if current_needuml["debug"]:
            debug_container = nodes.container()
            if isinstance(puml_node, nodes.figure):
                data = puml_node.children[0]["uml"]
            else:
                data = puml_node["uml"]
            data = "\n".join([html.escape(line) for line in data.split("\n")])
            debug_para = nodes.raw("", f"<pre>{data}</pre>", format="html")
            debug_container += debug_para
            content += debug_container

        node.replace_self(content)
