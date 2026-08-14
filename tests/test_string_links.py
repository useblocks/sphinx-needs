"""Tests for ``needs_string_links``.

The configuration is validated and compiled during ``config-inited``, so the
tests come in three flavours:

* validation tests proving that an unusable configuration is skipped with a
  ``needs.string_link`` warning, instead of aborting the build,
* rendering tests pinning the semantics of a *valid* configuration
  (splitting, first-entry-wins, non-matching fallback, ...),
* regression tests for the specific rendering bugs fixed alongside.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from sphinx.util.console import strip_colors

INDEX = """\
String links
============

.. req:: A need
   :id: SLINK_1
   :ticket: AB-1

   Body.
"""

CONF_HEAD = """\
extensions = ['sphinx_needs']
needs_fields = {
    'ticket': {'nullable': True},
    'tickets': {'nullable': True},
    'other': {'nullable': True},
    'mylist': {'schema': {'type': 'array', 'items': {'type': 'string'}}},
}
"""

GOOD_LINK = {
    "regex": r"^(?P<value>[A-Z]+-\d+)$",
    "link_url": "https://tracker.example.com/{{value}}",
    "link_name": "T:{{value}}",
    "options": ["ticket"],
}


def conf_py(string_links: Any, extra: str = "") -> str:
    """Build a ``conf.py`` declaring the given ``needs_string_links``."""
    return f"{CONF_HEAD}needs_string_links = {string_links!r}\n{extra}\n"


def build(
    make_app: Any,
    tempdir: Any,
    string_links: Any,
    *,
    index: str = INDEX,
    extra: str = "",
) -> Any:
    """Build a one-page project with the given ``needs_string_links``."""
    from tests.conftest import create_src_files_in_tmpdir

    srcdir = create_src_files_in_tmpdir(
        [
            (Path("conf.py"), conf_py(string_links, extra)),
            (Path("index.rst"), index),
        ],
        tempdir,
    )
    app = make_app(srcdir=srcdir, buildername="html")
    app.build()
    return app


def need_html(app: Any) -> str:
    """The rendered ``index.html`` of a built project."""
    return (Path(app.outdir) / "index.html").read_text()


def warnings_of(app: Any) -> str:
    """Every warning the build emitted, as one string."""
    return strip_colors(app._warning.getvalue())


def _meta_span(html: str, field: str) -> str:
    """Extract the meta-area markup of one field from a rendered page."""
    match = re.search(
        rf'<span class="needs_{field}">.*?</span></span>', html, flags=re.DOTALL
    )
    assert match is not None, f"no meta area for {field!r} in\n{html}"
    return match.group(0)


# --------------------------------------------------------------------------
# validation: an unusable configuration is a warning, not a crash
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bad_conf", "expected"),
    [
        pytest.param(
            {k: v for k, v in GOOD_LINK.items() if k != "regex"},
            "missing required key(s) 'regex'",
            id="missing-regex",
        ),
        pytest.param(
            {k: v for k, v in GOOD_LINK.items() if k != "link_url"},
            "missing required key(s) 'link_url'",
            id="missing-link_url",
        ),
        pytest.param(
            {k: v for k, v in GOOD_LINK.items() if k != "link_name"},
            "missing required key(s) 'link_name'",
            id="missing-link_name",
        ),
        pytest.param(
            {k: v for k, v in GOOD_LINK.items() if k != "options"},
            "missing required key(s) 'options'",
            id="missing-options",
        ),
        pytest.param({}, "missing required key(s) ", id="empty-conf"),
        pytest.param(
            {**GOOD_LINK, "regex": r"^[a-\d]+$"},
            "'regex' is not a valid regular expression",
            id="bad-regex",
        ),
        pytest.param(
            {**GOOD_LINK, "link_url": "https://x/{{ unclosed "},
            "'link_url' is not a valid template",
            id="bad-url-template",
        ),
        pytest.param(
            {**GOOD_LINK, "link_name": "{% for %}"},
            "'link_name' is not a valid template",
            id="bad-name-template",
        ),
        pytest.param("not-a-dict", "must be a dict", id="conf-not-a-dict"),
        pytest.param(
            {**GOOD_LINK, "options": "ticket"},
            "'options' must be a list of strings",
            id="options-as-string",
        ),
        pytest.param(
            {**GOOD_LINK, "options": ["ticket", 7]},
            "'options' must be a list of strings",
            id="options-not-all-strings",
        ),
        pytest.param(
            {**GOOD_LINK, "regex": 42},
            "'regex' must be a string",
            id="regex-not-a-string",
        ),
    ],
)
def test_invalid_conf_warns_but_the_build_survives(
    bad_conf: Any, expected: str, make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """A bad entry is skipped: the build succeeds and its siblings still work.

    Every case here aborted the build with an uncaught exception before
    the configuration was validated at ``config-inited``.
    """
    app = build(
        make_app,
        sphinx_test_tempdir,
        {"bad": bad_conf, "good": GOOD_LINK},
    )

    warnings = warnings_of(app)
    assert "needs_string_links['bad']" in warnings, warnings
    assert expected in warnings, warnings
    assert "needs.string_link" in warnings, warnings
    assert "needs_string_links['good']" not in warnings, warnings

    # the sibling entry still compiled and rendered
    assert 'href="https://tracker.example.com/AB-1"' in need_html(app)


def test_string_links_not_a_dict_warns(make_app: Any, sphinx_test_tempdir: Any) -> None:
    """``needs_string_links`` itself being the wrong type must not crash the build."""
    app = build(make_app, sphinx_test_tempdir, [GOOD_LINK])

    warnings = warnings_of(app)
    assert "needs_string_links must be a dict" in warnings, warnings
    assert "AB-1" in need_html(app)


def test_invalid_conf_is_pruned_from_the_config(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """A skipped entry is removed, so no renderer can trip over it later."""
    app = build(
        make_app,
        sphinx_test_tempdir,
        {"bad": {"link_url": "x", "link_name": "y", "options": ["ticket"]}},
    )
    assert app.config.needs_string_links == {}


def test_valid_config_object_survives_a_build(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """A wholly valid configuration is left exactly as the user wrote it."""
    app = build(make_app, sphinx_test_tempdir, {"good": GOOD_LINK})
    assert app.config.needs_string_links == {"good": GOOD_LINK}
    assert warnings_of(app) == "", warnings_of(app)


def test_options_as_tuple_is_accepted(make_app: Any, sphinx_test_tempdir: Any) -> None:
    """A tuple is a legitimate spelling of a list, and worked before validation."""
    app = build(
        make_app,
        sphinx_test_tempdir,
        {"good": {**GOOD_LINK, "options": ("ticket",)}},
    )
    assert warnings_of(app) == "", warnings_of(app)
    assert 'href="https://tracker.example.com/AB-1"' in need_html(app)


def test_unused_broken_conf_still_only_warns(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """A broken entry naming a field no need uses used to kill the build anyway."""
    app = build(
        make_app,
        sphinx_test_tempdir,
        {
            "bad": {
                "regex": "(",
                "link_url": "u",
                "link_name": "n",
                "options": ["other"],
            }
        },
    )
    assert "needs_string_links['bad']" in warnings_of(app)
    assert "SLINK_1" in need_html(app)


# --------------------------------------------------------------------------
# rendering: the semantics of a valid configuration
# --------------------------------------------------------------------------

MULTI_INDEX = """\
String links
============

