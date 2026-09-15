"""The documentation toolchain is an extra; the extension checks it at load time.

``pip install sphinx-test-reports`` installs the converter's dependency only.
The Sphinx extension needs Sphinx and sphinx-needs at the versions the
``sphinx`` extra declares -- and an extra is opt-in, so a project that installs
the bare package next to an older toolchain never shows pip those floors. The
lazy ``setup`` compares the installed versions against the extra's declarations
when Sphinx loads the extension, and names the install line in its message.
"""

import sys
from importlib.metadata import PackageNotFoundError
from io import StringIO

import pytest

import sphinxcontrib.test_reports as package
from sphinxcontrib.test_reports import toolchain

DECLARED = [
    "lxml",
    'sphinx>=7.4; extra == "sphinx"',
    'sphinx-needs>=6.0.1; extra == "sphinx"',
    'pytest>=7.0; extra == "pytest"',
    'pytest>=7.0; extra == "test"',
]

AT_THE_FLOORS = {"sphinx": "7.4.7", "sphinx-needs": "6.0.1"}

VIOLATION = "sphinx-needs 5.1.0 is installed, but sphinx-needs>=6.0.1 is required"


def _environment(monkeypatch, installed, declared=DECLARED):
    """Fake the metadata: what this package declares and what is installed."""

    def requires(name):
        assert name == toolchain.DISTRIBUTION
        return declared

    def version(name):
        try:
            return installed[name]
        except KeyError:
            raise PackageNotFoundError(name) from None

    monkeypatch.setattr(toolchain, "requires", requires)
    monkeypatch.setattr(toolchain, "version", version)


class TestUnmetRequirements:
    def test_a_toolchain_at_the_floors_is_accepted(self, monkeypatch):
        _environment(monkeypatch, AT_THE_FLOORS)
        assert toolchain.unmet_requirements() == []

    def test_a_version_below_the_floor_is_named_with_the_floor(self, monkeypatch):
        _environment(monkeypatch, {**AT_THE_FLOORS, "sphinx-needs": "5.1.0"})
        assert toolchain.unmet_requirements() == [VIOLATION]

    def test_every_violation_is_reported_in_declaration_order(self, monkeypatch):
        _environment(monkeypatch, {"sphinx": "7.3.7", "sphinx-needs": "5.1.0"})
        assert toolchain.unmet_requirements() == [
            "sphinx 7.3.7 is installed, but sphinx>=7.4 is required",
            VIOLATION,
        ]

    def test_a_missing_distribution_is_left_to_the_import(self, monkeypatch):
        # The import that fails on a missing package states the problem more
        # precisely -- and a toolchain importable from a source tree without
        # metadata must not be refused on the strength of the metadata alone.
        _environment(monkeypatch, {"sphinx": "7.4.7"})
        assert toolchain.unmet_requirements() == []

    def test_other_extras_and_the_core_dependency_are_not_checked(self, monkeypatch):
        _environment(monkeypatch, {**AT_THE_FLOORS, "lxml": "0.1", "pytest": "1.0"})
        assert toolchain.unmet_requirements() == []

    def test_a_prerelease_above_the_floor_is_accepted(self, monkeypatch):
        _environment(monkeypatch, {**AT_THE_FLOORS, "sphinx-needs": "9.0.0rc1"})
        assert toolchain.unmet_requirements() == []

    def test_without_our_own_metadata_there_is_nothing_to_check(self, monkeypatch):
        # Run from a source tree on sys.path, the package has no metadata.
        def requires(name):
            raise PackageNotFoundError(name)

        monkeypatch.setattr(toolchain, "requires", requires)
        assert toolchain.unmet_requirements() == []

    def test_without_packaging_the_check_is_skipped(self, monkeypatch):
        # `packaging` is not a dependency of this package: it arrives with
        # Sphinx (and with pytest). Where neither is installed, nothing loads
        # the extension either -- so the check stands down instead of failing
        # on its own import.
        _environment(monkeypatch, {"sphinx": "7.3.7", "sphinx-needs": "5.1.0"})
        monkeypatch.setitem(sys.modules, "packaging.requirements", None)
        assert toolchain.unmet_requirements() == []

    def test_the_installed_metadata_declares_the_toolchain_under_the_extra(self):
        # Against the real metadata: the extra the check reads is the one
        # pyproject.toml declares. Renaming it there would silently disarm the
        # check, and this test.
        names = sorted(
            requirement.name for requirement in toolchain.toolchain_requirements()
        )
        assert names == ["sphinx", "sphinx-needs"]

    def test_this_environment_meets_the_floors(self):
        assert toolchain.unmet_requirements() == []


@pytest.mark.toolchain
class TestLazySetup:
    """Sphinx resolves ``setup`` through getattr(); the check runs first."""

    def test_a_sufficient_toolchain_resolves_setup(self):
        from sphinxcontrib.test_reports.test_reports import setup

        assert package.setup is setup

    def test_a_toolchain_below_the_floors_is_an_extension_error(self, monkeypatch):
        from sphinx.errors import ExtensionError

        monkeypatch.setattr(toolchain, "unmet_requirements", lambda: [VIOLATION])
        with pytest.raises(ExtensionError) as info:
            _ = package.setup
        message = str(info.value)
        assert message.startswith("Could not load extension sphinxcontrib.test_reports")
        assert VIOLATION in message
        assert toolchain.INSTALL_HINT in message
        # Nothing was imported, so there is no exception to wrap; the message
        # must not end in an empty "(exception: ...)".
        assert "(exception:" not in message

    def test_sphinx_surfaces_the_error_when_loading_the_extension(
        self, tmp_path, monkeypatch
    ):
        # Sphinx fetches `setup` with getattr(module, "setup", None), which
        # only swallows AttributeError. The error must reach the user as the
        # extension error it is, install line included -- not as "extension
        # has no setup() function".
        from sphinx.application import Sphinx
        from sphinx.errors import ExtensionError

        monkeypatch.setattr(toolchain, "unmet_requirements", lambda: [VIOLATION])
        (tmp_path / "conf.py").write_text(
            'extensions = ["sphinxcontrib.test_reports"]\n', encoding="utf-8"
        )
        (tmp_path / "index.rst").write_text("Index\n=====\n", encoding="utf-8")
        with pytest.raises(ExtensionError, match=r"sphinx-test-reports\[sphinx\]"):
            Sphinx(
                srcdir=tmp_path,
                confdir=tmp_path,
                outdir=tmp_path / "_build",
                doctreedir=tmp_path / "_doctrees",
                buildername="html",
                status=None,
                warning=StringIO(),
            )
