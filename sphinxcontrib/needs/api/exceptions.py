from sphinx.errors import SphinxError, SphinxWarning


class NeedsNotLoadedException(SphinxError):
    """
    Sphinx-Needs is not loaded. Therefore configuration parameters and functions are missing.

    Make sure ``sphinxcontrib.needs`` is added to the``extension`` parameter of
    ``conf.py``-
    """


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


class NeedsInvalidOption(SphinxError):
    pass


class NeedsTemplateException(SphinxError):
    pass
