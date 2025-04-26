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
            "missing_id",
            "invalid_id",
            "duplicate_id",
            "invalid_status",
            "invalid_tags",
            "invalid_constraints",
            "invalid_jinja_content",
            "invalid_template",
            "global_option",
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
        "missing_id",
        "invalid_id",
        "duplicate_id",
        "invalid_status",
        "invalid_tags",
        "invalid_constraints",
        "invalid_jinja_content",
        "invalid_template",
        "global_option",
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