.. req:: A need
   :id: SLINK_1
   :ticket: AB-1
   :tickets: AB-1, AB-2; AB-3
   :other: totally-not-matching

   Body.
"""


def test_single_value_renders_one_link(make_app: Any, sphinx_test_tempdir: Any) -> None:
    """The happy path: a fully matched value becomes a single link."""
    app = build(make_app, sphinx_test_tempdir, {"t": GOOD_LINK})
    assert warnings_of(app) == "", warnings_of(app)
    assert (
        '<a class="reference external" href="https://tracker.example.com/AB-1">'
        "T:AB-1</a>" in need_html(app)
    )


def test_multi_item_value_is_split_and_linked(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """A field named in ``options`` is split on ``,`` and ``;``, and stripped."""
    app = build(
        make_app,
        sphinx_test_tempdir,
        {"t": {**GOOD_LINK, "options": ["tickets"]}},
        index=MULTI_INDEX,
    )
    html = need_html(app)
    for number in ("AB-1", "AB-2", "AB-3"):
        assert f'href="https://tracker.example.com/{number}">T:{number}</a>' in html


def test_non_matching_value_falls_back_to_text(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """A value the regex does not match renders as plain text, silently."""
    app = build(
        make_app,
        sphinx_test_tempdir,
        {"t": {**GOOD_LINK, "options": ["other"]}},
        index=MULTI_INDEX,
    )
    assert warnings_of(app) == "", warnings_of(app)
    html = need_html(app)
    assert "totally-not-matching" in html
    assert "tracker.example.com/totally" not in html


def test_named_groups_and_filters(make_app: Any, sphinx_test_tempdir: Any) -> None:
    """All named groups reach both templates, and template filters work."""
    app = build(
        make_app,
        sphinx_test_tempdir,
        {
            "t": {
                "regex": r"^(?P<tool>[A-Z]+)-(?P<num>\d+)$",
                "link_url": "https://{{tool | lower}}.example.com/{{num}}",
                "link_name": "{{tool}} number {{num}}",
                "options": ["ticket"],
            }
        },
    )
    assert (
        '<a class="reference external" href="https://ab.example.com/1">'
        "AB number 1</a>" in need_html(app)
    )


def test_first_matching_conf_wins(make_app: Any, sphinx_test_tempdir: Any) -> None:
    """Only the first entry naming the field is consulted -- there is no fallthrough."""
    app = build(
        make_app,
        sphinx_test_tempdir,
        {
            "first": {**GOOD_LINK, "link_name": "FIRST {{value}}"},
            "second": {**GOOD_LINK, "link_name": "SECOND {{value}}"},
        },
    )
    html = need_html(app)
    assert "FIRST AB-1" in html
    assert "SECOND" not in html


def test_first_conf_blocks_a_matching_second_one(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """A non-matching first entry is *not* followed by the second one."""
    app = build(
        make_app,
        sphinx_test_tempdir,
        {
            "first": {**GOOD_LINK, "regex": "^WILL-NEVER-MATCH$"},
            "second": GOOD_LINK,
        },
    )
    html = need_html(app)
    assert "tracker.example.com" not in html
    assert "AB-1" in html


def test_render_context_shadows_capture_groups(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """``needs_render_context`` wins over a same-named capture group."""
    app = build(
        make_app,
        sphinx_test_tempdir,
        {"t": GOOD_LINK},
        extra="needs_render_context = {'value': 'CLOBBER'}\n",
    )
    assert 'href="https://tracker.example.com/CLOBBER"' in need_html(app)


# --------------------------------------------------------------------------
# regressions
# --------------------------------------------------------------------------


def test_template_failure_keeps_the_value(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """A template that fails at *render* time must not eat the field value.

    An unknown filter only fails once it is rendered, so it escapes the
    configuration-time check. The value used to vanish from the page entirely.
    """
    app = build(
        make_app,
        sphinx_test_tempdir,
        {"t": {**GOOD_LINK, "link_name": "{{value | no_such_filter}}"}},
    )
    warnings = warnings_of(app)
    assert "Problems dealing with string to link transformation" in warnings
    # and the warning now says where, rather than only which field
    assert "index.rst:" in warnings, warnings

    meta = _meta_span(need_html(app), "ticket")
    assert "AB-1" in meta, meta
    assert "<a " not in meta, meta


BLANK_INDEX = """\
String links
============

.. req:: A need
   :id: SLINK_1
   :tickets: AB-1, , AB-2

   Body.
"""


def test_whitespace_only_items_are_dropped(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """``AB-1, , AB-2`` is two items, not three.

    The emptiness test ran on the *unstripped* item, so a whitespace-only
    item survived it and then stripped to nothing, rendering as a phantom
    item between two separators.
    """
    app = build(
        make_app,
        sphinx_test_tempdir,
        {"t": {**GOOD_LINK, "options": ["tickets"]}},
        index=BLANK_INDEX,
    )
    meta = _meta_span(need_html(app), "tickets")
    assert meta.count("<a ") == 2, meta
    assert "<em>; </em><em>; </em>" not in meta, meta
