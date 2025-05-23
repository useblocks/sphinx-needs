from __future__ import annotations

from typing import Any

from sphinx.application import Sphinx

from sphinx_needs.config import _NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.directives.needservice import NeedserviceDirective
from sphinx_needs.logging import get_logger
from sphinx_needs.services.base import BaseService


class ServiceManager:
    def __init__(self, app: Sphinx):
        self.app = app

        self.log = get_logger(__name__)
        self.services: dict[str, BaseService] = {}

    def register(self, name: str, klass: type[BaseService], **kwargs: Any) -> None:
        try:
            config = NeedsSphinxConfig(self.app.config).services[name]
        except KeyError:
            self.log.debug(
                f"No service config found for {name}. Add it in your conf.py to needs_services dictionary."
            )
            config = {}

        # Register options from service class
        for option in klass.options:
            if option not in _NEEDS_CONFIG.extra_options:
                self.log.debug(f'Register option "{option}" for service "{name}"')
                _NEEDS_CONFIG.add_extra_option(option, f"Added by service {name}")
                # Register new option directly in Service directive, as its class options got already
                # calculated
                NeedserviceDirective.option_spec[option] = _NEEDS_CONFIG.extra_options[
                    option
                ].validator

        # Init service with custom config
        self.services[name] = klass(self.app, name, config, **kwargs)

    def get(self, name: str) -> BaseService:
        if name in self.services:
            return self.services[name]
        else:
            raise NeedsServiceException(
                "Service {} could not be found. Available services are {}".format(
                    name, ", ".join(self.services)
                )
            )


class NeedsServiceException(BaseException):
    pass
