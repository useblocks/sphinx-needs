import json
import os
import time
from pathlib import Path

import pytest
from syrupy.extensions import AmberSnapshotExtension
from syrupy.filters import props

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings


class SnapshotExtension(AmberSnapshotExtension):
    @classmethod
    def get_snapshot_name(cls, *, test_location, index: str) -> str:
        # only use the index as name, not the test function name,
        # so that multiple tests can share the same snapshot
        return index


@pytest.fixture
def snapshot(snapshot):
    return snapshot.use_extension(SnapshotExtension)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_global_options",
        }
    ],
    indirect=True,
)
def test_doc_global_option(test_app, snapshot):
    test_app.build()
    warning_records = build_warnings(test_app)
    assert warning_records == [
        'WARNING: Config option "needs_global_options" is deprecated. Please use needs_fields and needs_links instead. [needs.deprecated]',
        "WARNING: needs_global_options['link3']['default'] value is incorrect: Invalid value for field 'link3': 1 [needs.config]",
        "WARNING: needs_global_options['bad_value_type']['default'] value is incorrect: Invalid value for field 'bad_value_type': 1.27 [needs.config]",
        "WARNING: needs_global_options['too_many_params']['predicates'] value is incorrect: defaults must be a list of (filter, value) pairs. [needs.config]",
        "WARNING: needs_global_options['unknown'] does not correspond to any defined field [needs.config]",
    ]

    needs_schema = SphinxNeedsData(test_app.env).get_schema()
    assert {
        s.name: {"default": s.default, "predicate_defaults": s.predicate_defaults}
        for s in needs_schema.iter_all_fields()
    } == snapshot(name="field_defaults_schema")

    json_data = Path(test_app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(
        name="field_defaults_needs", exclude=props("created", "project", "creator")
    )


CONF_INVALID_PREDICATE = """\
extensions = ["sphinx_needs"]

needs_types = [
    {"directive": "spec", "title": "Specification", "prefix": "SP_"}
]

needs_fields = {
    # `section_name` is a field of the need, but is not available to a predicate,
    # so evaluating these raises a NameError
    "with_default": {
        "predicates": [("section_name == 'Test'", "matched")],
        "default": "fallback",
    },
    "without_default": {
        "nullable": True,
        "predicates": [("section_name == 'Test'", "matched")],
    },
    "later_predicate": {
        "predicates": [
            ("section_name == 'Test'", "unreachable"),
            ("status == 'open'", "matched"),
        ],
        "default": "fallback",
    },
    "valid_only": {
        "predicates": [("status == 'open'", "matched")],
        "default": "fallback",
    },
}

needs_links = {
    "blocks": {
        "incoming": "is blocked by",
        "outgoing": "blocks",
        # `content` is likewise not available to a predicate
        "predicates": [("'body' in content", ["SPEC_2"])],
        "default": ["SPEC_1"],
    },
}
"""

INDEX_INVALID_PREDICATE = """\
Test
====

.. spec:: Specification 1
    :id: SPEC_1
    :status: open

.. spec:: Specification 2
    :id: SPEC_2
    :status: open
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_INVALID_PREDICATE),
                (Path("index.rst"), INDEX_INVALID_PREDICATE),
            ],
        }
    ],
    indirect=True,
)
def test_invalid_predicate_default(test_app):
    """A predicate that cannot be evaluated warns and is skipped, and the build completes.

    Such a predicate used to raise out of ``add_need`` and end the whole build with a
    traceback, so a single mistake in ``needs_fields`` / ``needs_links`` cost the
    project every need and every other warning in the build.
    """
    test_app.build()

    warning_records = build_warnings(test_app)
    assert warning_records == [
        "<srcdir>/index.rst:4: WARNING: needs_fields['with_default']['predicates']: "
        "Predicate \"section_name == 'Test'\" not valid. "
        "Error: name 'section_name' is not defined. "
        "The predicate is skipped. [needs.config]",
        "<srcdir>/index.rst:4: WARNING: needs_fields['without_default']['predicates']: "
        "Predicate \"section_name == 'Test'\" not valid. "
        "Error: name 'section_name' is not defined. "
        "The predicate is skipped. [needs.config]",
        "<srcdir>/index.rst:4: WARNING: needs_fields['later_predicate']['predicates']: "
        "Predicate \"section_name == 'Test'\" not valid. "
        "Error: name 'section_name' is not defined. "
        "The predicate is skipped. [needs.config]",
        "<srcdir>/index.rst:4: WARNING: needs_links['blocks']['predicates']: "
        "Predicate \"'body' in content\" not valid. "
        "Error: name 'content' is not defined. "
        "The predicate is skipped. [needs.config]",
    ]

    needs = SphinxNeedsData(test_app.env).get_needs_view()
    assert set(needs) == {"SPEC_1", "SPEC_2"}
    need = needs["SPEC_1"]
    # the skipped predicate falls back to the plain default ...
    assert need["with_default"] == "fallback"
    # ... or, where there is none, leaves the field unset
    assert need["without_default"] is None
    # a later predicate is still evaluated, and still wins over the plain default
    assert need["later_predicate"] == "matched"
    # a predicate that evaluates is unaffected
    assert need["valid_only"] == "matched"
    # links behave the same way
    assert need["blocks"] == ["SPEC_1"]


CONF_UNKNOWN_GLOBAL_OPTION_KEYS = """\
extensions = ["sphinx_needs"]

needs_types = [
    {"directive": "spec", "title": "Specification", "prefix": "SP_"}
]

needs_global_options = {
    # the unknown keys are given in an order that is not alphabetical, so that a
    # sort would show
    "status": {"default": "open", "unexpected_z": 1, "unexpected_a": 2, "unexpected_m": 3},
}
"""

INDEX_UNKNOWN_GLOBAL_OPTION_KEYS = """\
Test
====

.. spec:: Specification 1
    :id: SPEC_1
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_UNKNOWN_GLOBAL_OPTION_KEYS),
                (Path("index.rst"), INDEX_UNKNOWN_GLOBAL_OPTION_KEYS),
            ],
        }
    ],
    indirect=True,
)
def test_unknown_global_option_keys_are_sorted(test_app):
    """The unknown-keys finding lists the keys sorted, so its text is stable.

    The keys came from a ``set``, so the message differed from run to run and
    could not be pinned (:issue:`2288`).
    """
    test_app.build()

    warning_records = build_warnings(test_app)
    assert warning_records == [
        'WARNING: Config option "needs_global_options" is deprecated. Please use '
        "needs_fields and needs_links instead. [needs.deprecated]",
        "WARNING: needs_global_options 'status' value contains unknown keys: "
        "['unexpected_a', 'unexpected_m', 'unexpected_z'] [needs.config]",
    ]


