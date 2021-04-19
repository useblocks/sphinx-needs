from docutils import nodes
from docutils.parsers.rst import Directive

from sphinxcontrib.needs.api import add_need
from sphinxcontrib.needs.directives.need import NeedDirective
from sphinxcontrib.needs.logging import get_logger


class Needservice(nodes.General, nodes.Element):
    pass


class NeedserviceDirective(Directive):
    has_content = True

    required_arguments = 1
    optional_arguments = 0

    option_spec = {}

    # Support all options from a common need.
    option_spec.update(NeedDirective.option_spec)

    final_argument_whitespace = True

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.log = get_logger(__name__)

    @property
    def env(self):
        return self.state.document.settings.env

    def run(self):
        docname = self.state.document.settings.env.docname
        app = self.env.app
        needs_services = self.env.app.needs_services

        service_name = self.arguments[0]
        service = needs_services.get(service_name)
        service_data = service.request(self.options)

        section = []

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
                    content.append("\n:{}: {}".format(name, value))

            # content.insert(0, '.. code-block:: text\n')
            options["content"] = "\n".join(content)
            # Replace values in datum with calculated/checked ones.
            datum.update(options)

            # ToDo: Tags and Status are not set (but exist in data)
            section += add_need(self.env.app, self.state, docname, self.lineno, need_type, need_title, **datum)

        return section
