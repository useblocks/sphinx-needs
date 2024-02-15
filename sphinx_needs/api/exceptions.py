from __future__ import annotations

from sphinx.errors import SphinxError, SphinxWarning


class NeedsApiConfigException(SphinxError):
    """
    A configuration changes collides with the already provided configuration by the user.

    Example: An extension wants to add an already existing needs_type.
    """


class NeedsApiConfigWarning(SphinxWarning):
    pass


class NeedsNoIdException(SphinxError):
    pass


class NeedsDuplicatedId(SphinxError):
    pass


class NeedsStatusNotAllowed(SphinxError):
    pass


class NeedsTagNotAllowed(SphinxError):
    pass


class NeedsInvalidException(SphinxError):
    pass


class NeedsConstraintNotAllowed(SphinxError):
    pass


class NeedsConstraintFailed(SphinxError):
    pass


class NeedsInvalidOption(SphinxError):
    pass


class NeedsTemplateException(SphinxError):
    pass


class NeedsInvalidFilter(SphinxError):
    pass
