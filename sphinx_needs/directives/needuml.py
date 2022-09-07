import html
import os
from typing import Sequence

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from jinja2 import BaseLoader, Environment, Template

from sphinx_needs.diagrams_common import calculate_link
from sphinx_needs.directives.needflow import make_entity_name
from sphinx_needs.filter_common import filter_needs


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
        "key": directives.unchanged_required,
        "save": directives.unchanged_required,
    }

    def run(self) -> Sequence[nodes.Node]:
        env = self.state.document.settings.env
        if not hasattr(env, "needs_all_needumls"):
            env.needs_all_needumls = {}

        if self.name == "needarch":
            targetid = "needarch-{docname}-{id}".format(docname=env.docname, id=env.new_serialno("needarch"))
            is_arch = True
        else:
            targetid = "needuml-{docname}-{id}".format(docname=env.docname, id=env.new_serialno("needuml"))
            is_arch = False

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

        key_name = self.options.get("key", None)
        if key_name == "diagram":
            raise NeedumlException(f"Needuml option key name can't be: {key_name}")

        save_path = self.options.get("save", None)
        plantuml_code_out_path = None
        if save_path:
            if os.path.isabs(save_path):
                raise NeedumlException(f"Given save path: {save_path}, is not a relative path.")
            else:
                plantuml_code_out_path = save_path

        env.needs_all_needumls[targetid] = {
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
            "key": key_name,
            "save": plantuml_code_out_path,
            "is_arch": is_arch,
        }

        return [targetnode] + [Needuml(targetid)]


class NeedarchDirective(NeedumlDirective):
    """
    Directive inherits from Needuml, but works only inside a need object.
    """

    def run(self) -> Sequence[nodes.Node]:
        return NeedumlDirective.run(self)


class JinjaFunctions:
    """
    Contains Jinja helper functions

    Provides access to sphinx-app and all Needs objects.
    """

    def __init__(self, app, fromdocname, parent_need_id):
        self.needs = app.builder.env.needs_all_needs
        self.app = app
        self.fromdocname = fromdocname
        self.parent_need_id = parent_need_id

    def uml(self, need_id, key="diagram", **kwargs):
        need_info = self.needs[need_id]

        if key != "diagram":
            if need_info[key]:
                uml_content = need_info[key]
            else:
                raise NeedumlException(f"Option key name: {key} does not exist in need {need_id}.")
        else:
            if need_info["diagram"]:
                uml_content = need_info["diagram"]
            else:
                return self.flow(need_id)

        # We need to rerender the fetched content, as it may contain also Jinja statements.
        mem_template = Environment(loader=BaseLoader).from_string(uml_content)
        data = {"needs": self.needs, "uml": self.uml, "flow": self.flow}
        data.update(kwargs)
        uml = mem_template.render(**data)

        return uml

    def flow(self, need_id):
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

    def filter(self, filter_string):
        """
        Return a list of found needs that pass the given filter string.
        """

        return filter_needs(self.app, list(self.needs.values()), filter_string=filter_string)

    def imports(self, *args):
        # gets all need ids from need links/extra_links options and wrap into jinja function uml()
        need_info = self.needs[self.parent_need_id]
        uml_ids = []
        for option_name in args:
            # check if link option_name exists in current need object
            if option_name in need_info and need_info[option_name]:
                for id in need_info[option_name]:
                    uml_ids.append(id)
        umls = ""
        if uml_ids:
            for uml_id in uml_ids:
                umls += self.uml(uml_id)
        return umls


def process_needuml(app, doctree, fromdocname):
    env = app.builder.env
    all_needs = env.needs_all_needs

    for node in doctree.findall(Needuml):
        id = node.attributes["ids"][0]
        current_needuml = env.needs_all_needumls[id]

        parent_need_id = None
        # Check if current needuml is needarch
        if current_needuml["is_arch"]:
            # Check if needarch is only used inside a need
            from sphinx_needs.directives.need import Need  # avoid circular import

            if not (current_needuml["target_node"].parent and isinstance(current_needuml["target_node"].parent, Need)):
                raise NeedArchException("Directive needarch can only be used inside a need.")
            else:
                # Calculate parent need id for needarch
                parent_need_id = current_needuml["target_node"].parent.attributes["refid"]

        try:
            if "sphinxcontrib.plantuml" not in app.config.extensions:
                raise ImportError
            from sphinxcontrib.plantuml import plantuml
        except ImportError:
            content = nodes.error()
            para = nodes.paragraph()
            text = nodes.Text("PlantUML is not available!")
            para += text
            content.append(para)
            # node.replace_self(content)
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
        jinja_utils = JinjaFunctions(app, fromdocname, parent_need_id)
        # Make the helpers available during rendering
        data = {"needs": all_needs, "uml": jinja_utils.uml, "flow": jinja_utils.flow, "filter": jinja_utils.filter}

        if current_needuml["is_arch"]:
            # Add jinja function import() only for needarch
            data.update({"import": jinja_utils.imports})
        else:
            # Check if func import() used in needuml
            if "{{import(" in current_needuml["content"]:
                raise NeedumlException("Jinja function import is not supported for needuml.")

        data.update(current_needuml["extra"])

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

        # Add calculated needuml content
        current_needuml["content_calculated"] = puml_node["uml"]

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


class NeedumlException(BaseException):
    """Errors during Needuml handling."""


class NeedArchException(BaseException):
    """Errors during Needarch handling."""
