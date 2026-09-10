"""The documentation toolchain the Sphinx extension needs, checked at load time.

Sphinx and sphinx-needs are the ``sphinx`` extra of this package rather than
dependencies: the ``test-reports`` command runs where they are not installed.
An extra is opt-in, so nothing shows pip the extra's version floors when a
project installs the bare package into an environment that already holds an
older toolchain -- the old versions stay, and the extension would fail later,
inside a directive, with a traceback that does not say why.

:func:`unmet_requirements` compares the installed toolchain against the floors
the extra declares, read from this package's own metadata so that they live in
``pyproject.toml`` alone. The lazy ``setup`` in the package ``__init__`` calls
it before the extension is imported and raises Sphinx's ``ExtensionError``
with the install line.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, requires, version
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packaging.requirements import Requirement

#: The distribution whose metadata declares the toolchain.
DISTRIBUTION = "sphinx-test-reports"
#: The extra holding the Sphinx extension's dependencies.
EXTRA = "sphinx"
#: The install line named by every message about a missing or outdated toolchain.
INSTALL_HINT = f'pip install "{DISTRIBUTION}[{EXTRA}]"'


def toolchain_requirements() -> list[Requirement]:
    """The requirements the extra declares, read from the installed metadata.

    Empty without metadata (the package imported from a source tree on
    ``sys.path``) and without ``packaging``, which parses them: it is not a
    dependency of this package but arrives with Sphinx (and with pytest), so it
    is there wherever the extension is loaded.
    """
    try:
        from packaging.requirements import Requirement
    except ImportError:
        return []
    try:
        declared = requires(DISTRIBUTION) or []
    except PackageNotFoundError:
        return []
    requirements = [Requirement(spec) for spec in declared]
    return [
        requirement
        for requirement in requirements
        if requirement.marker is not None
        and requirement.marker.evaluate({"extra": EXTRA})
    ]


def unmet_requirements() -> list[str]:
    """One sentence per requirement of the extra the environment falls short of.

    A requirement whose distribution is not installed at all is not reported:
    the import that fails on it states the problem more precisely, and a
    toolchain importable from a source tree without metadata must not be
    refused on the strength of the metadata alone.
    """
    unmet: list[str] = []
    for requirement in toolchain_requirements():
        try:
            installed = version(requirement.name)
        except PackageNotFoundError:
            continue
        if not requirement.specifier.contains(installed, prereleases=True):
            unmet.append(
                f"{requirement.name} {installed} is installed, "
                f"but {requirement.name}{requirement.specifier} is required"
            )
    return unmet
