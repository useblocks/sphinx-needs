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
import re
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
            {**GOOD_LINK, "options": {"ticket": True}},
            "'options' must be a list of strings",
            id="options-as-mapping",
        ),
        pytest.param(
            {**GOOD_LINK, "options": ["ticket", 7]},
            "'options' must be a list of strings",
            id="options-not-all-strings",
        ),
        pytest.param(
            {**GOOD_LINK, "regex": 42},
            "'regex' must be a string or a compiled pattern",
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


@pytest.mark.parametrize(
    "value",
    [
        pytest.param([GOOD_LINK], id="non-empty-list"),
        pytest.param([1], id="list-of-junk"),
        pytest.param([], id="empty-list"),
        pytest.param("", id="empty-string"),
        pytest.param(0, id="zero"),
    ],
)
def test_string_links_not_a_dict_warns(
    value: Any, make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """``needs_string_links`` itself being the wrong type must not crash the build.

    The *falsy* spellings are the interesting ones: ``[]`` is a plausible typo for
    ``{}``, and it used to slip past the emptiness check unvalidated and then die on
    ``.items()`` inside the renderer.
    """
    app = build(make_app, sphinx_test_tempdir, value)

    warnings = warnings_of(app)
    assert "needs_string_links must be a dict" in warnings, warnings
    assert "needs.string_link" in warnings, warnings
    assert app.config.needs_string_links == {}
    # the build still produced a page
    assert "SLINK_1" in need_html(app)


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


@pytest.mark.parametrize(
    "options",
    [
        pytest.param(("ticket",), id="tuple"),
        pytest.param({"ticket"}, id="set"),
        pytest.param(frozenset({"ticket"}), id="frozenset"),
    ],
)
def test_options_collection_spellings_are_accepted(
    options: Any, make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """``options`` is only ever membership-tested, so any collection of strings works.

    All three spellings render links on the unvalidated code, so rejecting them would
    have been silent link loss on a configuration that was already correct.
    """
    app = build(
        make_app,
        sphinx_test_tempdir,
        {"good": {**GOOD_LINK, "options": options}},
    )
    assert warnings_of(app) == "", warnings_of(app)
    assert 'href="https://tracker.example.com/AB-1"' in need_html(app)
    # normalised to plain data for the rebound configuration
    assert app.config.needs_string_links["good"]["options"] == ["ticket"]


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        pytest.param(
            're.compile(r"^(?P<value>[A-Z]+-\\d+)$")', "AB-1", id="compiled-pattern"
        ),
        pytest.param(
            're.compile(r"^(?P<value>[a-z]+-\\d+)$", re.IGNORECASE)',
            "AB-1",
            id="compiled-pattern-with-flags",
        ),
    ],
)
def test_regex_accepts_a_compiled_pattern(
    pattern: str, expected: str, make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """``re.compile`` is idempotent, so a pre-compiled pattern works -- flags and all.

    The ``re.IGNORECASE`` case is the one that pins flag preservation: the pattern is
    lower-case only, and the value is upper-case.
    """
    from tests.conftest import create_src_files_in_tmpdir

    conf = (
        CONF_HEAD
        + "needs_string_links = {'good': {\n"
        + f"    'regex': {pattern},\n"
        + "    'link_url': 'https://tracker.example.com/{{value}}',\n"
        + "    'link_name': 'T:{{value}}',\n"
        + "    'options': ['ticket'],\n"
        + "}}\n"
    )
    srcdir = create_src_files_in_tmpdir(
        [(Path("conf.py"), conf), (Path("index.rst"), INDEX)], sphinx_test_tempdir
    )
    app = make_app(srcdir=srcdir, buildername="html")
    app.build()

    assert warnings_of(app) == "", warnings_of(app)
    assert f'href="https://tracker.example.com/{expected}"' in need_html(app)


def test_empty_options_warns_but_keeps_the_entry(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """An entry with no fields to apply to is a silent no-op worth naming."""
    app = build(
        make_app,
        sphinx_test_tempdir,
        {"t": {**GOOD_LINK, "options": []}},
    )
    warnings = warnings_of(app)
    assert "'options' is empty, so this entry can never apply." in warnings, warnings
    assert "needs.string_link" in warnings, warnings
    # warn only -- the entry is kept
    assert app.config.needs_string_links["t"]["options"] == []


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


def test_unknown_key_warns_but_keeps_the_entry(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """A misspelled key was swallowed in silence, leaving a working-but-wrong link.

    The entry is kept, so nobody's links vanish over a stray key.
    """
    app = build(
        make_app,
        sphinx_test_tempdir,
        {"t": {**GOOD_LINK, "link_naem": "typo"}},
    )
    warnings = warnings_of(app)
    assert "unknown key(s) 'link_naem'" in warnings, warnings
    assert "needs.string_link" in warnings, warnings
    assert 'href="https://tracker.example.com/AB-1"' in need_html(app)


def test_undeclared_field_in_options_warns(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """``options`` naming a field that is not registered can never match."""
    app = build(
        make_app,
        sphinx_test_tempdir,
        {"t": {**GOOD_LINK, "options": ["ticket", "no_such_field"]}},
    )
    warnings = warnings_of(app)
    assert "'options' names 'no_such_field'" in warnings, warnings
    assert "not a registered need field" in warnings, warnings
    # warn only: the entry is still applied to the field that *is* registered
    assert 'href="https://tracker.example.com/AB-1"' in need_html(app)


def test_core_fields_are_accepted_in_options(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """A core field is a legitimate string-link target, and must not warn."""
    app = build(
        make_app,
        sphinx_test_tempdir,
        {
            "t": {
                "regex": r"^(?P<value>\w+)$",
                "link_url": "https://s.example.com/{{value}}",
                "link_name": "S:{{value}}",
                "options": ["status"],
            }
        },
    )
    assert warnings_of(app) == "", warnings_of(app)


SEPARATOR_INDEX = """\
String links
============

.. req:: A need
   :id: SLINK_1
   :ticket: AB-1
   :tickets: AB-1, AB-2; AB-3
   :other: Q

   Body.
"""


@pytest.mark.parametrize(
    ("field", "items"),
    [
        pytest.param("ticket", 1, id="one-item"),
        pytest.param("tickets", 3, id="three-items"),
        pytest.param("other", 1, id="one-character-value"),
    ],
)
def test_separators_go_between_items(
    field: str, items: int, make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """N items produce N-1 separators in the meta area, as they do in a needtable.

    The condition read ``len(data)`` -- a character count of the whole value --
    so every item got a trailing separator, except when the value was a single
    character, which got none at all.
    """
    app = build(
        make_app,
        sphinx_test_tempdir,
        {"t": {**GOOD_LINK, "options": ["ticket", "tickets", "other"]}},
        index=SEPARATOR_INDEX,
    )
    meta = _meta_span(need_html(app), field)
    assert meta.count("<em>; </em>") == items - 1, meta


LIST_INDEX = """\
String links
============

.. req:: A need
   :id: SLINK_1
   :mylist: XX-1, XX-2
   :tags: alpha, beta

   Body.

.. needtable::
   :columns: id;mylist
   :style: table
"""


@pytest.mark.parametrize("field", ["mylist", "tags"])
def test_list_fields_are_linked_in_the_meta_area(
    field: str, make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """A list field links element by element, as it already did in a needtable.

    The meta area's list branch never consulted the string links, so the same
    field linked in a table but rendered as plain text in the need itself.
    """
    app = build(
        make_app,
        sphinx_test_tempdir,
        {
            "t": {
                "regex": r"^(?P<value>.+)$",
                "link_url": "https://list.example.com/{{value}}",
                "link_name": "L:{{value}}",
                "options": [field],
            }
        },
        index=LIST_INDEX,
    )
    meta = _meta_span(need_html(app), field)
    assert meta.count("<a ") == 2, meta
    assert 'class="needs_spacer"' in meta, meta


def test_list_field_agrees_between_meta_and_needtable(
    make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """The two surfaces produce the same links for the same list field."""
    app = build(
        make_app,
        sphinx_test_tempdir,
        {
            "t": {
                "regex": r"^(?P<value>.+)$",
                "link_url": "https://list.example.com/{{value}}",
                "link_name": "L:{{value}}",
                "options": ["mylist"],
            }
        },
        index=LIST_INDEX,
    )
    html = need_html(app)
    for item in ("XX-1", "XX-2"):
        href = f'href="https://list.example.com/{item}">L:{item}</a>'
        # once in the need's meta area, once in the needtable cell
        assert html.count(href) == 2, html
