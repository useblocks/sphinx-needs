from typing import Dict

from docutils.parsers.rst import directives
from sphinx.application import Sphinx

from sphinx_needs.api.configuration import NEEDS_CONFIG
from sphinx_needs.directives.needservice import NeedserviceDirective
from sphinx_needs.logging import get_logger
from sphinx_needs.services.base import BaseService


class ServiceManager:
    def __init__(self, app: Sphinx):
        self.app = app

        self.log = get_logger(__name__)
        self.services: Dict[str, BaseService] = {}

    def register(self, name: str, clazz, **kwargs) -> None:
        try:
            config = self.app.config.needs_services[name]
        except KeyError:
            self.log.debug(
                "No service config found for {}. " "Add it in your conf.py to needs_services dictionary.".format(name)
            )
            config = {}

        # Register options from service class
        for option in clazz.options:
            extra_option_names = NEEDS_CONFIG.get("extra_options").keys()
            if option not in extra_option_names:
                self.log.debug(f'Register option "{option}" for service "{name}"')
                NEEDS_CONFIG.add("extra_options", {option: directives.unchanged}, dict, append=True)
                # Register new option directly in Service directive, as its class options got already
                # calculated
                NeedserviceDirective.option_spec[option] = directives.unchanged

        # Init service with custom config
        self.services[name] = clazz(self.app, name, config, **kwargs)

    def get(self, name: str) -> BaseService:
        if name in self.services:
            return self.services[name]
        else:
            raise NeedsServiceException(
                "Service {} could not be found. " "Available services are {}".format(name, ", ".join(self.services))
            )


class NeedsServiceException(BaseException):
    pass
