"""What sphinx-needs derives for one build stays out of Sphinx's configuration.

Two values are derived at the start of every build and read by its filters: the ``var``
proxy over the variant data, and the need types as ``c.is_a`` reads them (each with
itself and every type inheriting from it). They are kept in sphinx-needs' own registry,
reset with it whenever the extension is set up, and read through
:class:`~sphinx_needs.config.NeedsSphinxConfig` (``variant_data_proxy``,
``is_a_types``), which cannot write them. Sphinx's ``Config`` holds the declared
options alone: a ``needs_*`` name that is not one is a value a project's ``conf.py``
could set, which no reader finds among the options, and which Sphinx pickles with the
environment (#2402, #1840).
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import NeedsApiConfigException
from sphinx_needs_testkit import assert_no_warnings

#: a project whose build derives both values: variant data, and a type inheriting
CONF = """\
extensions = ["sphinx_needs"]
needs_variant_data = {"platform": "arm"}
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_"},
    {
        "directive": "sys_req",
        "title": "System requirement",
        "prefix": "SR_",
        "inherits": "req",
    },
    {"directive": "spec", "title": "Specification", "prefix": "S_"},
]
"""

INDEX = """\
Case
====

.. req:: A requirement
   :id: R_001

.. sys_req:: A system requirement
   :id: SR_001

.. spec:: A specification
   :id: S_001

.. needextend:: "c.is_a('req') and var.platform == 'arm'"
   :+tags: selected
"""

#: a project of the default types, without variant data
PLAIN_CONF = 'extensions = ["sphinx_needs"]\n'


def _write(srcdir: Path, conf: str) -> Path:
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(conf, encoding="utf-8")
    (srcdir / "index.rst").write_text(INDEX, encoding="utf-8")
    return srcdir


def _undeclared_needs_values(config: Any) -> list[str]:
    """The ``needs_*`` attributes of a Sphinx configuration that are no declared value.

    ``name in config`` asks Sphinx for its declared values, Sphinx's own
    ``needs_sphinx`` and ``needs_extensions`` included, which share the prefix.
    """
    return sorted(k for k in vars(config) if k.startswith("needs_") and k not in config)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), INDEX)],
        }
    ],
    indirect=True,
)
def test_a_build_writes_no_undeclared_configuration_value(test_app: Any) -> None:
    """After a build whose filters read both values, Sphinx's configuration holds the
    declared ``needs_*`` options alone, and the values are read where they are kept."""
    app = test_app
    app.build()
    assert_no_warnings(app)
    view = SphinxNeedsData(app.env).get_needs_view()
    assert sorted(i for i, need in view.items() if "selected" in need["tags"]) == [
        "R_001",
        "SR_001",
    ]
    assert _undeclared_needs_values(app.config) == []
    config = NeedsSphinxConfig(app.config)
    assert config.variant_data_proxy is not None
    assert config.is_a_types is not None
    assert dict(config.is_a_types) == {
        "req": frozenset({"req", "sys_req"}),
        "sys_req": frozenset({"sys_req"}),
        "spec": frozenset({"spec"}),
    }


def test_an_application_reads_no_build_data_until_it_builds(
    make_app: Any, tmp_path: Path
) -> None:
    """The values are one build's: an application set up after another was built, and
    not built itself, reads neither, whatever the earlier build derived."""
    built = make_app(
        srcdir=_write(tmp_path / "built", CONF),
        buildername="needs",
        freshenv=True,
        warning=io.StringIO(),
    )
    built.build()
    assert NeedsSphinxConfig(built.config).is_a_types is not None
    fresh = make_app(
        srcdir=_write(tmp_path / "fresh", PLAIN_CONF),
        buildername="needs",
        freshenv=True,
        warning=io.StringIO(),
    )
    config = NeedsSphinxConfig(fresh.config)
    assert config.is_a_types is None
    assert config.variant_data_proxy is None


@pytest.mark.parametrize("name", ["variant_data_proxy", "is_a_types"])
def test_the_build_data_cannot_be_written_through_the_configuration(
    name: str, make_app: Any, tmp_path: Path
) -> None:
    """Each is derived from the configuration at the start of a build, so a write
    through the configuration would reach nothing the next build reads."""
    app = make_app(
        srcdir=_write(tmp_path / "src", PLAIN_CONF),
        buildername="needs",
        freshenv=True,
        warning=io.StringIO(),
    )
    with pytest.raises(NeedsApiConfigException, match=f"NeedsSphinxConfig.{name} "):
        setattr(NeedsSphinxConfig(app.config), name, None)