CONF_DEFAULT_IN_BOTH = """\
extensions = ["sphinx_needs"]
needs_build_json = True

needs_types = [
    {"directive": "spec", "title": "Specification", "prefix": "SP_"},
    {
        "directive": "impl",
        "title": "Implementation",
        "prefix": "IM_",
        "fields": {"per_type": {"default": "from_type"}},
    },
]

needs_fields = {
    # a default in both: needs_fields' is used, needs_global_options' reported
    "both": {"schema": {"type": "string"}, "default": "from_fields"},
    # declared without a default: needs_global_options' default applies, as before
    "declared_only": {"schema": {"type": "string"}},
    # predicates in both: needs_fields' are used, needs_global_options' reported
    "predicates": {
        "schema": {"type": "string"},
        "predicates": [("type == 'spec'", "from_fields")],
    },
    # a default in needs_fields, predicates in needs_global_options: nothing is set
    # twice, so both apply
    "mixed": {"schema": {"type": "string"}, "default": "from_fields"},
    # a need type's own default wins over both, on that type
    "per_type": {"schema": {"type": "string"}, "default": "from_fields"},
    # a core field narrowed with a default: the same rule
    "status": {"schema": {"type": "string"}, "default": "open"},
    # a default of None is no default: needs_global_options' applies, unreported
    "none_default": {"schema": {"type": "string"}, "default": None},
}

needs_global_options = {
    "both": {"default": "from_global"},
    "declared_only": {"default": "from_global"},
    "predicates": {"predicates": [("type == 'spec'", "from_global")]},
    "mixed": {"predicates": [("type == 'spec'", "from_global")]},
    "per_type": {"default": "from_global"},
    "status": {"default": "closed"},
    "none_default": {"default": "from_global"},
}
"""

