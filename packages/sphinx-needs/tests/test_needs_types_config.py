"""``needs_types``: the two shapes, the findings, and one registration per directive.

``needs_types`` is a list of mappings, each naming its ``directive``, or a mapping from
directive name to the other keys -- in ``conf.py`` and in the ``needs_from_toml`` file
alike (``[[needs.types]]`` / ``[needs.types.<name>]``). A ``config-inited`` handler at
priority 12 resolves either to the list every reader of the option expects, in the
order the entries are given, and reports what it cannot use as ``needs.config``
warnings instead of failing the build (#2262).

A need type's directive is registered once, whichever of ``load_config`` and
``add_need_type`` comes first (#2271); a directive of another class under a type's name
is still overridden, with Sphinx's own warning.
"""

from __future__ import annotations

import copy
import json
import pickle
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from docutils.parsers.rst import directives
from sphinx.config import Config
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

from sphinx_needs.api import get_need_types
from sphinx_needs.api.need import _get_need_type
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.directives.need import NeedDirective
from sphinx_needs.exceptions import InvalidNeedException, NeedsConfigException
from sphinx_needs.needs import normalise_need_types
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
"""

TOML_CONF = CONF + 'needs_from_toml = "ubproject.toml"\n'

#: the known keys, as the unknown-key finding lists them
KNOWN = "known keys are directive, title, prefix, color, style, inherits, fields, links"

#: three types in an order that is not alphabetical, so that a sort would show
ZETA = {"title": "Zeta", "prefix": "Z_", "color": "#000001", "style": "node"}
ALPHA = {"title": "Alpha", "prefix": "A_", "color": "#000002", "style": "card"}
MID = {"title": "Mid", "prefix": "M_", "color": "", "style": "frame"}

#: ``ZETA``, ``ALPHA`` and ``MID``, as the list every reader sees
RESOLVED = [
    {"directive": "zeta", **ZETA},
    {"directive": "alpha", **ALPHA},
    {"directive": "mid", **MID},
]

#: the same three types, as a mapping from directive name to the other keys
MAPPING = {"zeta": ZETA, "alpha": ALPHA, "mid": MID}

LIST_CONF = CONF + f"needs_types = {RESOLVED!r}\n"
MAPPING_CONF = CONF + f"needs_types = {MAPPING!r}\n"

#: the same three types as ``[needs.types.<name>]`` tables; a later sub-table of an
#: earlier type does not move it (and ``content`` is not a key of a type)
TABLES_TOML = """\
[needs]
build_json = true

[needs.types.zeta]
title = "Zeta"
prefix = "Z_"
color = "#000001"
style = "node"

[needs.types.alpha]
title = "Alpha"
prefix = "A_"
color = "#000002"
style = "card"

[needs.types.mid]
title = "Mid"
prefix = "M_"
color = ""
style = "frame"

[needs.types.alpha.content]
diagram = "plantuml"
"""

#: one need of each type, each with a generated id
TYPES_INDEX = """\
.. zeta:: A zeta need

.. alpha:: An alpha need

