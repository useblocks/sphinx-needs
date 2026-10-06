"""``generate_need_id``: the id ``add_need`` derives for a need without one (#2084).

An extension that creates needs -- sphinx-codelinks, sphinx-test-reports -- must know
that id BEFORE it calls ``add_need``, to detect a second definition of the same generated
id. Each case is a real build: a directive calls ``generate_need_id`` and then
``add_need`` with the same inputs, and the id is read back off the need the build
created, through ``get_needs_view``.
"""

from __future__ import annotations

import textwrap
from typing import Any

import pytest
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import InvalidNeedException, generate_need_id, get_needs_view
from sphinx_needs.api.need import add_need
from sphinx_needs_testkit import assert_no_warnings

CONF = """\
    extensions = ["sphinx_needs"]
    needs_types = [
        {
            "directive": "spec",
            "title": "Specification",
            "prefix": "SP_",
            "color": "#FEDCD2",
            "style": "node",
        }
    ]
    """

RST = "Title\n=====\n\n.. probe::\n\n   First line.\n   Second line.\n"

#: stands for the directive's own ``self.content``, a docutils ``StringList`` -- what a
#: directive-based extension naturally passes as ``content``
DIRECTIVE_CONTENT = object()


@pytest.fixture
def probe(make_app, tmp_path):
    """Build a project whose one ``probe`` directive calls ``generate_need_id`` and
    then ``add_need`` with the same arguments; return the application and what each of
    the two calls gave (an id or a list of nodes, or the exception it raised)."""

    def _probe(inputs: dict[str, Any], confoverrides: dict[str, Any] | None = None):
        srcdir = tmp_path / "src"
        srcdir.mkdir()
        (srcdir / "conf.py").write_text(textwrap.dedent(CONF), encoding="utf-8")
        (srcdir / "index.rst").write_text(RST, encoding="utf-8")
        app = make_app(srcdir=srcdir, freshenv=True, confoverrides=confoverrides or {})
        record: dict[str, Any] = {}

        class Probe(SphinxDirective):
            has_content = True

            def run(self):
                given = inputs
                if given.get("content") is DIRECTIVE_CONTENT:
                    given = {**given, "content": self.content}
                try:
                    record["generated"] = generate_need_id(app, **given)
                except InvalidNeedException as exc:
                    record["generated"] = exc
                try:
                    return add_need(
                        app, self.state, self.env.docname, self.lineno, **given
                    )
                except InvalidNeedException as exc:
                    record["added"] = exc
                    return []

        app.add_directive("probe", Probe)
        app.build()
        return app, record

    return _probe


@pytest.mark.parametrize(
    ("inputs", "confoverrides"),
    [
        pytest.param({"need_type": "spec", "title": "A title"}, None, id="default"),
        pytest.param(
            {"need_type": "spec", "title": "A title"},
            {"needs_id_from_title": True},
            id="id-from-title",
        ),
        pytest.param(
            {"need_type": "spec", "title": "A title"},
            {"needs_id_length": 12},
            id="id-length-12",
        ),
        pytest.param(
            {"need_type": "spec", "title": "Tab\there, ümlaut and 漢字"},
            {"needs_id_from_title": True, "needs_id_length": 40},
            id="tab-and-non-ascii",
        ),
        pytest.param(
            {"need_type": "spec", "title": "", "content": "Only content."},
            None,
            id="content-with-empty-title",
        ),
        pytest.param(
            {"need_type": "spec", "title": "Short", "full_title": "The full title"},
            {"needs_id_from_title": True},
            id="full-title",
        ),
        pytest.param(
            {"need_type": "spec", "title": "", "content": ""},
            None,
            id="empty-title-and-content",
        ),
        # an empty full_title is given, so it is hashed -- or, being empty, the content
        pytest.param(
            {"need_type": "spec", "title": "T", "content": "C", "full_title": ""},
            None,
            id="empty-full-title",
        ),
        pytest.param(
            {"need_type": "spec", "title": "", "content": DIRECTIVE_CONTENT},
            None,
            id="string-list-content",
        ),
    ],
)
def test_generate_need_id_is_the_id_add_need_assigns(probe, inputs, confoverrides):
    """For each input the #2042 review checked, an empty ``full_title``, and the
    directive's own content (a ``StringList``), the helper returns the id of the need
    ``add_need`` then creates."""
    app, record = probe(inputs, confoverrides)
    assert "added" not in record, record.get("added")
    generated = record["generated"]
    assert isinstance(generated, str)
    assert list(get_needs_view(app)) == [generated]
    assert generated.startswith("SP_")
    assert_no_warnings(app)


def test_generate_need_id_of_an_unknown_type_raises_as_add_need_does(probe):
    """An unknown type is refused by both, with the same exception."""
    _app, record = probe({"need_type": "nope", "title": "A title"})
    generated, added = record["generated"], record["added"]
    assert isinstance(generated, InvalidNeedException)
    assert isinstance(added, InvalidNeedException)
    assert generated.type == added.type == "invalid_type"
    assert str(generated) == str(added) == "Unknown need type 'nope'. [invalid_type]"
