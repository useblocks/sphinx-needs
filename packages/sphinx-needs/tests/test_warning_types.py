"""The ``[needs.<subtype>]`` suffix of a warning is rendered exactly once (#2091).

Sphinx appends `` [type.subtype]`` to a typed warning itself when ``show_warning_types``
is on: the option exists since Sphinx 7.3 (default ``False``) and defaults to ``True``
since 8.0. Before 8.0 sphinx-needs appends the suffix itself, so it must do so only when
Sphinx will not -- on 7.4 with the option on, both appended it.
"""

import re
from pathlib import Path
from typing import Any

import pytest
from sphinx import version_info
from sphinx.testing.util import SphinxTestApp

from sphinx_needs import logging as needs_logging
from sphinx_needs_testkit import build_warnings

CONF = 'extensions = ["sphinx_needs"]\n'

INDEX = """\
Test
====

.. req:: A
   :id: REQ_1
   :links: REQ_MISSING
"""


def _suffixes(app: SphinxTestApp, marker: str = "REQ_MISSING") -> list[list[str]]:
    """The ``[needs.*]`` bracket groups of each warning containing ``marker`` (by
    default, the one naming the dangling link)."""
    lines = [w for w in build_warnings(app) if marker in w]
    assert len(lines) == 1, build_warnings(app)
    return [re.findall(r"\[needs\.[a-z_]+\]", line) for line in lines]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), INDEX)],
            "confoverrides": {"show_warning_types": True},
        }
    ],
    indirect=True,
)
def test_suffix_once_when_sphinx_shows_warning_types(test_app: SphinxTestApp):
    """With ``show_warning_types = True`` Sphinx renders the suffix on every version
    (7.4 included), so sphinx-needs adds none: exactly one ``[needs.link_outgoing]``."""
    test_app.build()
    assert _suffixes(test_app) == [["[needs.link_outgoing]"]]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), INDEX)],
            "confoverrides": {"show_warning_types": False},
        }
    ],
    indirect=True,
)
def test_suffix_per_version_when_sphinx_hides_warning_types(test_app: SphinxTestApp):
    """With ``show_warning_types = False`` the expectation depends on the version:
    before Sphinx 8 sphinx-needs appends the suffix itself (once); from 8 on it never
    appends and Sphinx renders nothing, so the line carries no suffix at all."""
    test_app.build()
    expected = ["[needs.link_outgoing]"] if version_info < (8,) else []
    assert _suffixes(test_app) == [expected]


#: a ``conf.py`` whose ``setup()`` registers one dynamic function twice: the second
#: registration warns ``needs.config`` while the extensions are being set up, before
#: ``config-inited``
CONF_SETUP_WARNING = """\
from sphinx_needs.api import add_dynamic_function

extensions = ["sphinx_needs"]


def suffix_probe_function(app, need, needs):
    return "x"


def setup(app):
    add_dynamic_function(app, suffix_probe_function)
    add_dynamic_function(app, suffix_probe_function)
"""

#: ``needs_from_toml`` names a file that does not exist: ``needs.config``, warned by
#: the first sphinx-needs handler of ``config-inited``
CONF_TOML_WARNING = 'extensions = ["sphinx_needs"]\nneeds_from_toml = "missing.toml"\n'


@pytest.mark.parametrize(
    ("test_app", "marker"),
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), CONF_SETUP_WARNING),
                    (Path("index.rst"), INDEX),
                ],
                "confoverrides": {"show_warning_types": True},
            },
            "Dynamic function suffix_probe_function already registered",
            id="at-setup",
        ),
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), CONF_TOML_WARNING),
                    (Path("index.rst"), INDEX),
                ],
                "confoverrides": {"show_warning_types": True},
            },
            "'needs_from_toml' file does not exist",
            id="at-config-inited",
        ),
    ],
    indirect=["test_app"],
)
def test_suffix_once_for_a_warning_before_the_documents_are_read(
    test_app: SphinxTestApp, marker: str
):
    """A warning emitted while the extensions are set up (the public API called from a
    ``setup()``), or while the configuration is loaded (the first ``config-inited``
    handler), carries ``[needs.config]`` once with ``show_warning_types = True``: the
    helpers learn the option before anything that can warn runs."""
    test_app.build()
    assert _suffixes(test_app, marker) == [["[needs.config]"]]


class _StubLogger:
    """Records what the helpers hand the Sphinx logger adapter."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def warning(self, msg: str, **kwargs: Any) -> None:
        self.calls.append(("warning", msg, kwargs))

    def error(self, msg: str, **kwargs: Any) -> None:
        self.calls.append(("error", msg, kwargs))


@pytest.mark.parametrize("helper", ["log_warning", "log_error"])
@pytest.mark.parametrize("leave_to_sphinx", [True, False])
def test_helpers_append_the_suffix_only_when_sphinx_does_not(
    monkeypatch, helper: str, leave_to_sphinx: bool
):
    """``log_warning`` and ``log_error`` alike: the message is passed unchanged where
    the suffix is left to Sphinx, and carries it where it is not."""
    monkeypatch.setattr(needs_logging._warning_types, "sphinx_renders", leave_to_sphinx)
    stub = _StubLogger()
    getattr(needs_logging, helper)(stub, "a problem", "config", None)

    expected = "a problem" if leave_to_sphinx else "a problem [needs.config]"
    level = helper.removeprefix("log_")
    assert stub.calls == [
        (
            level,
            expected,
            {
                "type": "needs",
                "subtype": "config",
                "location": None,
                "color": None,
                "once": False,
            },
        )
    ]
