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
        'WARNING: Config option "needs_global_options" is deprecated. Please use needs_fields and needs_extra_links instead. [needs.deprecated]',
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
        "WARNING: needs_extra_links['link3']['default'] value is incorrect: Invalid value for field 'link3': 1 [needs.config]",
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
