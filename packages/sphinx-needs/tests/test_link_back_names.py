"""A link type's back links, ``<l>_back``, and a field or link type of that name.

The back links of a link type ``l`` are computed on every need under the name
``l_back``, so that name is claimed by the link type. A field or another link type
declared with it is one rule, applied where the schema is built, as a ``needs.config``
finding rather than an abort, whichever door the other declaration comes through:

* ``links`` and ``parent_needs``, which every project has, never yield: a field (from
  ``needs_fields``, ``needs_extra_options``, ``add_field`` or a service) or a link type
  named ``links_back`` or ``parent_needs_back`` is ignored instead;
* between two global declarations, a name declared outright beats back links: a link
  type ``x`` (``needs_links`` or ``needs_extra_links``) beside a field or a link type
  ``x_back`` is refused and does not exist -- no directive option, no back links, no
  entry of the ``needs_schema`` -- and ``x_back`` keeps the value its needs give it,
  in every view.

What a need type declares is a lower tier, pinned with the per-type declarations
(``test_type_local_fields.py``, ``test_type_local_link_types.py``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.filter_common import filter_needs_view
from sphinx_needs.needs_schema import FieldsSchema
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_types = [
    dict(directive="t", title="T", prefix="T_"),
    dict(directive="u", title="U", prefix="U_"),
]
"""

#: a need giving ``x_back`` a value, and a need linking to it through ``x``
INDEX = (
    ".. t:: A\n   :id: T_001\n   :x_back: authored\n\n"
    ".. u:: B\n   :id: U_001\n   :x: T_001\n"
)

#: the option ``x`` of ``U_001`` (``INDEX``), once ``x`` is no link type
UNKNOWN_X = "<srcdir>/index.rst:8: WARNING: Unknown option 'x' [needs.directive]"

DEPRECATED_EXTRA_LINKS = (
    'WARNING: Config option "needs_extra_links" is deprecated. Please use '
    '"needs_links" instead. [needs.deprecated]'
)
DEPRECATED_EXTRA_OPTIONS = (
    'WARNING: Config option "needs_extra_options" is deprecated. Please use '
    '"needs_fields" instead. [needs.deprecated]'
)
DEPRECATED_GLOBAL_OPTIONS = (
    'WARNING: Config option "needs_global_options" is deprecated. Please use '
    "needs_fields and needs_links instead. [needs.deprecated]"
)

#: the field ``x_back`` through each door a field is declared by
FIELD_X_BACK = (
    "needs_fields = {'x_back': {'schema': {'type': 'string'}, 'nullable': True}}\n"
)
EXTRA_OPTION_X_BACK = "needs_extra_options = ['x_back']\n"
ADD_FIELD_X_BACK = """\
from sphinx_needs.api import add_field

def setup(app):
    add_field("x_back", "by an extension", schema={"type": "string"}, nullable=True)
"""
#: after ``check_configuration`` (``config-inited``, priority 600)
LATE_ADD_FIELD_X_BACK = """\
from sphinx_needs.api import add_field

def _late(app, config):
    add_field("x_back", "late", schema={"type": "string"}, nullable=True)

def setup(app):
    app.connect("config-inited", _late, priority=900)
"""
#: registered at ``env-before-read-docs``, after the configuration is checked
SERVICE_X_BACK = """\
from sphinx_needs.services.base import BaseService

class Svc(BaseService):
    options = ["x_back"]

    def __init__(self, app, name, config, **kwargs):
        super().__init__()

needs_services = {"svc": {"class": Svc, "class_init": {}}}
"""
LINKS_X = "needs_links = {'x': {}}\n"
EXTRA_LINKS_X = "needs_extra_links = [{'option': 'x'}]\n"


def _project(conf: str, index: str = INDEX, builder: str = "needs") -> dict[str, Any]:
    return {
        "buildername": builder,
        "files": [
            (Path("conf.py"), CONF + conf),
            (Path("index.rst"), "Case\n====\n\n" + index),
        ],
    }


def _version(app: Any) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    return _version(app)["needs"]


def _properties(app: Any) -> dict[str, Any]:
    return _version(app)["needs_schema"]["properties"]


def _schema(app: Any) -> FieldsSchema:
    return SphinxNeedsData(app.env).get_schema()


def _warnings(app: Any) -> list[str]:
    """The build's warnings, but Sphinx's own about a service class in ``conf.py``,
    which it cannot pickle (its text differs between Sphinx versions)."""
    return [w for w in build_warnings(app) if "cannot cache unpick" not in w]


