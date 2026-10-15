"""Either order of the two extensions registers each need directive once (#2271).

sphinx-test-reports adds its three need types with ``add_need_type`` from a
``config-inited`` handler at the default priority, as sphinx-needs' ``load_config``
registers the configured ones, so the order of ``extensions`` decides which runs first.
Listing this extension first used to register ``testfile``, ``testsuite`` and
``testcase`` twice, with one ``already registered`` warning each.
"""

import pytest

from sphinx_needs.data import SphinxNeedsData


@pytest.mark.parametrize(
    "extensions",
    [
        pytest.param(["sphinx_needs", "sphinx_test_reports"], id="sphinx-needs-first"),
        pytest.param(["sphinx_test_reports", "sphinx_needs"], id="test-reports-first"),
    ],
)
def test_either_order_registers_each_need_directive_once(build_page, extensions):
    app, stream = build_page(
        ".. testfile:: A test file\n   :id: TF_00001\n",
        conf=f"extensions = {extensions!r}\n",
    )
    assert "already registered" not in stream
    assert stream == ""
    assert list(SphinxNeedsData(app.env).get_needs_view()) == ["TF_00001"]
