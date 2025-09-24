from __future__ import annotations

from typing import Literal

from sphinx.errors import SphinxError, SphinxWarning


class NeedsApiConfigException(SphinxError):
    """
    A configuration changes collides with the already provided configuration by the user.

    Example: An extension wants to add an already existing needs_type.
    """


class InvalidNeedException(Exception):
    """Raised when a need could not be created/added, due to a validation issue."""

    def __init__(
        self,
        type_: Literal[
            "invalid_kwargs",
            "invalid_type",
            "invalid_extra_option",
            "invalid_link_option",
            "missing_id",
            "invalid_id",
            "duplicate_id",
            "invalid_title",
            "invalid_status",
            "invalid_tags",
            "invalid_layout",
            "invalid_style",
            "invalid_value",
            "invalid_constraints",
            "invalid_jinja_content",
            "invalid_template",
            "global_option",
            "failed_init",
        ],
        message: str,
    ) -> None:
        self._type = type_
        self._message = message
        super().__init__(f"{message} [{type_}]")

    @property
    def type(
        self,
    ) -> Literal[
        "invalid_kwargs",
        "invalid_type",
        "invalid_extra_option",
        "invalid_link_option",
        "missing_id",
        "invalid_id",
        "duplicate_id",
        "invalid_title",
        "invalid_status",
        "invalid_tags",
        "invalid_layout",
        "invalid_style",
        "invalid_value",
        "invalid_constraints",
        "invalid_jinja_content",
        "invalid_template",
        "global_option",
        "failed_init",
    ]:
        return self._type

    @property
    def message(self) -> str:
        return self._message


class NeedsApiConfigWarning(SphinxWarning):
    pass


class NeedsInvalidException(SphinxError):
    pass


class NeedsConstraintFailed(SphinxError):
    pass


class NeedsInvalidFilter(SphinxError):
    pass


class NeedsConfigException(SphinxError):
    pass


class VariantParsingException(Exception):
    """Called if parsing of given function string has not worked"""

    def __init__(self, message: str) -> None:
        # as we often catch these exception in a generic way, add a prefix to the message,
        # to make it easier to identify the source of the error
        message = f"Error parsing variant function: {message}"
        super().__init__(message)


class FunctionParsingException(Exception):
    """Called if parsing of given function string has not worked"""

    def __init__(self, message: str, name: str | None) -> None:
        # as we often catch these exception in a generic way, add a prefix to the message,
        # to make it easier to identify the source of the error
        name_str = f" {name!r}" if name else ""
        message = f"Error parsing dynamic function{name_str}: {message}"
        super().__init__(message)
