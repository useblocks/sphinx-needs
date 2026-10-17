"""An incremental build compares an unchanged configuration (sphinx-needs #2265).

This extension adds its three need types with sphinx-needs' ``add_need_type`` from a
``config-inited`` handler. They are kept in sphinx-needs' own registry, as the need
types and layout of sphinx-needs' GitHub services are, and never written into
``needs_types`` or ``needs_layouts``: the configuration Sphinx compares with the one
pickled by the previous build is the same, and it names no changed option. The two
values used to differ on every build after the first, as the GitHub service appended
to them after Sphinx had compared the configurations.
"""

import pickle
import re
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors

import sphinx_needs.api
from sphinx_needs.api import get_need_types


@pytest.mark.skipif(
    not hasattr(sphinx_needs.api, "add_need_layout"),
    reason="the installed sphinx-needs predates its fix of #2265 (which added "
    "add_need_layout); the fix ships in the next sphinx-needs release",
)
@pytest.mark.parametrize(
    "extensions",
    [
        pytest.param(["sphinx_needs", "sphinx_test_reports"], id="sphinx-needs-first"),
        pytest.param(["sphinx_test_reports", "sphinx_needs"], id="test-reports-first"),
    ],
)
def test_an_incremental_build_changes_no_configuration_option(
    make_app, tmp_path, clean_docutils_registry, extensions
):
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(f"extensions = {extensions!r}\n", encoding="utf-8")
    (srcdir / "index.rst").write_text("Probe\n=====\n", encoding="utf-8")

    first = make_app("html", srcdir=srcdir, freshenv=True)
    first.build()
    old_env = pickle.loads(Path(first.doctreedir, "environment.pickle").read_bytes())
    types = ["testfile", "testsuite", "testcase"]
    assert all(name in get_need_types(first) for name in types)
    assert not any(entry["directive"] in types for entry in first.config.needs_types)

    second = make_app("html", srcdir=srcdir)
    old_values = {item.name: item.value for item in old_env.config}
    new_values = {item.name: item.value for item in second.config}
    assert {
        name
        for name in old_values.keys() | new_values.keys()
        if old_values.get(name) != new_values.get(name)
    } == set()
    second.build()
    # Sphinx 8 and later name the changed options in a status line; Sphinx 7 does not.
    # ``html_theme`` is among them: ``SphinxTestApp`` sets it to ``basic`` only after
    # Sphinx has compared the configurations, and the first build pickled ``basic``
    reported = re.search(
        r"The configuration has changed \(\d+ options?: (.*)\)",
        strip_colors(second._status.getvalue()),
    )
    assert reported is None or re.findall(r"'(needs_[^']+)'", reported.group(1)) == []