.. mid:: A mid need
"""


def _project(conf: str, index: str = "", **files: str) -> dict[str, Any]:
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), "Case\n====\n\n" + index),
            *((Path(name), text) for name, text in files.items()),
        ],
    }


def _toml_project(config: str, index: str = "") -> dict[str, Any]:
    return _project(TOML_CONF, index, **{"ubproject.toml": config})


def _write(srcdir: Path, conf: str, index: str = "", **files: str) -> Path:
    srcdir.mkdir(parents=True)
    for name, text in {
        "conf.py": conf,
        "index.rst": "Case\n====\n\n" + index,
        **files,
    }.items():
        (srcdir / name).write_text(text, encoding="utf-8")
    return srcdir


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _resolved(app: Any) -> list[dict[str, Any]]:
    """The list every reader of ``needs_types`` sees."""
    return [dict(entry) for entry in NeedsSphinxConfig(app.config).types]


# -- the two shapes ---------------------------------------------------------------------


def test_the_mapping_shape_resolves_to_the_list_shape(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """A mapping from directive name to the other keys is the list of entries, in the
    order the mapping gives them: the same list, the same need types in the same order,
    the same needs."""
    built = {}
    for name, conf in (("list", LIST_CONF), ("mapping", MAPPING_CONF)):
        app = make_app("needs", srcdir=_write(tmp_path / name, conf, TYPES_INDEX))
        assert get_need_types(app) == ["zeta", "alpha", "mid"]
        assert _resolved(app) == RESOLVED
        app.build()
        assert build_warnings(app) == []
        built[name] = _needs(app)
        # each project registers its own directives
        app.cleanup()
    assert built["mapping"] == built["list"]
    assert sorted(
        (n["type"], n["type_name"], n["id"][:2]) for n in built["list"].values()
    ) == [
        ("alpha", "Alpha", "A_"),
        ("mid", "Mid", "M_"),
        ("zeta", "Zeta", "Z_"),
    ]


def test_toml_tables_resolve_to_the_list_shape(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """``[needs.types.<name>]`` tables are the same list, in the order the tables first
    appear: a later sub-table of ``alpha`` does not move it. Its ``content`` key is not
    a key of a need type, and is reported and ignored."""
    reference = make_app(
        "needs", srcdir=_write(tmp_path / "list", LIST_CONF, TYPES_INDEX)
    )
    reference.build()
    expected = _needs(reference)
    # the project below registers its own directives
    reference.cleanup()

    app = make_app(
        "needs",
        srcdir=_write(
            tmp_path / "toml", TOML_CONF, TYPES_INDEX, **{"ubproject.toml": TABLES_TOML}
        ),
    )
    assert get_need_types(app) == ["zeta", "alpha", "mid"]
    assert _resolved(app) == RESOLVED
    app.build()
    assert build_warnings(app) == [
        f"WARNING: needs_types['alpha'] has an unknown key 'content'; {KNOWN}; the key "
        "is ignored [needs.config]"
    ]
    assert _needs(app) == expected


# -- the findings -----------------------------------------------------------------------

REQ = {"directive": "req", "title": "Requirement", "prefix": "R_"}
SPEC = {"directive": "spec", "title": "Specification", "prefix": "S_"}
REQ_VALUE = {"title": "Requirement", "prefix": "R_"}


def _conf_case(
    value: object, warnings: list[str], resolved: list[dict[str, Any]], **kwargs: Any
) -> Any:
    return pytest.param(
        _project(CONF + f"needs_types = {value!r}\n"),
        warnings,
        resolved,
        **kwargs,
    )


FINDINGS = [
    _conf_case(
        [REQ, "spec", 3],
        [
            "needs_types entry 2 is not a mapping (got str); the entry is ignored",
            "needs_types entry 3 is not a mapping (got int); the entry is ignored",
        ],
        [REQ],
        id="entry-not-a-mapping",
    ),
    _conf_case(
        {"req": REQ_VALUE, "spec": ["Specification", "S_"]},
        ["needs_types['spec'] is not a mapping (got list); the entry is ignored"],
        [REQ],
        id="value-not-a-mapping",
    ),
    _conf_case(
        [{"title": "Requirement", "prefix": "R_"}, SPEC],
        ["needs_types entry 1 has no 'directive'; the entry is ignored"],
        [SPEC],
        id="no-directive",
    ),
    _conf_case(
        [{**REQ, "directive": ""}, {**REQ, "directive": 5}, SPEC],
        [
            "needs_types entry 1 has directive = '', which is not a non-empty string; "
            "the entry is ignored",
            "needs_types entry 2 has directive = 5, which is not a non-empty string; "
            "the entry is ignored",
        ],
        [SPEC],
        id="directive-not-a-name",
    ),
    _conf_case(
        {"": REQ_VALUE, "spec": {"title": "Specification", "prefix": "S_"}},
        [
            "needs_types[''] does not name a directive: the key must be a non-empty "
            "string; the entry is ignored"
        ],
        [SPEC],
        id="empty-key",
    ),
    _conf_case(
        {"req": {**REQ_VALUE, "directive": "spec"}},
        [
            "needs_types['req'] sets directive = 'spec'; the key names the directive "
            "and the value is ignored"
        ],
        [REQ],
        id="directive-differs-from-key",
    ),
    _conf_case(
        {"req": {"directive": "req", **REQ_VALUE}},
        [],
        [REQ],
        id="directive-equals-key",
    ),
    _conf_case(
        [{"directive": "req", "prefix": "R_"}, SPEC],
        ["needs_types entry 1 ('req') has no 'title'; the entry is ignored"],
        [SPEC],
        id="no-title",
    ),
    _conf_case(
        {"req": {"prefix": 1}, "spec": {"title": "Specification", "prefix": "S_"}},
        [
            "needs_types['req'] has no 'title' and a 'prefix' that is not a string "
            "(got int); the entry is ignored"
        ],
        [SPEC],
        id="no-title-and-prefix-not-a-string",
    ),
    _conf_case(
        [{**REQ, "prefix": "", "color": ""}],
        [],
        [{**REQ, "prefix": "", "color": ""}],
        id="empty-prefix-and-color",
    ),
    _conf_case(
        [{**REQ, "color": 1, "style": None}],
        [
            "needs_types entry 1 ('req') has a 'color' that is not a string (got int) "
            "and a 'style' that is not a string (got NoneType); the keys are ignored"
        ],
        [REQ],
        id="color-and-style-not-strings",
    ),
    _conf_case(
        [{**REQ, "bogus": 1, "content": "plantuml"}],
        [
            f"needs_types entry 1 ('req') has unknown keys 'bogus', 'content'; {KNOWN}; "
            "the keys are ignored"
        ],
        [REQ],
        id="unknown-keys",
    ),
    _conf_case(
        {"req": {**REQ_VALUE, "content": "plantuml"}},
        [
            f"needs_types['req'] has an unknown key 'content'; {KNOWN}; the key is "
            "ignored"
        ],
        [REQ],
        id="unknown-key-table",
    ),
    _conf_case(
        [
            {**REQ, "title": "One"},
            {**REQ, "title": "Two"},
            SPEC,
            {**REQ, "title": "Three"},
        ],
        [
            "needs_types declares the directive 'req' 3 times, at entries 1, 2 and 4; "
            "the last entry is used"
        ],
        [SPEC, {**REQ, "title": "Three"}],
        id="duplicate-three-times",
    ),
    _conf_case(
        [{**REQ, "bogus": 1}, {**REQ, "title": 2}, SPEC, "x", {**REQ, "title": "Last"}],
        [
            f"needs_types entry 1 ('req') has an unknown key 'bogus'; {KNOWN}; the key "
            "is ignored",
            "needs_types entry 2 ('req') has a 'title' that is not a string (got int); "
            "the entry is ignored",
            "needs_types entry 4 is not a mapping (got str); the entry is ignored",
            "needs_types declares the directive 'req' twice, at entries 1 and 5; the "
            "last entry is used",
        ],
        [SPEC, {**REQ, "title": "Last"}],
        id="findings-in-entry-order",
    ),
    _conf_case(
        [{"directive": "req", "prefix": "R_", "bogus": 1}],
        ["needs_types entry 1 ('req') has no 'title'; the entry is ignored"],
        [],
        id="dropped-entry-reports-only-why",
    ),
    _conf_case(
        [REQ, {**REQ, "title": "Two"}],
        [
            "needs_types declares the directive 'req' twice, at entries 1 and 2; the "
            "last entry is used"
        ],
        [{**REQ, "title": "Two"}],
        id="adjacent-duplicate",
    ),
    # the declarations of a type: their shape here, what they declare in
    # test_type_declarations.py
    _conf_case(
        {"req": {**REQ_VALUE, "inherits": "", "fields": [], "links": "links"}},
        [
            "needs_types['req'] has an 'inherits' that is not a non-empty string (got "
            "'') and a 'fields' that is not a mapping (got list) and a 'links' that is "
            "not a mapping (got str); the keys are ignored"
        ],
        [REQ],
        id="declarations-not-of-their-shape",
    ),
    _conf_case(
        [{**REQ, "inherits": 3}],
        [
            "needs_types entry 1 ('req') has an 'inherits' that is not a non-empty "
            "string (got int); the key is ignored"
        ],
        [REQ],
        id="inherits-not-a-name",
    ),
    _conf_case(
        [{**REQ, "fields": {"status": "open"}, "links": {"links": None}}],
        [
            "needs_types entry 1 ('req').fields['status'] is not a mapping (got str); "
            "the entry is ignored",
            "needs_types entry 1 ('req').links['links'] is not a mapping (got "
            "NoneType); the entry is ignored",
        ],
        [{**REQ, "fields": {}, "links": {}}],
        id="declaration-not-a-mapping",
    ),
    _conf_case(
        {
            "req": {
                **REQ_VALUE,
                "fields": {
                    "status": {
                        "description": 1,
                        "nullable": "no",
                        "schema": [],
                        "predicates": "x",
                        "default": "open",
                    }
                },
                "links": {"links": {"predicates": [["a", "b", "c"], [5, "x"]]}},
            }
        },
        [
            "needs_types['req'].fields['status'] has a 'description' that is not a "
            "string (got int) and a 'schema' that is not a mapping (got list) and a "
            "'nullable' that is not a boolean (got str) and a 'predicates' that is not "
            "a list of (filter, value) pairs (got str); the keys are ignored",
            "needs_types['req'].links['links'] has a 'predicates' that is not a list "
            "of (filter, value) pairs (got a list with an item that is not a (filter, "
            "value) pair); the key is ignored",
        ],
        [
            {
                **REQ,
                "fields": {"status": {"default": "open"}},
                "links": {"links": {}},
            }
        ],
        id="declaration-keys-not-of-their-shape",
    ),
    _conf_case(
        [
            {
                **REQ,
                "fields": {"status": {"parse_variants": True, "derive": "x"}},
                "links": {"links": {"nullable": False, "incoming": "in"}},
            }
        ],
        [
            "needs_types entry 1 ('req').fields['status'] has unknown keys "
            "'parse_variants', 'derive'; known keys are description, schema, "
            "nullable, default, predicates; the keys are ignored",
            "needs_types entry 1 ('req').links['links'] has unknown keys 'nullable', "
            "'incoming'; known keys are description, schema, default, predicates; the "
            "keys are ignored",
        ],
        [{**REQ, "fields": {"status": {}}, "links": {"links": {}}}],
        id="declaration-unknown-keys",
    ),
    _conf_case(
        {
            "req": {
                **REQ_VALUE,
                "inherits": "spec",
                "fields": {
                    "status": {
                        "description": "d",
                        "schema": {"enum": ["open"]},
                        "nullable": True,
                        "default": "open",
                        "predicates": [("id == 'R_1'", "open")],
                    }
                },
                "links": {"links": {"description": "d", "default": []}},
            },
            "spec": {"title": "Specification", "prefix": "S_"},
        },
        [],
        [
            {
                **REQ,
                "inherits": "spec",
                "fields": {
                    "status": {
                        "description": "d",
                        "schema": {"enum": ["open"]},
                        "nullable": True,
                        "default": "open",
                        "predicates": [("id == 'R_1'", "open")],
                    }
                },
                "links": {"links": {"description": "d", "default": []}},
            },
            SPEC,
        ],
        id="declarations-of-their-shape",
    ),
]


@pytest.mark.parametrize(
    ("test_app", "warnings", "resolved"), FINDINGS, indirect=["test_app"]
)
def test_each_finding_and_what_it_leaves(
    test_app: Any, warnings: list[str], resolved: list[dict[str, Any]]
) -> None:
    """Each problem is one ``needs.config`` warning, in entry order and the duplicates
    last, and the build goes on with what is left: an entry without a usable directive,
    ``title`` or ``prefix`` is dropped (its directive does not exist), a ``color`` or
    ``style`` that is not a string and an unknown key are removed from a kept entry, and
    a duplicate directive resolves to its last entry, at its own position."""
    app = test_app
    assert _resolved(app) == resolved
    app.build()
    assert build_warnings(app) == [
        f"WARNING: {text} [needs.config]" for text in warnings
    ]
    needs_config = NeedsSphinxConfig(app.config)
    for entry in resolved:
        assert _get_need_type(needs_config, entry["directive"]) == entry
        assert directives._directives.get(entry["directive"]) is NeedDirective
    if not any(entry["directive"] == "req" for entry in resolved):
        with pytest.raises(InvalidNeedException):
            _get_need_type(needs_config, "req")
        assert "req" not in directives._directives


@pytest.mark.parametrize(
    "files",
    [
        pytest.param({"conf.py": CONF + "needs_types = 'req'\n"}, id="conf"),
        pytest.param(
            {"conf.py": TOML_CONF, "ubproject.toml": '[needs]\ntypes = "req"\n'},
            id="toml",
        ),
    ],
)
def test_a_value_of_neither_shape_stops_the_build(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, files: dict[str, str]
) -> None:
    """A value that is neither a list nor a mapping leaves no need type to read: the
    configuration is refused before any document is read."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    for name, text in {"index.rst": "Case\n====\n", **files}.items():
        (srcdir / name).write_text(text, encoding="utf-8")
    with pytest.raises(NeedsConfigException) as excinfo:
        make_app("needs", srcdir=srcdir)
    assert str(excinfo.value) == (
        "Config option 'needs_types' must be a list of need type mappings or a mapping "
        "from directive name to need type, got str."
    )


