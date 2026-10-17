from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sphinx.application import Sphinx

from sphinx_needs.config import _NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.logging import get_logger
from sphinx_needs.services.base import BaseService
from sphinx_needs.services.config.github import GITHUB_SERVICES


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
            if option == "type":
                # TODO this should probably be done a bit more systematically;
                # the github service adds a "type" option, but this is related to the core need field NOT an extra field
                pass
            elif option not in _NEEDS_CONFIG.fields:
                self.log.debug(f'Register option "{option}" for service "{name}"')
                _NEEDS_CONFIG.add_field(
                    option,
                    f"Added by service {name}",
                    "service",
                    nullable=True,
                    schema={"type": "string"},
                )

        # Init service with custom config
        self.services[name] = klass(self.app, name, config, **kwargs)

    def get(self, name: str) -> BaseService:
        """The registered service of the name.

        :raises NeedsServiceException: If no service of the name is registered; for a
            built-in GitHub service, saying it is not configured and how to configure it.
        """
        if name in self.services:
            return self.services[name]
        if name in GITHUB_SERVICES:
            raise NeedsServiceException(self._unregistered_builtin(name))
        if not self.services:
            raise NeedsServiceException(
                f"Service {name} could not be found: no service is registered"
            )
        raise NeedsServiceException(
            "Service {} could not be found. Available services are {}".format(
                name, ", ".join(self.services)
            )
        )

    def _unregistered_builtin(self, name: str) -> str:
        """Why the built-in service of the name is not registered, and the fix."""
        example = (
            f'e.g. needs_services = {{"{name}": {{}}}} in conf.py, or a '
            f"[needs.services.{name}] table in ubproject.toml"
        )
        configured = NeedsSphinxConfig(self.app.config).services
        if (
            isinstance(configured, Mapping)
            and name in configured
            and not isinstance(configured[name], Mapping)
        ):
            return (
                f"Service {name!r} is a built-in service whose needs_services entry is "
                "not a mapping of options, so it is not registered: configure it as a "
                f"mapping, {example}"
            )
        return (
            f"Service {name!r} is a built-in service that is not configured, so it is "
            f"not registered: name it in needs_services to use it, {example}"
        )


class NeedsServiceException(Exception):
    """Raised when a service is not registered."""
