import os

from docutils import nodes

from docutils.parsers.rst import Directive
from pkg_resources import parse_version
import sphinx

from sphinxcontrib.needs.api import add_need
from sphinxcontrib.needs.utils import INTERNALS

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging
logger = logging.getLogger(__name__)


class Needservice(nodes.General, nodes.Element):
    pass


class NeedserviceDirective(Directive):
    has_content = True

    required_arguments = 1
    optional_arguments = 0

    option_spec = {}

    final_argument_whitespace = True

    def __init__(self, *args, **kw):
        super(NeedserviceDirective, self).__init__(*args, **kw)
        self.log = logging.getLogger(__name__)

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

            content = datum['content'].split('\n')
            content.extend(self.content)

            if 'type' not in datum.keys():
                # Use the first defined type, if nothing got defined by service (should not be the case)
                need_type = self.env.app.config.needs_types[0]['directive']
            else:
                need_type = datum['type']
                del datum['type']

            if 'title' not in datum.keys():
                need_title = ""
            else:
                need_title = datum['title']
                del datum['title']

            # We need to check if all given options from services are really available as configured
            # extra_option or extra_link
            missing_options = {}
            for element in datum.keys():
                defined_options = INTERNALS + list(getattr(app.config, "needs_extra_options", {}).keys())
                if element not in defined_options and element not in getattr(app.config, "needs_extra_links", []):
                    missing_options[element] = datum[element]

            # Finally delete not found options
            for missing_option in missing_options:
                del datum[missing_option]

            if app.config.needs_service_all_data:
                for name, value in missing_options.items():
                    content.append(f'\n:{name}: {value}')

            options['content'] = '\n'.join(content)
            # Replace values in datum with calculated/checked ones.
            datum.update(options)

            section += add_need(self.env.app, self.state, docname, self.lineno,
                                need_type, need_title, **datum)

        return section