# -- the resolution itself ------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(RESOLVED, id="list"),
        pytest.param(MAPPING, id="mapping"),
        pytest.param([REQ, "spec", {**SPEC, "color": 1, "bogus": 2}], id="findings"),
        pytest.param({"req": {**REQ_VALUE, "directive": "spec"}}, id="key-wins"),
        pytest.param([{**REQ, "title": "One"}, SPEC, REQ], id="duplicate"),
        pytest.param([{"directive": "req"}, {}], id="nothing-left"),
    ],
)
def test_the_resolution_is_pure_and_idempotent(value: object) -> None:
    """Resolving leaves the configured value as it was, shares no entry with it, and a
    resolved list resolves to itself without a finding."""
    before = copy.deepcopy(value)
    resolved, _ = normalise_need_types(value)
    assert value == before
    for entry in resolved:
        entry["title"] = "changed"
    assert value == before
    resolved, _ = normalise_need_types(value)
    assert normalise_need_types(resolved) == (resolved, [])


def test_the_declarations_are_resolved_anew() -> None:
    """A resolved entry shares no declaration with the configured value: changing one
    changes nothing in the other."""
    value = {
        "req": {
            **REQ_VALUE,
            "inherits": "spec",
            "fields": {
                "x": {
                    "schema": {"enum": ["A"]},
                    "default": ["d"],
                    "predicates": [["True", "p"]],
                    "bogus": 1,
                }
            },
            "links": {"blocks": {"default": ["R_1"]}},
        }
    }
    before = copy.deepcopy(value)
    resolved, findings = normalise_need_types(value)
    assert len(findings) == 1
    entry: dict[str, Any] = dict(resolved[0])
    entry["fields"]["x"]["schema"]["enum"].append("B")
    entry["fields"]["x"]["default"].append("e")
    entry["fields"]["x"]["predicates"][0][1] = "q"
    entry["links"]["blocks"]["default"].clear()
    entry["fields"]["y"] = {}
    assert value == before
    assert normalise_need_types(normalise_need_types(value)[0]) == (
        normalise_need_types(value)[0],
        [],
    )


