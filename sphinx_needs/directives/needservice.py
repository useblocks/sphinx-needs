import typing
from typing import Any, Dict, List, Sequence

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from docutils.parsers.rst.states import RSTState, RSTStateMachine
from docutils.statemachine import StringList
from sphinx.environment import BuildEnvironment
from sphinx_data_viewer.api import get_data_viewer_node

from sphinx_needs.api import add_need
from sphinx_needs.directives.need import NeedDirective
from sphinx_needs.logging import get_logger
from sphinx_needs.services.base import BaseService
from sphinx_needs.utils import add_doc, unwrap


class Needservice(nodes.General, nodes.Element):  # type: ignore
    pass


class NeedserviceDirective(Directive):
    has_content = True

    required_arguments = 1
    optional_arguments = 0

    option_spec = {
        "debug": directives.flag,
    }

    # Support all options from a common need.
    option_spec.update(NeedDirective.option_spec)

    final_argument_whitespace = True

    def __init__(
        self,
        name: str,
        arguments: List[str],
        options: Dict[str, Any],
        content: StringList,
        lineno: int,
        content_offset: int,
        block_text: str,
        state: RSTState,
        state_machine: RSTStateMachine,
    ):
        super().__init__(name, arguments, options, content, lineno, content_offset, block_text, state, state_machine)
        self.log = get_logger(__name__)

    @property
    def env(self) -> BuildEnvironment:
        return typing.cast(BuildEnvironment, self.state.document.settings.env)

    def run(self) -> Sequence[nodes.Node]:
        docname = self.env.docname
        app = self.env.app
        needs_services: Dict[str, BaseService] = getattr(app, "needs_services", {})

        service_name = self.arguments[0]
        service = unwrap(needs_services.get(service_name))
        section = []

        if "debug" not in self.options:
            service_data = service.request(self.options)
            for datum in service_data:
                options = {}

                try:
                    content = datum["content"].split("\n")
                except KeyError:
                    content = []

                content.extend(self.content)

                if "type" not in datum.keys():
                    # Use the first defined type, if nothing got defined by service (should not be the case)
                    need_type = self.env.app.config.needs_types[0]["directive"]
                else:
                    need_type = datum["type"]
                    del datum["type"]

                if "title" not in datum.keys():
                    need_title = ""
                else:
                    need_title = datum["title"]
                    del datum["title"]

                # We need to check if all given options from services are really available as configured
                # extra_option or extra_link
                missing_options = {}
                for element in datum.keys():
                    defined_options = list(self.__class__.option_spec.keys())
                    defined_options.append("content")  # Add content, so that it gets not detected as missing
                    if element not in defined_options and element not in getattr(app.config, "needs_extra_links", []):
                        missing_options[element] = datum[element]

                # Finally delete not found options
                for missing_option in missing_options:
                    del datum[missing_option]

                if app.config.needs_service_all_data:
                    for name, value in missing_options.items():
                        content.append(f"\n:{name}: {value}")

                # content.insert(0, '.. code-block:: text\n')
                options["content"] = "\n".join(content)
                # Replace values in datum with calculated/checked ones.
                datum.update(options)

                # ToDo: Tags and Status are not set (but exist in data)
                section += add_need(self.env.app, self.state, docname, self.lineno, need_type, need_title, **datum)
        else:
            try:
                service_debug_data = service.debug(self.options)
            except NotImplementedError:
                service_debug_data = {"error": f'Service {service_name} does not support "debug" output.'}
            viewer_node = get_data_viewer_node(title="Debug data", data=service_debug_data)
            section.append(viewer_node)

        add_doc(self.env, self.env.docname)

        return section
