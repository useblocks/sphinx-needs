from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from sphinx.util.docutils import SphinxDirective

from sphinx_needs.logging import get_logger


class BaseService:
    options: ClassVar[Sequence[str]]
    """The options of the ``needservice`` directive the service reads, beside those of
    a need: request parameters, such as the GitHub services' ``query``. They are never
    need fields, and are not copied onto the needs the service creates."""

    fields: ClassVar[Sequence[str]]
    """The need fields the service's needs carry, registered when the service is.

    A service class that declares ``options`` but no ``fields`` of its own is read the
    way it was written: its options are its fields too (deprecated).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.log = get_logger(__name__)

    # note the public API originally just had the `request` method that parsed options as the first argument,
    # and so to not break existing subclasses, we keep that method signature,
    # then also introduce `request_from_directive`, which is what is now called by the directive

    def request(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        raise NotImplementedError("Must be implemented by the service!")

    def request_from_directive(
        self, directive: SphinxDirective, /
    ) -> list[dict[str, Any]]:
        return self.request(directive.options)

    def debug(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("Must be implemented by the service!")


def is_legacy_service(klass: object, /) -> bool:
    """Whether a service class is written for the old meaning of ``options``, where its
    options were its need fields too.

    It is when it has no ``fields``, or when it declares ``options`` in a class more
    derived than the one declaring ``fields`` -- such as a subclass of
    ``GithubService`` adding to its options. The class may be any callable carrying the
    attributes, such as a factory function, which is read by its attributes alone.

    :param klass: The service class, as ``needs_services`` or the API gives it.
    """
    if getattr(klass, "fields", None) is None:
        return True
    mro = getattr(klass, "__mro__", None)
    if not isinstance(mro, tuple):
        return False
    options_owner = next((i for i, k in enumerate(mro) if "options" in vars(k)), None)
    fields_owner = next((i for i, k in enumerate(mro) if "fields" in vars(k)), None)
    return (
        options_owner is not None
        and fields_owner is not None
        and options_owner < fields_owner
    )


def service_fields(klass: object, /) -> list[str]:
    """The need fields a service class registers: its ``fields``; for a class written
    for the old meaning, its options but ``type`` (a core field) too.

    :param klass: The service class, as ``needs_services`` or the API gives it.
    """
    fields = list(getattr(klass, "fields", None) or ())
    if is_legacy_service(klass):
        fields.extend(
            option
            for option in legacy_service_options(klass)
            if option not in fields
        )
    return fields


def legacy_service_options(klass: object, /) -> list[str]:
    """The options of a service class written for the old meaning, which it registers
    as need fields: its options but ``type``, a core field. None for another class.

    :param klass: The service class, as ``needs_services`` or the API gives it.
    """
    if not is_legacy_service(klass):
        return []
    return [option for option in getattr(klass, "options", ()) if option != "type"]


def service_options(klass: object, /) -> list[str]:
    """The options of the ``needservice`` directive a service class reads, which are
    not need fields. None for a class written for the old meaning, whose options are
    its fields.

    :param klass: The service class, as ``needs_services`` or the API gives it.
    """
    if is_legacy_service(klass):
        return []
    return list(getattr(klass, "options", ()))