#: what the finding says a ``predicates`` value that is not of its shape is
NOT_A_LIST = "(got str)"
NOT_A_PAIR = "(got a list with an item that is not a (filter, value) pair)"


@pytest.mark.parametrize(
    ("predicates", "got"),
    [
        pytest.param([["id == 'R_1'", "open"]], None, id="a-list-of-lists"),
        pytest.param([("id == 'R_1'", ["a", "b"])], None, id="a-tuple-any-value"),
        pytest.param((), None, id="none"),
        pytest.param("x", NOT_A_LIST, id="not-a-list"),
        pytest.param(["id == 'R_1'"], NOT_A_PAIR, id="not-a-pair"),
        pytest.param([["id == 'R_1'"]], NOT_A_PAIR, id="one-item"),
        pytest.param([["id == 'R_1'", "a", "b"]], NOT_A_PAIR, id="three-items"),
        pytest.param([[5, "open"]], NOT_A_PAIR, id="a-filter-not-a-string"),
    ],
)
def test_predicates_are_filter_value_pairs(predicates: object, got: str | None) -> None:
    """``predicates`` is a list of pairs, each a filter string and a value of any
    type, as ``needs_fields`` takes them; the finding says which of the two it is
    not."""
    resolved, findings = normalise_need_types(
        {"req": {**REQ_VALUE, "fields": {"status": {"predicates": predicates}}}}
    )
    assert ("predicates" in resolved[0]["fields"]["status"]) is (got is None)
    assert findings == (
        []
        if got is None
        else [
            "needs_types['req'].fields['status'] has a 'predicates' that is not a "
            f"list of (filter, value) pairs {got}; the key is ignored"
        ]
    )


