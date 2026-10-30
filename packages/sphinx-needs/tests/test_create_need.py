"""``create_need`` and ``add_need``: the two doors of one creation path."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.api import add_need, create_need
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import InvalidNeedException
from sphinx_needs.need_item import NeedItemSourceExternal, NeedItemSourceUnknown
from sphinx_needs_testkit import build_warnings

DEPRECATED_KEY_EXT = '''\
"""Calls ``add_need`` with a deprecated key, and keeps what it warned."""

import warnings

from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import add_need


class DeprecatedKey(SphinxDirective):
    def run(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            nodes = add_need(
                self.env.app,
                self.state,
                self.env.docname,
                self.lineno,
                need_type="req",
                title="a need given a deprecated key",
                id="R_DEP",
                hide_tags=True,
            )
        # Sphinx's own deprecations (``env.app``) are not this test's
        self.env.deprecated_key_warnings = [
            (w.category.__name__, str(w.message), w.filename)
            for w in caught
            if not w.category.__name__.startswith("RemovedInSphinx")
        ]
        return nodes


def setup(app):
    app.add_directive("deprecated-key", DeprecatedKey)
    return {"parallel_read_safe": False}
'''


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    "import sys\nfrom pathlib import Path\n\n"
                    "sys.path.insert(0, str(Path(__file__).parent))\n"
                    'sys.modules.pop("deprecated_key_ext", None)\n'
                    'extensions = ["sphinx_needs", "deprecated_key_ext"]\n',
                ),
                (Path("deprecated_key_ext.py"), DEPRECATED_KEY_EXT),
                (Path("index.rst"), "Keys\n====\n\n.. deprecated-key::\n"),
            ],
        }
    ],
    indirect=True,
)
def test_add_need_still_warns_once_of_a_deprecated_key(test_app: SphinxTestApp):
    """``add_need``'s own ``DeprecationWarning`` for a key it no longer reads is
    unchanged: once per call, from ``api/need.py`` (its ``stacklevel=1``), and the key
    is dropped rather than refused."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert "R_DEP" in SphinxNeedsData(app.env).get_needs_view()
    caught = app.env.deprecated_key_warnings
    assert [(category, message) for category, message, _ in caught] == [
        ("DeprecationWarning", "deprecated key found in kwargs")
    ]
    assert Path(caught[0][2]).as_posix().endswith("sphinx_needs/api/need.py")


# --- the delegation fence: add_need(**legacy) == create_need(**explicit) -------------------

