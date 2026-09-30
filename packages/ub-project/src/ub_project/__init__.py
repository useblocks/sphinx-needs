"""The shared reader for ``ubproject.toml`` and its variant data.

One implementation of the parts of ``ubproject.toml`` that more than one tool reads -- the
sphinx-needs family of Sphinx extensions and their command lines, which will depend on it,
and ubCode, which is to be held to the same behaviour through the conformance corpus in
this package's tests. Standard library only: no Sphinx, no docutils, no sibling
distribution.

It decides no policy. Discovery (walk up or read the ``confdir``), whether a finding is
worth a warning, and how ``-D`` / ``-c`` on a command line interact with the file are each
consumer's to decide; this package returns what it found and raises
:class:`ProjectConfigError` for what it cannot accept.
"""

from ub_project.project import (
    DEFAULT_FILENAME,
    ProjectConfigError,
    anchor,
    find_project_config,
    load_toml,
    select_table,
    table_path,
)
from ub_project.variant_data import (
    deep_merge,
    load_variant_data_file,
    resolve_variant_data,
    validate_variant_data,
)
from ub_project.variants import (
    VARIANT_DATA_LEGACY_LOCATION,
    VARIANT_DATA_LOCATION,
    VARIANTS_UNKNOWN_KEY,
    Diagnostic,
    VariantsResult,
    read_variants,
)

__version__ = "1.0.0.dev0"

__all__ = [
    "DEFAULT_FILENAME",
    "VARIANTS_UNKNOWN_KEY",
    "VARIANT_DATA_LEGACY_LOCATION",
    "VARIANT_DATA_LOCATION",
    "Diagnostic",
    "ProjectConfigError",
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