INDEX_DEFAULT_IN_BOTH = """\
Test
====

.. spec:: Specification
    :id: SP_001

.. impl:: Implementation
    :id: IM_001
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF_DEFAULT_IN_BOTH),
                (Path("index.rst"), INDEX_DEFAULT_IN_BOTH),
            ],
        }
    ],
    indirect=True,
)
def test_needs_fields_default_wins_over_global_options(test_app):
    """A field's ``default`` (or ``predicates``) set in both ``needs_fields`` and
    ``needs_global_options`` is ``needs_fields``', and the ignored value is reported,
    once per field (:issue:`2264`).

    The legacy value was applied last and replaced the ``needs_fields`` one silently:
    every unset need held it, and the only message was the deprecation every use of
    ``needs_global_options`` gives. A field ``needs_fields`` declares without the key
    still takes the legacy value, and a need type's own default still wins over both.
    """
    test_app.build()

    assert build_warnings(test_app) == [
        'WARNING: Config option "needs_global_options" is deprecated. Please use '
        "needs_fields and needs_links instead. [needs.deprecated]",
        "WARNING: needs_global_options['both']['default'] ('from_global') is "
        "ignored: needs_fields['both']['default'] ('from_fields') takes precedence "
        "[needs.config]",
        "WARNING: needs_global_options['predicates']['predicates'] "
        "([(\"type == 'spec'\", 'from_global')]) is ignored: "
        "needs_fields['predicates']['predicates'] "
        "([(\"type == 'spec'\", 'from_fields')]) takes precedence [needs.config]",
        "WARNING: needs_global_options['per_type']['default'] ('from_global') is "
        "ignored: needs_fields['per_type']['default'] ('from_fields') takes precedence "
        "[needs.config]",
        "WARNING: needs_global_options['status']['default'] ('closed') is "
        "ignored: needs_fields['status']['default'] ('open') takes precedence "
        "[needs.config]",
    ]

    needs = _needs(test_app)
    assert {
        name: {i: n[name] for i, n in needs.items()}
        for name in (
            "both",
            "declared_only",
            "predicates",
            "mixed",
            "per_type",
            "status",
            "none_default",
        )
    } == {
        "both": {"SP_001": "from_fields", "IM_001": "from_fields"},
        "declared_only": {"SP_001": "from_global", "IM_001": "from_global"},
        "predicates": {"SP_001": "from_fields", "IM_001": None},
        "mixed": {"SP_001": "from_global", "IM_001": "from_fields"},
        "per_type": {"SP_001": "from_fields", "IM_001": "from_type"},
        "status": {"SP_001": "open", "IM_001": "open"},
        "none_default": {"SP_001": "from_global", "IM_001": "from_global"},
    }


CONF_BOTH_KEYS_IN_BOTH = """\
extensions = ["sphinx_needs"]
needs_build_json = True

needs_fields = {
    "asil": {
        "schema": {"type": "string"},
        "default": "QM",
        "predicates": [("status == 'open'", "B")],
    },
}

needs_global_options = {
    "asil": {"default": "A", "predicates": [("status == 'open'", "C")]},
}
"""

INDEX_BOTH_KEYS_IN_BOTH = """\
Test
====

.. req:: Open
    :id: REQ_001
    :status: open

.. req:: Unset
    :id: REQ_002
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF_BOTH_KEYS_IN_BOTH),
                (Path("index.rst"), INDEX_BOTH_KEYS_IN_BOTH),
            ],
        }
    ],
    indirect=True,
)
def test_needs_fields_default_and_predicates_win_in_one_warning(test_app):
    """A field whose ``default`` and ``predicates`` are both set in both places is
    reported once, naming both keys (:issue:`2264`)."""
    test_app.build()

    assert build_warnings(test_app) == [
        'WARNING: Config option "needs_global_options" is deprecated. Please use '
        "needs_fields and needs_links instead. [needs.deprecated]",
        "WARNING: needs_global_options['asil']['default'] ('A') and "
        "needs_global_options['asil']['predicates'] ([(\"status == 'open'\", 'C')]) "
        "are ignored: needs_fields['asil']['default'] ('QM') and "
        "needs_fields['asil']['predicates'] ([(\"status == 'open'\", 'B')]) "
        "take precedence [needs.config]",
    ]
    assert {i: n["asil"] for i, n in _needs(test_app).items()} == {
        "REQ_001": "B",
        "REQ_002": "QM",
    }


CONF_LINK_DEFAULT_IN_BOTH = """\
extensions = ["sphinx_needs"]
needs_build_json = True

needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "REQ_"},
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "links": {"per_type": {"default": ["SP_001"]}},
    },
]

needs_links = {
    # a default in both: needs_links' is used, needs_global_options' reported
    "both": {"default": ["REQ_001"]},
    # declared without a default: needs_global_options' default applies, as before
    "declared_only": {},
    # predicates in both: needs_links' are used, needs_global_options' reported
    "predicates": {"predicates": [("type == 'spec'", ["REQ_001"])]},
    # a default in needs_links, predicates in needs_global_options: nothing is set
    # twice, so both apply
    "mixed": {"default": ["REQ_001"]},
    # a need type's own default wins over both, on that type
    "per_type": {"default": ["REQ_001"]},
    # a default of None is no default: needs_global_options' applies, and only the
    # value needs_links refuses is reported
    "none_default": {"default": None},
    # declared in needs_extra_links too: that entry is the declaration, as in the
    # schema, so its default is used and the warning names it
    "extra": {"default": ["SP_001"]},
}

# the deprecated list-based declaration: the same rule, naming needs_extra_links
needs_extra_links = [{"option": "extra", "default": ["REQ_001"]}]

needs_global_options = {
    "both": {"default": ["REQ_002"]},
    "declared_only": {"default": ["REQ_002"]},
    "predicates": {"predicates": [("type == 'spec'", ["REQ_002"])]},
    "mixed": {"predicates": [("type == 'spec'", ["REQ_002"])]},
    "per_type": {"default": ["REQ_002"]},
    "none_default": {"default": ["REQ_002"]},
    "extra": {"default": ["REQ_002"]},
}
"""