DELEGATION_EXT = '''\
"""Creates each case twice, through ``add_need`` and through ``create_need``, and keeps
what the two gave: the need, its nodes, or the refusal."""

from docutils.statemachine import StringList
from sphinx.util.docutils import SphinxDirective

from sphinx_needs._need_source import NeedSourceHop, directive_hops
from sphinx_needs.api import MarkupContent, add_need, create_need, del_need
from sphinx_needs.api.need import _create_need
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import InvalidNeedException
from sphinx_needs.need_item import (
    NeedItemSourceDirective,
    NeedItemSourceExternal,
    NeedItemSourceImport,
    NeedItemSourceService,
    NeedItemSourceUnknown,
)

#: ``add_need``'s keywords that say where the need is from: ``create_need``'s source
LOCATION = ("docname", "lineno", "lineno_content", "is_import", "is_external", "external_url")
#: ``add_need``'s keywords that ``create_need`` has too
NAMED = ("id", "content", "doctype", "jinja_content", "full_title", "allow_type_coercion")
#: ``add_need``'s keywords that only the record paths give, through the private core
RECORD_ONLY = ("parts", "arch", "signature", "sections", "external_css")

#: name -> (the legacy keywords, the sources it applies to (None: all))
CASES = {
    "plain": ({}, None),
    "core": (
        dict(status="open", tags="a, b", collapse=True, style="green", layout="clean",
             constraints="c1"),
        None,
    ),
    "hide": (dict(hide=True), None),
    "templates": (dict(template="t", pre_template="pre", post_template="post"), None),
    "extras_links": (dict(prio="high", links="R_OTHER", blocks="R_OTHER"), None),
    "content_str": (dict(content="Some *text*."), None),
    "content_sl": (
        dict(content=StringList(["A line", "", "Another"], source="x")),
        ("unknown", "directive", "service", "import"),
    ),
    "content_markup": (
        dict(content=MarkupContent("Md *text*", markup=".md")),
        ("unknown", "directive", "service", "import"),
    ),
    "jinja": (dict(content="{{ title }} jinja", jinja_content=True), None),
    "doctype": (dict(doctype=".md", content="x"), None),
    "full_title": (dict(full_title="A much longer title"), None),
    "no_id": (dict(id=None), None),
    # ``{source}``: the source's name, so that each source's generated id is its own
    "no_id_full_title": (dict(id=None, full_title="A full title {source}"), None),
    "no_id_content": (dict(id=None, title="", content="hashed {source}"), None),
    "coercion_on": (dict(count="3"), None),
    "coercion_off": (dict(count="3", allow_type_coercion=False), None),
    "record_only": (
        dict(parts={"p1": {"id": "p1", "content": "a part"}}, arch={"x": "y"},
             signature="sig()", sections=["A section"], external_css="ext_css"),
        None,
    ),
    "location": (dict(lineno_content=7, is_import=True), ("unknown",)),
    "external_keywords": (
        dict(is_external=True, external_url="http://example.org/x.html"), ("unknown",)
    ),
    # refused alike
    "unknown_field": (dict(nosuch="x"), ("unknown", "directive")),
    "id_required": (dict(id=None, id_required=True), ("unknown", "directive")),
    "duplicate_id": (dict(id="R_OTHER"), ("unknown", "directive")),
    "bad_markup": (
        dict(content=MarkupContent("x", markup=".nosuch")), ("unknown", "directive")
    ),
}


def _outcome(call, data):
    """What a creation gave: its need, as recorded, and nodes; or its refusal, and
    whether it recorded a need anyway."""
    before = set(data.get_needs_mutable())
    try:
        result = call()
    except InvalidNeedException as err:
        added = set(data.get_needs_mutable()) - before
        return ("refused", err.type, err.message, added)
    (nid,) = set(data.get_needs_mutable()) - before
    nodes = result[1] if isinstance(result, tuple) else result
    need = data.get_needs_mutable()[nid]
    returned = result[0] if isinstance(result, tuple) else None
    return ("created", need, [n.pformat() for n in nodes], returned)


class DelegationFence(SphinxDirective):
    def run(self):
        app = self.env.app
        data = SphinxNeedsData(self.env)
        link_names = set(data.get_schema().iter_link_field_names())
        hops = directive_hops(self)
        line = self.get_source_info()[1] or self.lineno
        sources = {
            "unknown": lambda: None,
            "directive": lambda: NeedItemSourceDirective(
                lineno=line, lineno_content=self.content_offset + 1,
                parser_lineno=self.lineno, hops=hops),
            "service": lambda: NeedItemSourceService(lineno=self.lineno, hops=hops),
            "import": lambda: NeedItemSourceImport(
                lineno=self.lineno, path="x.json",
                hops=(NeedSourceHop(kind="file"), *hops)),
            "external": lambda: NeedItemSourceExternal(url="http://example.org/p.html"),
        }
        rows = self.env.__dict__.setdefault("delegation_rows", [])
        for cname, (case, applies) in CASES.items():
            for sname, make_source in sources.items():
                if applies is not None and sname not in applies:
                    continue
                legacy = {
                    k: v.replace("{source}", sname) if isinstance(v, str) else v
                    for k, v in case.items()
                }
                id_required = legacy.pop("id_required", False)
                title = legacy.pop("title", f"Fence {sname} {cname}")
                nid = f"FN_{sname}_{cname}".upper()
                legacy.setdefault("id", nid)
                source = make_source()
                external = sname == "external" or legacy.get("is_external", False)
                state = None if external else self.state
                if source is None:
                    legacy.setdefault("docname", self.env.docname)
                    legacy.setdefault("lineno", self.lineno)
                app.config.needs_id_required = id_required
                try:
                    a = _outcome(
                        lambda: add_need(app, state, need_type="req", title=title,
                                         need_source=source, **legacy),
                        data,
                    )
                    if a[0] == "created":
                        del_need(app, a[1]["id"])
                        a = ("created", a[1].copy(), a[2])
                    kw = dict(legacy)
                    location = {k: kw.pop(k) for k in LOCATION if k in kw}
                    explicit_source = source or NeedItemSourceUnknown(**location)
                    named = {k: kw.pop(k) for k in NAMED if k in kw}
                    record_only = {k: kw.pop(k) for k in RECORD_ONLY if k in kw}
                    fields = {k: v for k, v in kw.items() if k not in link_names}
                    links = {k: v for k, v in kw.items() if k in link_names}
                    if record_only:
                        call = lambda: _create_need(  # noqa: E731
                            app, state, explicit_source, "req", title,
                            values={**fields, **links}, **named, **record_only)
                    else:
                        call = lambda: create_need(  # noqa: E731
                            app, state, explicit_source, "req", title,
                            fields=fields, links=links, **named)
                    b = _outcome(call, data)
                finally:
                    app.config.needs_id_required = False
                recorded = None
                if b[0] == "created":
                    # the need returned is the need recorded
                    recorded = b[3] is b[1]
                    b = ("created", b[1].copy(), b[2])
                rows.append((sname, cname, legacy, a, b, recorded))
        return []


def setup(app):
    app.add_directive("delegation-fence", DelegationFence)
    return {"parallel_read_safe": False}
'''

