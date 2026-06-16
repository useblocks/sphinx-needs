"""Regression test for sphinx-needs schema validation of sphinx-test-reports fields.

sphinx-test-reports registers a number of extra fields (``file``, ``suite``,
``case``, ``passed``, ``failed``, ``errors`` ...) with sphinx-needs via its
field API. These fields are attached to *every* need in the project.

When a user defines a strict sphinx-needs schema -- one that forbids any field
beyond the core ``id`` / ``title`` / ``type`` (``unevaluatedProperties: false``)
-- those registered fields must not be treated as "additional" fields for needs
that never populate them. In other words, the fields have to default to an
unset/None value so they are stripped before schema validation.

This test builds a project with both extensions enabled and a strict schema,
and asserts that plain needs which leave the sphinx-test-reports fields
unpopulated produce no schema violation.
"""

import json
from pathlib import Path

import pytest
import sphinx_needs
from packaging.version import Version

# The needs_schema_definitions / schema-validation feature was introduced in
# sphinx-needs 6.0.0; skip on older versions that do not support it.
SN_SUPPORTS_SCHEMAS = Version(sphinx_needs.__version__) >= Version("6.0.0")


@pytest.mark.skipif(
    not SN_SUPPORTS_SCHEMAS,
    reason="needs_schema_definitions requires sphinx-needs>=6.0.0",
)
@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/schema_strictness"}],
    indirect=True,
)
def test_strict_schema_ignores_unpopulated_test_report_fields(test_app):
    app = test_app
    app.build()

    assert app.statuscode == 0

    report_file = Path(app.outdir, "schema_violations.json")
    assert report_file.exists(), "sphinx-needs did not write schema_violations.json"

    report = json.loads(report_file.read_text(encoding="utf-8"))

    # Schema validation actually ran over our two needs ...
    assert report.get("validated_needs_count", 0) >= 2

    # ... and produced no violations. If sphinx-test-reports registered its
    # fields with non-null defaults, REQ_1/REQ_2 would carry empty values for
    # file/suite/passed/... and the strict schema would (wrongly) report
    # "unevaluated properties are not allowed".
    assert report["validation_warnings"] == {}, (
        "Strict schema flagged unpopulated sphinx-test-reports fields: "
        f"{json.dumps(report['validation_warnings'], indent=2)}"
    )


@pytest.mark.skipif(
    not SN_SUPPORTS_SCHEMAS,
    reason="needs_schema_definitions requires sphinx-needs>=6.0.0",
)
@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/schema_strictness_status"}],
    indirect=True,
)
def test_strict_schema_allows_constrained_field_in_local_schema(test_app):
    """Counterpart to the test above: a field that *is* part of the local schema
    validates correctly while the unpopulated sphinx-test-reports fields stay
    ignored.

    The schema evaluates the core ``status`` field (``const: open``, and marks
    it ``required``) and forbids every other field
    (``unevaluatedProperties: false``). The single need sets ``status: open``
    and leaves all sphinx-test-reports fields unpopulated, so the build must
    report no violation.
    """
    app = test_app
    app.build()

    assert app.statuscode == 0

    report_file = Path(app.outdir, "schema_violations.json")
    assert report_file.exists(), "sphinx-needs did not write schema_violations.json"

    report = json.loads(report_file.read_text(encoding="utf-8"))

    # The need was validated ...
    assert report.get("validated_needs_count", 0) >= 1

    # ... and the constrained-and-populated 'status' field plus the stripped
    # (unpopulated) sphinx-test-reports fields together produce no violation.
    assert report["validation_warnings"] == {}, (
        "Strict schema with a constrained 'status' field reported violations: "
        f"{json.dumps(report['validation_warnings'], indent=2)}"
    )