INDEX_LINK_DEFAULT_IN_BOTH = """\
Test
====

.. req:: First
    :id: REQ_001

.. req:: Second
    :id: REQ_002

.. spec:: Specification
    :id: SP_001
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF_LINK_DEFAULT_IN_BOTH),
                (Path("index.rst"), INDEX_LINK_DEFAULT_IN_BOTH),
            ],
        }
    ],
    indirect=True,
)
def test_needs_links_default_wins_over_global_options(test_app):
    """A link type's ``default`` (or ``predicates``) set in both its ``needs_links``
    (or ``needs_extra_links``) entry and ``needs_global_options`` is the entry's, and
    the ignored value is reported, once per link type (:issue:`2317`).

    The rule :issue:`2264` gave fields: the legacy value was applied last and
    replaced the link type's own silently, so every need that did not set the link
    type linked to it. A link type declared without the key still takes the legacy
    value, and a need type's own default still wins over both, on that type.
    """
    test_app.build()

    assert build_warnings(test_app) == [
        'WARNING: Config option "needs_extra_links" is deprecated. Please use '
        '"needs_links" instead. [needs.deprecated]',
        # needs_links refuses None as a value (unlike needs_fields, which reads it
        # as no default); that is all that is reported for it
        "WARNING: needs_links['none_default']['default'] value is incorrect: "
        "Invalid value for field 'none_default': None [needs.config]",
        'WARNING: Config option "needs_global_options" is deprecated. Please use '
        "needs_fields and needs_links instead. [needs.deprecated]",
        "WARNING: needs_global_options['both']['default'] (['REQ_002']) is "
        "ignored: needs_links['both']['default'] (['REQ_001']) takes precedence "
        "[needs.config]",
        "WARNING: needs_global_options['predicates']['predicates'] "
        "([(\"type == 'spec'\", ['REQ_002'])]) is ignored: "
        "needs_links['predicates']['predicates'] "
        "([(\"type == 'spec'\", ['REQ_001'])]) takes precedence [needs.config]",
        "WARNING: needs_global_options['per_type']['default'] (['REQ_002']) is "
        "ignored: needs_links['per_type']['default'] (['REQ_001']) takes "
        "precedence [needs.config]",
        "WARNING: needs_global_options['extra']['default'] (['REQ_002']) is "
        "ignored: needs_extra_links['extra']['default'] (['REQ_001']) takes "
        "precedence [needs.config]",
    ]

    needs = _needs(test_app)
    assert {
        name: {i: n[name] for i, n in needs.items()}
        for name in (
            "both",
            "declared_only",
            "predicates",
            "mixed",
            "per_type",
            "none_default",
            "extra",
        )
    } == {
        "both": {"REQ_001": ["REQ_001"], "REQ_002": ["REQ_001"], "SP_001": ["REQ_001"]},
        "declared_only": {
            "REQ_001": ["REQ_002"],
            "REQ_002": ["REQ_002"],
            "SP_001": ["REQ_002"],
        },
        "predicates": {"REQ_001": [], "REQ_002": [], "SP_001": ["REQ_001"]},
        "mixed": {
            "REQ_001": ["REQ_001"],
            "REQ_002": ["REQ_001"],
            "SP_001": ["REQ_002"],
        },
        "per_type": {
            "REQ_001": ["REQ_001"],
            "REQ_002": ["REQ_001"],
            "SP_001": ["SP_001"],
        },
        "none_default": {
            "REQ_001": ["REQ_002"],
            "REQ_002": ["REQ_002"],
            "SP_001": ["REQ_002"],
        },
        "extra": {
            "REQ_001": ["REQ_001"],
            "REQ_002": ["REQ_001"],
            "SP_001": ["REQ_001"],
        },
    }


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_field_defaults",
        }
    ],
    indirect=True,
)
def test_doc_field_defaults(test_app, snapshot):
    test_app.build()
    warning_records = build_warnings(test_app)
    assert warning_records == [
        "WARNING: needs_fields['bad_value_type']['default'] value is incorrect: Invalid value for field 'bad_value_type': 1.27 [needs.config]",
        "WARNING: needs_fields['too_many_params']['predicates'] value is incorrect: defaults must be a list of (filter, value) pairs. [needs.config]",
        "WARNING: needs_links['link3']['default'] value is incorrect: Invalid value for field 'link3': 1 [needs.config]",
    ]

    needs_schema = SphinxNeedsData(test_app.env).get_schema()
    assert {
        s.name: {"default": s.default, "predicate_defaults": s.predicate_defaults}
        for s in needs_schema.iter_all_fields()
    } == snapshot(name="field_defaults_schema")

    json_data = Path(test_app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(
        name="field_defaults_needs", exclude=props("created", "project", "creator")
    )


def _needs(app) -> dict[str, dict]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


#: per ``conf.py`` confval: its value before and after, the option the needs are
#: written with, the field read, and its value before and after on both needs
REREAD_CASES = {
    "needs_fields": (
        'needs_fields = {"owner": {"schema": {"type": "string"}}}\n',
        'needs_fields = {"owner": {"schema": {"type": "string"}, "default": "alice"}}\n',
        "",
        "owner",
        None,
        "alice",
    ),
    # the legacy entry reads no default: the schema an authored value is converted by
    "needs_extra_options": (
        'needs_extra_options = [{"name": "hours"}]\n',
        'needs_extra_options = [{"name": "hours", "schema": {"type": "number"}}]\n',
        "   :hours: 3\n",
        "hours",
        "3",
        3.0,
    ),
    "needs_links": (
        'needs_links = {"covers": {}}\n',
        'needs_links = {"covers": {"default": ["REQ_001"]}}\n',
        "",
        "covers",
        [],
        ["REQ_001"],
    ),
    "needs_extra_links": (
        'needs_extra_links = [{"option": "covers"}]\n',
        'needs_extra_links = [{"option": "covers", "default": ["REQ_001"]}]\n',
        "",
        "covers",
        [],
        ["REQ_001"],
    ),
    "needs_global_options": (
        'needs_fields = {"owner": {"schema": {"type": "string"}}}\n',
        'needs_fields = {"owner": {"schema": {"type": "string"}}}\n'
        'needs_global_options = {"owner": {"default": "alice"}}\n',
        "",
        "owner",
        None,
        "alice",
    ),
}

REREAD_HEAD = 'extensions = ["sphinx_needs"]\nneeds_build_json = True\n'


def _reread_files(confval: str) -> list[tuple[Path, str]]:
    before, _, option, *_ = REREAD_CASES[confval]
    return [
        (Path("conf.py"), REREAD_HEAD + before),
        (
            Path("index.rst"),
            "Index\n=====\n\n.. toctree::\n\n   other\n\n"
            f".. req:: One\n   :id: REQ_001\n{option}",
        ),
        (Path("other.rst"), f"Other\n=====\n\n.. req:: Two\n   :id: REQ_002\n{option}"),
    ]


@pytest.mark.parametrize(
    ("test_app", "confval"),
    [
        pytest.param(
            {"buildername": "needs", "files": _reread_files(confval)},
            confval,
            id=confval,
        )
        for confval in REREAD_CASES
    ],
    indirect=["test_app"],
)
def test_a_changed_configuration_rereads_every_document(test_app, make_app, confval):
    """A ``default`` (or a legacy option's ``schema``) added in ``conf.py`` between two
    builds applies at once, to the needs of documents that did not change.

    Each of the five confvals is read by every need as it is created, so a change to
    one re-reads every document: before, the second build kept the needs as the first
    build created them (``needs_extra_options``'s ``hours`` the text ``"3"``).
    """
    _, after, _, field, old, new = REREAD_CASES[confval]
    app = test_app
    app.build()
    assert {i: n[field] for i, n in _needs(app).items()} == {
        "REQ_001": old,
        "REQ_002": old,
    }

    conf = Path(app.srcdir, "conf.py")
    conf.write_text(REREAD_HEAD + after, encoding="utf-8")
    # newer than the first build, whatever the file system's clock resolution
    later = time.time_ns() + 60_000_000_000
    os.utime(conf, ns=(later, later))

    second = make_app(buildername="needs", srcdir=app.srcdir)
    second.build()
    assert {i: n[field] for i, n in _needs(second).items()} == {
        "REQ_001": new,
        "REQ_002": new,
    }
    assert f"[config changed ('{confval}')] 2 added" in second._status.getvalue()