DELEGATION_CONF = """\
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.modules.pop("delegation_ext", None)
extensions = ["sphinx_needs", "myst_parser", "delegation_ext"]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
needs_id_regex = ".*"
needs_fields = {
    "prio": {"nullable": True},
    "count": {"nullable": True, "schema": {"type": "integer"}},
}
needs_links = {"blocks": {}}
needs_constraints = {"c1": {"check_0": "True"}}
"""

DELEGATION_FILES = [
    (Path("conf.py"), DELEGATION_CONF),
    (Path("delegation_ext.py"), DELEGATION_EXT),
    (Path("needs_templates/t.need"), "Template of {{ title }}\n"),
    (Path("needs_templates/pre.need"), "Before {{ id }}\n"),
    (Path("needs_templates/post.need"), "After {{ id }}\n"),
    (
        Path("index.rst"),
        "Delegation\n==========\n\n.. req:: other\n   :id: R_OTHER\n\n"
        ".. delegation-fence::\n",
    ),
]


@pytest.fixture
def delegation_rows(test_app: SphinxTestApp) -> list[tuple]:
    test_app.build()
    assert build_warnings(test_app) == []
    return test_app.env.delegation_rows


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "files": DELEGATION_FILES}], indirect=True
)
def test_add_need_and_create_need_create_the_same_need(delegation_rows):
    """P1. Each case, through ``add_need`` with its legacy keywords and through
    ``create_need`` with the same values (the record-only ones through the private
    core), gives an equal need (its source, hops included) and equal nodes."""
    created = [row for row in delegation_rows if row[3][0] == "created"]
    assert len(created) > 60
    assert [(sname, cname) for sname, cname, _, a, b, _ in created if a != b] == []


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "files": DELEGATION_FILES}], indirect=True
)
def test_add_need_and_create_need_refuse_alike(delegation_rows):
    """P2. A case one path refuses the other refuses with the same type and message,
    and neither has recorded the need."""
    refused = {
        (sname, cname): a
        for sname, cname, _, a, b, _ in delegation_rows
        if a[0] == "refused" or b[0] == "refused"
    }
    assert {
        (sname, cname): b
        for sname, cname, _, a, b, _ in delegation_rows
        if (sname, cname) in refused
    } == refused
    assert {cname for _, cname in refused} == {
        "coercion_off",
        "unknown_field",
        "id_required",
        "duplicate_id",
        "bad_markup",
    }
    assert {a[1] for a in refused.values()} == {
        "invalid_field_value",
        "invalid_kwargs",
        "missing_id",
        "duplicate_id",
        "content_markup",
    }
    # neither path recorded a need it refused
    assert [key for key, a in refused.items() if a[3]] == []


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "files": DELEGATION_FILES}], indirect=True
)
def test_the_need_returned_is_the_need_recorded(delegation_rows):
    """P8. ``create_need`` returns the recorded need itself, not a copy."""
    recorded = [row[5] for row in delegation_rows if row[4][0] == "created"]
    assert recorded and all(recorded)


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "files": DELEGATION_FILES}], indirect=True
)
def test_every_keyword_of_add_need_is_in_a_case(delegation_rows):
    """P3. Every parameter of ``add_need`` but ``app``, ``state`` and its fields is
    given a value other than its default by some case, so a parameter added later
    fails this until a case maps it."""
    parameters = inspect.signature(add_need).parameters
    given: set[str] = {"need_type", "title"}
    for sname, _, legacy, _, _, _ in delegation_rows:
        if sname != "unknown":
            given.add("need_source")
        given.update(
            name
            for name, value in legacy.items()
            if name in parameters and value != parameters[name].default
        )
    assert {
        name
        for name, parameter in parameters.items()
        if parameter.kind is not parameter.VAR_KEYWORD
    } - {"app", "state"} - given == set()


