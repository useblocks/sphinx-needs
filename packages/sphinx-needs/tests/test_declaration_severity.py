"""The ``severity`` of a need type's declaration, where the corpus cannot pin it.

The fields-per-type conformance corpus pins what a severity does to a need and its
findings; it compares no message and no ``needs.config`` finding, which are each
tool's own. These tests pin sphinx-needs' wording: which need type a lowered severity
is reported against, and the warning for a ``severity`` on an entry that takes none.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sphinx_needs_testkit import build_warnings

CONF_PY = 'extensions = ["sphinx_needs"]\nneeds_from_toml = "ubproject.toml"\n'


def _project(toml: str, source: str = "") -> dict[str, Any]:
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), CONF_PY),
            (Path("ubproject.toml"), toml),
            (Path("index.rst"), "Case\n====\n\n" + source),
        ],
    }


LOWERED = """\
[needs.fields.category]
schema = { type = "string", enum = ["a", "b"] }

[needs.links.satisfies]

[needs.types.req]
title = "Requirement"
prefix = "R_"

[needs.types.req.fields.category]
severity = "warning"

[needs.types.req.back_links.satisfies]
schema = { minItems = 1 }
severity = "warning"

[needs.types.mid]
title = "Mid"
prefix = "M_"
inherits = "req"

[needs.types.mid.fields.category]
description = "Narrowed, its severity kept"

[needs.types.mid.back_links.satisfies]
description = "Narrowed, its severity kept"

[needs.types.leaf]
title = "Leaf"
prefix = "L_"
inherits = "mid"

[needs.types.leaf.fields.category]
severity = "info"

[needs.types.leaf.back_links.satisfies]
severity = "info"
"""


@pytest.mark.parametrize("test_app", [_project(LOWERED)], indirect=True)
def test_a_lowered_severity_names_the_type_that_gave_it(test_app: Any) -> None:
    """A severity lowered under an ancestor's is reported as the type whose entry
    gave the severity declares it (``req``), not the nearest type with an entry of the
    field (``mid``, whose entry gives none and keeps ``req``'s)."""
    test_app.build()
    assert build_warnings(test_app) == [
        f"WARNING: needs_types['leaf'].{table}[{name!r}] widens the field as need "
        "type 'req' declares it: Child 'severity' 'info' is lower than parent "
        "'severity' 'warning'. [needs.type_widening]"
        for table, name in (("fields", "category"), ("back_links", "satisfies"))
    ]


GLOBAL = """\
[needs.fields.asil]
schema = { type = "string", enum = ["QM", "A"] }
severity = "warning"

[needs.links.blocks]
severity = "info"

[needs.types.req]
title = "Requirement"
prefix = "R_"
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(GLOBAL, ".. req:: Outside the enum\n   :id: REQ_1\n   :asil: B\n")],
    indirect=True,
)
def test_a_severity_on_a_global_entry_is_reported_and_ignored(test_app: Any) -> None:
    """A ``severity`` is a need type's declaration's: on a ``needs_fields`` or
    ``needs_links`` entry it is one ``needs.config`` warning, and ignored, so the
    field still fails as a violation."""
    test_app.build()
    warnings = build_warnings(test_app)
    assert warnings[:2] == [
        "WARNING: needs_fields['asil'] sets 'severity', which is declared on a need "
        "type's entry ([needs.types.<type>.fields.asil]); it is ignored here "
        "[needs.config]",
        "WARNING: needs_links['blocks'] sets 'severity', which is declared on a need "
        "type's entry ([needs.types.<type>.links.blocks]); it is ignored here "
        "[needs.config]",
    ]
    assert len(warnings) == 3
    assert warnings[2].startswith("ERROR: Need 'REQ_1' has schema violations:")
    assert warnings[2].endswith("[sn_schema_violation.field_fail]")
