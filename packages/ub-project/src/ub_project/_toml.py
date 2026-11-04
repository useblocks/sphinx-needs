"""The one TOML parser in the package: TOML 1.1 on every supported Python.

The standard library's ``tomllib`` reads TOML 1.1 from Python 3.15 and TOML 1.0 below it,
so below 3.15 its backport ``tomli`` (2.4 or later, which the manifest declares for those
Pythons alone) is read instead. Nothing else in the package imports a TOML library, and no
TOML library name or exception class leaves it: a consumer sees
:class:`~ub_project.ProjectConfigError`.
"""

from __future__ import annotations

import sys

if sys.version_info >= (3, 15):
    import tomllib as _reader
else:
    import tomli as _reader

#: The parser's error for invalid TOML; it is a different class on each branch.
TOMLDecodeError = _reader.TOMLDecodeError
load = _reader.load
loads = _reader.loads
