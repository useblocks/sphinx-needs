import json
import os
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from syrupy.extensions import AmberSnapshotExtension
from syrupy.filters import props

from sphinx_needs.data import SphinxNeedsData


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
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_doc_global_option(test_app, snapshot):
    test_app.build()
    warnings = strip_colors(
        test_app._warning.getvalue().replace(str(test_app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == [
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
            "no_plantuml": True,
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

    warnings = strip_colors(
        test_app._warning.getvalue().replace(str(test_app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == [
        "srcdir/index.rst:4: WARNING: needs_fields['with_default']['predicates']: "
        "Predicate \"section_name == 'Test'\" not valid. "
        "Error: name 'section_name' is not defined. "
        "The predicate is skipped. [needs.config]",
        "srcdir/index.rst:4: WARNING: needs_fields['without_default']['predicates']: "
        "Predicate \"section_name == 'Test'\" not valid. "
        "Error: name 'section_name' is not defined. "
        "The predicate is skipped. [needs.config]",
        "srcdir/index.rst:4: WARNING: needs_fields['later_predicate']['predicates']: "
        "Predicate \"section_name == 'Test'\" not valid. "
        "Error: name 'section_name' is not defined. "
        "The predicate is skipped. [needs.config]",
        "srcdir/index.rst:4: WARNING: needs_links['blocks']['predicates']: "
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


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_field_defaults",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_doc_field_defaults(test_app, snapshot):
    test_app.build()
    warnings = strip_colors(
        test_app._warning.getvalue().replace(str(test_app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == [
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
