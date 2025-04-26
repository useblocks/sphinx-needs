import warnings

from sphinx_needs.exceptions import (
    InvalidNeedException,  # noqa: F401
    NeedsApiConfigException,  # noqa: F401
    NeedsApiConfigWarning,  # noqa: F401
    NeedsConstraintFailed,  # noqa: F401
    NeedsInvalidException,  # noqa: F401
    NeedsInvalidFilter,  # noqa: F401
)

warnings.warn(
    "'sphinx_needs.api.exceptions' is deprecated. Use 'sphinx_needs.exception' instead.",
    stacklevel=2,
)