def test_the_mapping_shape_is_the_list_in_its_order() -> None:
    """Each key becomes the entry's ``directive``, first, in the mapping's order."""
    resolved, findings = normalise_need_types(MAPPING)
    assert (resolved, findings) == (RESOLVED, [])
    assert [next(iter(entry)) for entry in resolved] == ["directive"] * 3


@pytest.mark.parametrize("value", ["req", ("req",), None, 3])
def test_a_value_of_neither_shape_is_refused(value: object) -> None:
    with pytest.raises(NeedsConfigException, match="must be a list of need type"):
        normalise_need_types(value)


# -- the duplicate on every creation path ------------------------------------------------

FIRST = {"directive": "req", "title": "First", "prefix": "F_"}
LAST = {"directive": "req", "title": "Last", "prefix": "L_"}

DUPLICATE_INDEX = """\
.. req:: A need of the directive

.. list2need::
   :types: req

   * A need of the list
"""

DUPLICATE_TOML = """\
[needs]
build_json = true

[[needs.types]]
directive = "req"
title = "First"
prefix = "F_"

[[needs.types]]
directive = "spec"
title = "Specification"
prefix = "S_"

[[needs.types]]
directive = "req"
title = "Last"
prefix = "L_"
"""


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            _project(
                CONF + f"needs_types = {[FIRST, SPEC, LAST]!r}\n", DUPLICATE_INDEX
            ),
            id="conf",
        ),
        pytest.param(_toml_project(DUPLICATE_TOML, DUPLICATE_INDEX), id="toml"),
    ],
    indirect=True,
)
def test_a_duplicate_directive_is_its_last_entry_on_every_path(test_app: Any) -> None:
    """A need of the directive and a need of ``list2need`` both take the last entry's
    title and prefix, and the directive is registered once: the finding is the only
    warning."""
    app = test_app
    # read before the build, which adds the GitHub service's types
    resolved = _resolved(app)
    app.build()
    needs = _needs(app)
    assert sorted(
        (n["title"], n["type_name"], n["id"][:2]) for n in needs.values()
    ) == [
        ("A need of the directive", "Last", "L_"),
        ("A need of the list", "Last", "L_"),
    ]
    assert build_warnings(app) == [
        "WARNING: needs_types declares the directive 'req' twice, at entries 1 and 3; "
        "the last entry is used [needs.config]"
    ]
    assert resolved == [SPEC, LAST]


