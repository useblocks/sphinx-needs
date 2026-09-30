"""The shared reader for ``ubproject.toml`` and its variant data.

One implementation of the parts of ``ubproject.toml`` that more than one tool reads -- the
sphinx-needs family of Sphinx extensions, their command lines, and ubCode, which is held to
the same behaviour by the conformance corpus in this package's tests. Standard library
only: no Sphinx, no docutils, no sibling distribution.

It decides no policy. Discovery (walk up or read the ``confdir``), whether a finding is
worth a warning, and how ``-D`` / ``-c`` on a command line interact with the file are each
consumer's to decide; this package returns what it found and raises
:class:`UbprojectError` for what it cannot accept.
"""

from ubproject.project import (
    DEFAULT_FILENAME,
    UbprojectError,
    anchor,
    find_project_config,
    load_toml,
    select_table,
    table_path,
)
from ubproject.variant_data import (
    deep_merge,
    load_variant_data_file,
    resolve_variant_data,
    validate_variant_data,
)
from ubproject.variants import (
    VARIANT_DATA_LEGACY_LOCATION,
    VARIANT_DATA_LOCATION,
    VARIANTS_UNKNOWN_KEY,
    Diagnostic,
    VariantsResult,
    read_variants,
)

__version__ = "1.0.0"

__all__ = [
    "DEFAULT_FILENAME",
    "VARIANTS_UNKNOWN_KEY",
    "VARIANT_DATA_LEGACY_LOCATION",
    "VARIANT_DATA_LOCATION",
    "Diagnostic",
    "UbprojectError",
    "VariantsResult",
    "__version__",
    "anchor",
    "deep_merge",
    "find_project_config",
    "load_toml",
    "load_variant_data_file",
    "read_variants",
    "resolve_variant_data",
    "select_table",
    "table_path",
    "validate_variant_data",
]
