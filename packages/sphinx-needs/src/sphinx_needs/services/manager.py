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
        configured = NeedsSphinxConfig(self.app.config).services
        entry = configured.get(name) if isinstance(configured, Mapping) else None
        if isinstance(entry, Mapping):
            # named in the live value, but not when the services were decided
            message = (
                f"Service {name!r} is named in needs_services, but only after the "
                "built-in services were decided (config-inited priority 12), so it is "
                "not registered: set it in conf.py, the needs_from_toml file, or a "
                "config-inited handler at priority 11 or below"
            )
            if "class" in entry:
                # setting it earlier would register the built-in, not this class
                message += (
                    "; a service class of your own needs a name of its own, as a "
                    "built-in name is always the built-in service"
                )
            return message
        if isinstance(configured, Mapping) and name in configured:
            # named with a value of another kind (reported as needs.config)
            return (
                f"Service {name!r} is a built-in service whose needs_services entry is "
                "not a mapping of options, so it is not registered: configure it as a "
                f"mapping, e.g. {builtin_service_fix(name)}"
            )
        return (
            f"Service {name!r} is a built-in service that is not configured, so it is "
            f"not registered: name it in needs_services to use it, e.g. "
            f"{builtin_service_fix(name)}"
        )


def builtin_service_fix(name: str) -> str:
    """How to configure the built-in service of the name, one spelling for every
    warning that gives it."""
    return (
        f'needs_services = {{"{name}": {{}}}} in conf.py, or a '
        f"[needs.services.{name}] table in the needs_from_toml file (below its "
        "needs_from_toml_table, if one is set)"
    )


class NeedsServiceException(Exception):
    """Raised when a service is not registered."""