# -- one registration per directive (#2271) -----------------------------------------------

ADD_TYPE_SETUP = """
def _add_story(app, config):
    from sphinx_needs.api import add_need_type
    add_need_type(app, "story", "Story", "ST_")

def setup(app):
    app.connect("config-inited", _add_story, priority={priority})
"""

STORY_INDEX = ".. story:: A story\n   :id: ST_00001\n"


@pytest.mark.parametrize(
    "test_app",
    [_project(CONF + ADD_TYPE_SETUP.format(priority=499), STORY_INDEX)],
    indirect=True,
)
def test_a_type_added_before_load_config_registers_its_directive_once(
    test_app: Any,
) -> None:
    """``add_need_type`` from a ``config-inited`` handler that runs before sphinx-needs'
    ``load_config`` registers the directive; ``load_config`` then finds it registered
    and does not register it again."""
    app = test_app
    assert get_need_types(app)[-1] == "story"
    app.build()
    assert build_warnings(app) == []
    assert list(_needs(app)) == ["ST_00001"]


#: a directive of another class under ``req``, registered before sphinx-needs' own
FOREIGN_SETUP = """
from docutils.parsers.rst import Directive

class Foreign(Directive):
    def run(self):
        return []

def setup(app):
    app.add_directive("req", Foreign)
"""

#: a subclass of the need directive under ``req``
SUBCLASS_SETUP = """
from sphinx_needs.directives.need import NeedDirective

class Derived(NeedDirective):
    pass

def setup(app):
    app.add_directive("req", Derived)
"""