def test_a_link_type_in_fields_or_a_field_in_links_is_refused(make_app, tmp_path):
    """``create_need``'s own refusals, before anything is recorded: a name given in the
    wrong mapping is named, with the mapping it belongs in; and a need on a page without
    a parser state."""
    (tmp_path / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\nneeds_fields = {"prio": {"nullable": True}}\n',
        encoding="utf-8",
    )
    (tmp_path / "index.rst").write_text("Refusals\n========\n", encoding="utf-8")
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    source = NeedItemSourceExternal(url="http://example.org/x.html")
    refusals = []
    for mappings in ({"fields": {"links": "R_1"}}, {"links": {"prio": "high"}}):
        with pytest.raises(InvalidNeedException) as err:
            create_need(app, None, source, "req", "T", id="R_X", **mappings)
        refusals.append((err.value.type, err.value.message))
    assert refusals == [
        (
            "invalid_kwargs",
            "['links'] are link types: give them in 'links', not in 'fields'.",
        ),
        (
            "invalid_kwargs",
            "['prio'] are fields: give them in 'fields', not in 'links'.",
        ),
    ]
    assert "R_X" not in SphinxNeedsData(app.env).get_needs_mutable()

    # a need placed on a page is rendered: it needs the page's parser state
    with pytest.raises(ValueError, match="a parser state is required"):
        create_need(app, None, NeedItemSourceUnknown(docname="index"), "req", "T")


def test_an_argument_of_create_need_in_fields_or_links_is_refused_naming_it(
    make_app, tmp_path
):
    """A name that is one of ``create_need``'s own arguments, given in a mapping, is
    refused naming the argument it belongs in; a field the project declares under such
    a name is a field, and other names keep the unknown-name message."""
    (tmp_path / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\n'
        'needs_fields = {"full_title": {"nullable": True}}\n',
        encoding="utf-8",
    )
    (tmp_path / "index.rst").write_text("Arguments\n=========\n", encoding="utf-8")
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    source = NeedItemSourceExternal(url="http://example.org/x.html")
    refusals = []
    for mappings in (
        {"fields": {"title": "T"}},
        {"links": {"content": "C"}},
        {"fields": {"type": "req"}},
    ):
        with pytest.raises(InvalidNeedException) as err:
            create_need(app, None, source, "req", "T", id="R_X", **mappings)
        refusals.append((err.value.type, err.value.message))
    assert refusals == [
        (
            "invalid_kwargs",
            "'title' is an argument of create_need: give it as title=, not in 'fields'.",
        ),
        (
            "invalid_kwargs",
            "'content' is an argument of create_need: give it as content=, not in "
            "'links'.",
        ),
        ("invalid_kwargs", "{'type'} not in 'needs_fields' or 'needs_links'."),
    ]
    need, _ = create_need(
        app, None, source, "req", "T", id="R_Y", fields={"full_title": "a field"}
    )
    assert need["full_title"] == "a field"


def test_only_the_need_s_own_values_are_named_as_arguments(make_app, tmp_path):
    """The names refused as arguments are the need's own values -- ``title``, ``id``,
    ``content``, ``doctype``, ``jinja_content``, ``full_title`` --, never the caller's
    plumbing (``state``, ``source``, ...), which a field author reading a sibling's
    warning cannot give; two of them are named together."""
    (tmp_path / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\n', encoding="utf-8"
    )
    (tmp_path / "index.rst").write_text("Arguments\n=========\n", encoding="utf-8")
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    source = NeedItemSourceExternal(url="http://example.org/x.html")
    refusals = []
    for fields in ({"content": "C", "title": "T"}, {"state": "draft"}):
        with pytest.raises(InvalidNeedException) as err:
            create_need(app, None, source, "req", "T", id="R_X", fields=fields)
        refusals.append(err.value.message)
    assert refusals == [
        "['content', 'title'] are arguments of create_need: give them as content=, "
        "title=, not in 'fields'.",
        "{'state'} not in 'needs_fields' or 'needs_links'.",
    ]