def _refused(declared: str, back: str, what: str) -> str:
    """The finding of a link type whose back links would be named as ``what``."""
    name = back.removesuffix("_back")
    return (
        f"WARNING: {declared} declares the link type {name!r}, whose back links would "
        f"be {back!r}, which is {what}; the link type is ignored [needs.config]"
    )


def _core_field(name: str, source: str) -> str:
    """The finding of a field named as the back links of a core link type."""
    link = name.removesuffix("_back")
    return (
        f"WARNING: Field {name!r} (from {source}) names the back links of the core "
        f"link type {link!r}, which is not a field; the field is ignored [needs.config]"
    )


def _core_link(declared: str, name: str) -> str:
    """The finding of a link type named as the back links of a core link type."""
    link = name.removesuffix("_back")
    return (
        f"WARNING: {declared} names the back links of the core link type {link!r}, "
        "which is not a link type; the link type is ignored [needs.config]"
    )


#: (id, the configuration, the findings before the refusal, the link type's entry,
#: where the field comes from)
FIELD_DOORS = [
    (
        "needs_fields-needs_links",
        FIELD_X_BACK + LINKS_X,
        [],
        "needs_links",
        "needs_fields",
    ),
    (
        "needs_extra_options-needs_links",
        EXTRA_OPTION_X_BACK + LINKS_X,
        [DEPRECATED_EXTRA_OPTIONS],
        "needs_links",
        "needs_extra_options",
    ),
    (
        "needs_fields-needs_extra_links",
        FIELD_X_BACK + EXTRA_LINKS_X,
        [DEPRECATED_EXTRA_LINKS],
        "needs_extra_links",
        "needs_fields",
    ),
    (
        "needs_extra_options-needs_extra_links",
        EXTRA_OPTION_X_BACK + EXTRA_LINKS_X,
        [DEPRECATED_EXTRA_OPTIONS, DEPRECATED_EXTRA_LINKS],
        "needs_extra_links",
        "needs_extra_options",
    ),
    (
        "add_field-needs_links",
        ADD_FIELD_X_BACK + LINKS_X,
        [],
        "needs_links",
        "add_field",
    ),
    (
        "add_field-needs_extra_links",
        ADD_FIELD_X_BACK + EXTRA_LINKS_X,
        [DEPRECATED_EXTRA_LINKS],
        "needs_extra_links",
        "add_field",
    ),
    (
        "late_add_field-needs_extra_links",
        LATE_ADD_FIELD_X_BACK + EXTRA_LINKS_X,
        [DEPRECATED_EXTRA_LINKS],
        "needs_extra_links",
        "add_field",
    ),
    (
        "service-needs_extra_links",
        SERVICE_X_BACK + EXTRA_LINKS_X,
        [DEPRECATED_EXTRA_LINKS],
        "needs_extra_links",
        "service",
    ),
]


@pytest.mark.parametrize(
    ("test_app", "before", "entry", "source"),
    [
        pytest.param(_project(conf), before, entry, source, id=door)
        for door, conf, before, entry, source in FIELD_DOORS
    ],
    indirect=["test_app"],
)
def test_a_link_type_whose_back_links_are_a_field_is_refused(
    test_app: Any, before: list[str], entry: str, source: str
) -> None:
    """#2293: a global link type ``x`` beside a global field ``x_back``, through every
    door either is declared by -- an extension's ``add_field`` after the configuration
    check and a service's field among them, and ``needs_extra_links``, which used to
    stop the build -- is refused with one finding naming both, and does not exist; the
    field keeps its value in needs.json, in Python and in a filter, and is validated
    as itself."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        *before,
        _refused(f"{entry} entry 'x'", "x_back", f"a field (from {source})"),
        UNKNOWN_X,
    ]
    schema = _schema(app)
    assert schema.get_link_field("x") is None
    assert schema.get_extra_field("x_back") is not None
    # a needs_extra_options field without a schema defaults to "", as it always has
    unset = "" if source == "needs_extra_options" else None
    needs = _needs(app)
    assert needs["T_001"]["x_back"] == "authored"
    assert needs["U_001"]["x_back"] == unset
    assert "x" not in needs["T_001"]
    assert "x" not in needs["U_001"]
    assert "x" not in _properties(app)
    assert _properties(app)["x_back"]["field_type"] == "extra"
    # the views agree: Python and the filters read what needs.json writes
    view = SphinxNeedsData(app.env).get_needs_view()
    assert {k: view[k]["x_back"] for k in ("T_001", "U_001")} == {
        "T_001": "authored",
        "U_001": unset,
    }
    matched = filter_needs_view(
        view, NeedsSphinxConfig(app.config), 'x_back == "authored"'
    )
    assert [need["id"] for need in matched] == ["T_001"]


@pytest.mark.parametrize(
    "test_app",
    [_project(FIELD_X_BACK + LINKS_X, builder="html")],
    indirect=True,
)
def test_the_page_of_a_refused_link_type(test_app: Any) -> None:
    """#2293, html: the incoming row of ``x`` used to iterate the authored string
    character by character, one ``needs.link_ref`` warning per character; the link
    type is refused, and the page shows the field's value."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        _refused("needs_links entry 'x'", "x_back", "a field (from needs_fields)"),
        UNKNOWN_X,
    ]
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "x incoming" not in html
    assert "authored" in html