#: a directive of another class that only shares the need directive's name
NAMESAKE_SETUP = """
from docutils.parsers.rst import Directive

class NeedDirective(Directive):
    def run(self):
        return []

def setup(app):
    app.add_directive("req", NeedDirective)
"""


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            _project(CONF + setup, ".. req:: A need\n   :id: R_00001\n"), id=name
        )
        for name, setup in (
            ("foreign", FOREIGN_SETUP),
            ("subclass", SUBCLASS_SETUP),
            ("namesake", NAMESAKE_SETUP),
        )
    ],
    indirect=True,
)
def test_a_foreign_directive_under_a_type_name_is_overridden(test_app: Any) -> None:
    """A directive of another class under a need type's name -- a subclass of the
    need directive, or a class that only shares its name, included -- is overridden by
    the need directive itself, with Sphinx's own warning, as it always was."""
    app = test_app
    assert directives._directives.get("req") is NeedDirective
    app.build()
    warnings = build_warnings(app)
    assert len(warnings) == 1
    assert "directive 'req' is already registered" in warnings[0]
    assert list(_needs(app)) == ["R_00001"]


#: the need directive already under ``story`` when ``add_need_type`` adds the type
STORY_REGISTERED_SETUP = """
def _add_story(app, config):
    from sphinx_needs.api import add_need_type
    add_need_type(app, "story", "Story", "ST_")

def setup(app):
    from sphinx_needs.directives.need import NeedDirective
    app.add_directive("story", NeedDirective)
    app.connect("config-inited", _add_story, priority=600)
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(CONF + STORY_REGISTERED_SETUP, STORY_INDEX)],
    indirect=True,
)
def test_add_need_type_registers_its_directive_once(test_app: Any) -> None:
    """``add_need_type`` goes through the same rule as ``load_config``: a name that
    already holds the need directive is not registered again."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert list(_needs(app)) == ["ST_00001"]


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            CONF
            + f"needs_types = { {'zeta': ZETA, 'alpha': ALPHA}!r}\n"
            + ADD_TYPE_SETUP.format(priority=600),
            ".. zeta:: A zeta\n   :id: Z_00001\n\n" + STORY_INDEX,
        )
    ],
    indirect=True,
)
def test_add_need_type_after_the_mapping_shape(test_app: Any) -> None:
    """A type added from code after the mapping shape is resolved is appended to the
    list, and its directive works."""
    app = test_app
    assert get_need_types(app) == ["zeta", "alpha", "story"]
    app.build()
    assert build_warnings(app) == []
    assert sorted(_needs(app)) == ["ST_00001", "Z_00001"]


# -- incremental builds -------------------------------------------------------------------


def _changed_options(old: Config, new: Config) -> set[str]:
    """The options whose values differ between two configurations, as Sphinx compares
    them before it decides what an incremental build re-reads."""
    old_values = {item.name: item.value for item in old}
    new_values = {item.name: item.value for item in new}
    return {
        name
        for name in old_values.keys() | new_values.keys()
        if old_values.get(name) != new_values.get(name)
    }


@pytest.mark.parametrize(
    "conf",
    [
        pytest.param(LIST_CONF, id="list"),
        pytest.param(MAPPING_CONF, id="mapping"),
    ],
)
def test_resolving_the_types_changes_no_configuration_option(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, conf: str
) -> None:
    """The resolved list is the value Sphinx sees on both sides of an incremental build.

    The options that differ are exactly the two the GitHub service changes after Sphinx
    compares the configurations -- it adds its need types and its layout from
    ``env-before-read-docs`` (#2265, pre-existing) -- for the list shape and the
    mapping shape alike: resolving the types adds nothing to them.
    """
    srcdir = _write(tmp_path / "src", conf, TYPES_INDEX)
    first = make_app("html", srcdir=srcdir, freshenv=True)
    first.build()
    first.cleanup()
    old_env = pickle.loads(Path(first.doctreedir, "environment.pickle").read_bytes())

    (srcdir / "index.rst").write_text(
        "Case\n====\n\n" + TYPES_INDEX + "\nMore text.\n", encoding="utf-8"
    )
    second = make_app("html", srcdir=srcdir)
    try:
        assert _changed_options(old_env.config, second.config) == {
            "needs_layouts",
            "needs_types",
        }
        second.build()
        # Sphinx 8 and later name the options in a status line; Sphinx 7 does not
        reported = re.search(
            r"The configuration has changed \(\d+ options?: (.*)\)",
            strip_colors(second._status.getvalue()),
        )
        if reported is not None:
            names = set(re.findall(r"'([^']+)'", reported.group(1)))
            assert {name for name in names if name.startswith("needs_")} == {
                "needs_layouts",
                "needs_types",
            }
    finally:
        second.cleanup()
