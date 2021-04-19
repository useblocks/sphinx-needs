from docutils.parsers.rst import directives

from sphinxcontrib.needs.directives.needservice import NeedserviceDirective
from sphinxcontrib.needs.logging import get_logger


class ServiceManager:
    def __init__(self, app):
        self.app = app

        self.log = get_logger(__name__)
        self.services = {}

    def register(self, name, clazz, **kwargs):
        try:
            config = self.app.config.needs_services[name]
        except KeyError:
            self.log.debug(
                "No service config found for {}. " "Add it in your conf.py to needs_services dictionary.".format(name)
            )
            config = {}

        # Register options from service class
        for option in clazz.options:
            if option not in self.app.config.needs_extra_options.keys():
                self.log.debug('Register option "{}" for service "{}"'.format(option, name))
                self.app.config.needs_extra_options[option] = directives.unchanged
                # Register new option directly in Service directive, as its class options got already
                # calculated
                NeedserviceDirective.option_spec[option] = directives.unchanged

        # Init service with custom config
        self.services[name] = clazz(self.app, name, config, **kwargs)

    def get(self, name):
        if name in self.services.keys():
            return self.services[name]
        else:
            raise NeedsServiceException(
                "Service {} could not be found. " "Available services are {}".format(name, ", ".join(self.services))
            )


class NeedsServiceException(BaseException):
    pass