#: the four pairs of global link types ``x`` and ``x_back``
LINK_PAIRS = [
    ("needs_links", "needs_links", "needs_links = {'x': {}, 'x_back': {}}\n", []),
    (
        "needs_extra_links",
        "needs_extra_links",
        "needs_extra_links = [{'option': 'x'}, {'option': 'x_back'}]\n",
        [DEPRECATED_EXTRA_LINKS],
    ),
    (
        "needs_links",
        "needs_extra_links",
        LINKS_X + "needs_extra_links = [{'option': 'x_back'}]\n",
        [DEPRECATED_EXTRA_LINKS],
    ),
    (
        "needs_extra_links",
        "needs_links",
        EXTRA_LINKS_X + "needs_links = {'x_back': {}}\n",
        [DEPRECATED_EXTRA_LINKS],
    ),
]


@pytest.mark.parametrize(
    ("test_app", "before", "entry", "other"),
    [
        pytest.param(
            _project(
                conf,
                ".. t:: A\n   :id: T_001\n   :x_back: U_002\n\n"
                ".. u:: B\n   :id: U_001\n   :x: T_001\n\n"
                ".. u:: C\n   :id: U_002\n",
            ),
            before,
            entry,
            other,
            id=f"{entry}-{other}",
        )
        for entry, other, conf, before in LINK_PAIRS
    ],
    indirect=["test_app"],
)
def test_a_link_type_whose_back_links_are_a_link_type_is_refused(
    test_app: Any, before: list[str], entry: str, other: str
) -> None:
    """#2293, link against link: global link types ``x`` and ``x_back``, through either
    table, refuse ``x``; ``x_back`` keeps the links its needs give it, and its own back
    links are computed."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        *before,
        _refused(f"{entry} entry 'x'", "x_back", f"a link type (from {other})"),
        UNKNOWN_X,
    ]
    assert _schema(app).get_link_field("x") is None
    needs = _needs(app)
    assert needs["T_001"]["x_back"] == ["U_002"]
    assert needs["U_002"]["x_back_back"] == ["T_001"]
    assert "x" not in needs["U_001"]
    assert "x" not in _properties(app)
    assert _properties(app)["x_back"]["field_type"] == "links"


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            "needs_links = {'x': {}, 'x_back': {}}\n"
            "needs_fields = {'x_back_back': {'schema': {'type': 'string'}}}\n",
            ".. t:: A\n   :id: T_001\n\n.. u:: B\n   :id: U_001\n   :x: T_001\n",
        )
    ],
    indirect=True,
)
def test_a_refused_link_type_claims_no_name(test_app: Any) -> None:
    """A link type refused for its own back links does not exist, so it takes no name
    from another: ``x_back`` yields to the field ``x_back_back``, and ``x`` keeps its
    back links, ``x_back``."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        _refused(
            "needs_links entry 'x_back'", "x_back_back", "a field (from needs_fields)"
        ),
    ]
    assert _schema(app).get_link_field("x_back") is None
    needs = _needs(app)
    assert needs["T_001"]["x_back"] == ["U_001"]
    assert _properties(app)["x_back"]["field_type"] == "backlinks"


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            "needs_links = {'aa': {}, 'parent_needs_back': {}}\n"
            "needs_fields = {'aa_back': {'schema': {'type': 'string'}}, "
            "'links_back': {'schema': {'type': 'string'}}}\n",
            ".. t:: A\n   :id: T_001\n",
        )
    ],
    indirect=True,
)
def test_the_findings_are_in_the_order_of_their_names(test_app: Any) -> None:
    """The findings come in the order of the names refused, whatever the order of the
    configuration (here the link types are given before the fields, and ``aa`` after
    ``parent_needs_back`` would be the order of the checks): the text is the same on
    every run and every machine."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        _refused("needs_links entry 'aa'", "aa_back", "a field (from needs_fields)"),
        _core_field("links_back", "needs_fields"),
        _core_link("needs_links entry 'parent_needs_back'", "parent_needs_back"),
    ]


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            FIELD_X_BACK + LINKS_X + EXTRA_LINKS_X,
            ".. t:: A\n   :id: T_001\n   :x_back: authored\n",
        )
    ],
    indirect=True,
)
def test_the_finding_names_the_entry_that_declares_the_link_type(
    test_app: Any,
) -> None:
    """A link type in both ``needs_links`` and ``needs_extra_links`` is the
    ``needs_extra_links`` entry, as where the schema is built: the finding names it."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        DEPRECATED_EXTRA_LINKS,
        _refused(
            "needs_extra_links entry 'x'", "x_back", "a field (from needs_fields)"
        ),
    ]
    assert _needs(app)["T_001"]["x_back"] == "authored"


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            FIELD_X_BACK + LINKS_X + "needs_types = [\n"
            "    dict(directive='t', title='T', prefix='T_',\n"
            "         fields={'x': {'schema': {'type': 'string'}}}),\n"
            "    dict(directive='u', title='U', prefix='U_', links={'x': {}}),\n"
            "]\n",
            ".. t:: A\n   :id: T_001\n   :x: hello\n\n"
            ".. u:: B\n   :id: U_001\n   :x: T_001\n",
        )
    ],
    indirect=True,
)
def test_a_refused_link_type_leaves_its_name_free(test_app: Any) -> None:
    """A refused link type does not exist, so its name is free: a need type may declare
    a field of that name (its needs hold it), and another type's ``links`` entry of the
    name names that field, not a link type."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        _refused("needs_links entry 'x'", "x_back", "a field (from needs_fields)"),
        "WARNING: needs_types['u'].links['x'] declares 'x', which is a field, not a "
        "link type; the entry is ignored [needs.type_conflict]",
        "<srcdir>/index.rst:8: WARNING: Field 'x' is not declared on need type 'u' "
        "and cannot be set in need 'U_001'; the value 'T_001' is ignored "
        "[needs.undeclared_for_type]",
    ]
    assert _schema(app).get_link_field("x") is None
    needs = _needs(app)
    assert (needs["T_001"]["x"], needs["U_001"]["x"]) == ("hello", None)
    assert _properties(app)["x"]["field_type"] == "extra"


#: a nested need, so that both core link types have back links
CORE_INDEX = (
    ".. t:: A\n   :id: T_001\n\n   .. u:: B\n      :id: U_001\n      :links: T_001\n"
)


def _add_field(name: str) -> str:
    return (
        "from sphinx_needs.api import add_field\n\n"
        "def setup(app):\n"
        f"    add_field({name!r}, 'by an extension', schema={{'type': 'string'}})\n"
    )


def _service(name: str) -> str:
    return SERVICE_X_BACK.replace('"x_back"', repr(name))


@pytest.mark.parametrize(
    ("test_app", "before", "name", "source"),
    [
        pytest.param(
            _project(
                "needs_fields = {'links_back': {'schema': {'type': 'string'}}}\n",
                CORE_INDEX,
            ),
            [],
            "links_back",
            "needs_fields",
            id="needs_fields",
        ),
        pytest.param(
            _project(
                "needs_extra_options = ['parent_needs_back']\n"
                "needs_extra_links = [{'option': 'blocks'}]\n",
                CORE_INDEX,
            ),
            [DEPRECATED_EXTRA_OPTIONS, DEPRECATED_EXTRA_LINKS],
            "parent_needs_back",
            "needs_extra_options",
            id="needs_extra_options",
        ),
        pytest.param(
            _project(_add_field("links_back"), CORE_INDEX),
            [],
            "links_back",
            "add_field",
            id="add_field",
        ),
        pytest.param(
            _project(_service("parent_needs_back"), CORE_INDEX),
            [],
            "parent_needs_back",
            "service",
            id="service",
        ),
    ],
    indirect=["test_app"],
)
def test_a_field_named_as_core_back_links_is_refused(
    test_app: Any, before: list[str], name: str, source: str
) -> None:
    """The core link types never yield: a field named ``links_back`` or
    ``parent_needs_back``, by any door, is ignored with one finding, and the back
    links are computed on every need as without it (a ``needs_extra_links`` entry
    beside it changes nothing)."""
    app = test_app
    app.build()
    assert _warnings(app) == [*before, _core_field(name, source)]
    assert _schema(app).get_extra_field(name) is None
    needs = _needs(app)
    assert (needs["T_001"]["links_back"], needs["T_001"]["parent_needs_back"]) == (
        ["U_001"],
        ["U_001"],
    )
    assert (needs["U_001"]["links_back"], needs["U_001"]["parent_needs_back"]) == (
        [],
        [],
    )
    assert _properties(app)[name]["field_type"] == "backlinks"


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            "needs_links = {'links_back': {}}\n"
            "needs_extra_links = [{'option': 'parent_needs_back'}]\n",
            CORE_INDEX,
        )
    ],
    indirect=True,
)
def test_a_link_type_named_as_core_back_links_is_refused(test_app: Any) -> None:
    """A link type named ``links_back`` or ``parent_needs_back`` is ignored, one finding
    each, and the core back links are computed as without it: the link type used to
    win, its links replacing the back links of ``links``."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        DEPRECATED_EXTRA_LINKS,
        _core_link("needs_links entry 'links_back'", "links_back"),
        _core_link("needs_extra_links entry 'parent_needs_back'", "parent_needs_back"),
    ]
    for name in ("links_back", "parent_needs_back"):
        assert _schema(app).get_link_field(name) is None, name
        assert _properties(app)[name]["field_type"] == "backlinks", name
    needs = _needs(app)
    assert (needs["T_001"]["links_back"], needs["T_001"]["parent_needs_back"]) == (
        ["U_001"],
        ["U_001"],
    )


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            "needs_extra_options = ['links_back']\nneeds_links = {'links_back': {}}\n",
            CORE_INDEX,
        )
    ],
    indirect=True,
)
def test_a_field_and_a_link_type_named_as_core_back_links_are_both_reported(
    test_app: Any,
) -> None:
    """A field and a link type both named ``links_back`` are both ignored, and each is
    its own finding, the field's first: one finding per refused declaration, not per
    name."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        DEPRECATED_EXTRA_OPTIONS,
        _core_field("links_back", "needs_extra_options"),
        _core_link("needs_links entry 'links_back'", "links_back"),
    ]
    assert _schema(app).get_extra_field("links_back") is None
    assert _schema(app).get_link_field("links_back") is None
    assert _needs(app)["T_001"]["links_back"] == ["U_001"]


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            FIELD_X_BACK
            + LINKS_X
            + "needs_global_options = {'x_back': {'default': 'g'}}\n",
            INDEX + "\n.. u:: C\n   :id: U_002\n",
        )
    ],
    indirect=True,
)
def test_a_global_default_reaches_the_field(test_app: Any) -> None:
    """A consequence, not a fix of its own: once ``x`` is refused, a
    ``needs_global_options`` default of ``x_back`` is the field's, as for any field."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        _refused("needs_links entry 'x'", "x_back", "a field (from needs_fields)"),
        DEPRECATED_GLOBAL_OPTIONS,
        UNKNOWN_X,
    ]
    needs = _needs(app)
    assert {k: needs[k]["x_back"] for k in ("T_001", "U_001", "U_002")} == {
        "T_001": "authored",
        "U_001": "g",
        "U_002": "g",
    }


#: a needs.json of one need of type ``t``, with a value of ``x_back``
IMPORTED = {
    "current_version": "",
    "versions": {
        "": {
            "needs": {
                "T_009": {
                    "id": "T_009",
                    "type": "t",
                    "title": "Imported",
                    "x_back": "imported",
                }
            }
        }
    },
}


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF + FIELD_X_BACK + LINKS_X),
                (
                    Path("index.rst"),
                    "Case\n====\n\n.. needimport:: needs_in.json\n",
                ),
                (Path("needs_in.json"), json.dumps(IMPORTED)),
            ],
        }
    ],
    indirect=True,
)
def test_an_imported_value_of_the_field_is_kept(test_app: Any) -> None:
    """A consequence, not a fix of its own: once ``x`` is refused, ``x_back`` is no
    back links, so a needimport keeps an imported value of it (it used to be dropped
    as the back links of ``x``)."""
    app = test_app
    app.build()
    assert _warnings(app) == [
        _refused("needs_links entry 'x'", "x_back", "a field (from needs_fields)"),
    ]
    assert _needs(app)["T_009"]["x_back"] == "imported"
