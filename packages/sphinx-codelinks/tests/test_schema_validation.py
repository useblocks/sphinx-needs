"""Regression test for sphinx-needs schema validation of sphinx-codelinks fields.

sphinx-codelinks registers extra fields (``project``, ``file``, ``directory``
and, when enabled, the local/remote url fields) with sphinx-needs. These fields
are attached to *every* need in the project.

When a user defines a strict sphinx-needs schema that forbids any field beyond
the core ``id`` / ``title`` / ``type`` (``unevaluatedProperties: false``), those
registered fields must not be treated as "additional" fields for needs that
never populate them. The fields therefore have to be registered with a typed
schema, so unset values default to ``None`` and are stripped before schema
validation (an untyped field defaults to ``""``, which is not stripped and trips
``unevaluatedProperties: false``).
"""

from collections.abc import Callable
from inspect import signature
import json
from pathlib import Path
import shutil

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx_needs.api import add_extra_option  # type: ignore[import-untyped]

# Schema validation (needs_schema_definitions) arrived in sphinx-needs 6.0.0,
# the same release where add_extra_option gained its ``schema`` keyword. Probe
# that keyword to gate the test, instead of pulling in ``packaging`` for a
# version comparison.
SN_SUPPORTS_SCHEMAS = "schema" in signature(add_extra_option).parameters


@pytest.mark.skipif(
    not SN_SUPPORTS_SCHEMAS,
    reason="needs_schema_definitions requires sphinx-needs>=6.0.0",
)
def test_strict_schema_ignores_unset_codelinks_fields(
    tmp_path: Path,
    make_app: Callable[..., SphinxTestApp],
) -> None:
    this_file_dir = Path(__file__).parent
    sphinx_project = Path("doc_test") / "schema_strictness"
    sphinx_src_dir = tmp_path / sphinx_project
    shutil.copytree(
        this_file_dir / sphinx_project,
        sphinx_src_dir,
        dirs_exist_ok=True,
    )

    app: SphinxTestApp = make_app(srcdir=sphinx_src_dir, freshenv=True)
    app.build()

    report = json.loads(
        (Path(app.outdir) / "schema_violations.json").read_text(encoding="utf-8")
    )

    # Schema validation actually ran over our need ...
    assert report["validated_needs_count"] >= 1

    # ... and produced no violations. If sphinx-codelinks registered its fields
    # untyped (default ""), REQ_1 would carry empty project/file/directory values
    # and the strict schema would (wrongly) report
    # "unevaluated properties are not allowed".
    assert report["validation_warnings"] == {}, (
        "Strict schema flagged unset sphinx-codelinks fields: "
        f"{json.dumps(report['validation_warnings'], indent=2)}"
    )
