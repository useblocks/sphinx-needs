from pathlib import Path

import pytest

from sphinx_needs_testkit import build_warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_need_jinja_content"}],
    indirect=True,
)
def test_doc_need_jinja_content(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()

    # deprecated (removed in 10.0): one warning at each need rendering its body, none
    # for ``:jinja_content: false``
    deprecated = [w for w in build_warnings(app) if w.endswith("[needs.deprecated]")]
    assert deprecated, "the jinja_content option is deprecated"
    assert all("jinja_content option of need" in w for w in deprecated)
    assert all("{{ content }}" in w and "10.0" in w for w in deprecated)
    assert not any("'JINJAID123'" in w or "'JINJAID124'" in w for w in deprecated)

    assert "Nested Spec Need" in html
    assert "Jinja Content Not Implemented" in html
    assert "JINJAID125" in html
    assert "JINJAID126" in html
    assert (
        """<p>Nested need with <code class="docutils literal notranslate"><span class="pre">:jinja_content:</span></code> option set to <code class="docutils literal notranslate"><span class="pre">true</span></code>.
This requirement has tags: <strong>user, login</strong>.</p>
<p>It links to:</p>
<ul class="simple">
<li><p>JINJAID126</p></li>
</ul>"""
        in html
    )
    assert (
        """<p>Need with <code class="docutils literal notranslate"><span class="pre">:jinja_content:</span></code> equal to <code class="docutils literal notranslate"><span class="pre">true</span></code>.
This requirement has status: <strong>open</strong>.</p>"""
        in html
    )

    # Test for needs_render_context
    assert "JINJA1D8913" in html
    assert "Project_X" in html
    assert "Content from custom_defined_func." in html
    assert "Daniel - ID: 811982" in html
    assert "Marco - ID: 234232" in html
