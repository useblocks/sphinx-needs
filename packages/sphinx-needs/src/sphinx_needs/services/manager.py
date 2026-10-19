from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sphinx.application import Sphinx

from sphinx_needs.config import _NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.exceptions import NeedsApiConfigException
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.services.base import (
    BaseService,
    legacy_service_options,
    service_declaration_problem,
    service_fields,
    service_options,
)
from sphinx_needs.services.config.github import GITHUB_SERVICES


class ServiceManager:
    def __init__(self, app: Sphinx):
        self.app = app

        self.log = get_logger(__name__)
        self.services: dict[str, BaseService] = {}
        #: the needservice options of each registered service, by name
        self._options: dict[str, tuple[str, ...]] = {}

    def register(self, name: str, klass: type[BaseService], **kwargs: Any) -> None:
        """Register a service of the name, made by calling the class, and the need
        fields it declares.

        :raises NeedsApiConfigException: If the class's ``options`` or ``fields`` are
            not lists of names.
        """
        if (problem := service_declaration_problem(klass)) is not None:
            qualname = getattr(klass, "__qualname__", type(klass).__name__)
            raise NeedsApiConfigException(
                f"Service {name!r} cannot be registered: its class {qualname!r} "
                f"{problem}"
            )
        try:
            config = NeedsSphinxConfig(self.app.config).services[name]
        except KeyError:
            self.log.debug(
                f"No service config found for {name}. Add it in your conf.py to needs_services dictionary."
            )
            config = {}

        if legacy := legacy_service_options(klass):
            qualname = getattr(klass, "__qualname__", type(klass).__name__)
            listed = ", ".join(repr(option) for option in legacy)
            # an empty list would drop the fields the class inherits
            owner = next(
                (
                    k
                    for k in getattr(klass, "__mro__", ())
                    if vars(k).get("fields") is not None
                ),
                None,
            )
            remedy = (
                "list the fields its needs carry in 'fields' (an empty list will do)"
                if owner is None
                else "declare 'fields' in the class itself, keeping those it inherits "
                f"(fields = [*{owner.__qualname__}.fields])"
            )
            log_warning(
                self.log,
                f"Service {name!r}: its class {qualname!r} declares 'options' but no "
                f"'fields' of its own, so its options ({listed}) are registered as "
                "need fields. This is deprecated: from sphinx-needs 10.0 a service's "
                f"'options' are only the needservice options it reads; {remedy}",
                "deprecated",
                None,
            )

        # Register the need fields of the service class
        for field_name in service_fields(klass):
            if field_name not in _NEEDS_CONFIG.fields:
                self.log.debug(f'Register field "{field_name}" for service "{name}"')
                _NEEDS_CONFIG.add_field(
                    field_name,
                    f"Added by service {name}",
                    "service",
                    nullable=True,
                    schema={"type": "string"},
                )
        self._options[name] = tuple(service_options(klass))

        # Init service with custom config
        self.services[name] = klass(self.app, name, config, **kwargs)

    def directive_options(self, name: str) -> Sequence[str] | None:
        """The options of the ``needservice`` directive the service registered under
        the name reads, which are not need fields: empty for a service class written
        for the old meaning of ``options``, whose options are its fields, and None for
        a name no service was registered under."""
        return self._options.get(name)

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
