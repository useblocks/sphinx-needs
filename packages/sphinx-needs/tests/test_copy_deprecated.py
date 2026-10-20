"""``copy = true`` on a link type is deprecated, in favour of a ``union`` link type.

The links are still copied into ``links`` as before; each declaration that writes
``copy = true`` is one ``needs.deprecated`` warning, naming the declaration, the release
removing the key and the ``union`` that replaces it. A declaration writing ``copy =
false``, the implicit ``links``, and one whose ``copy`` another finding already refuses
(a derived link type's, a need type's entry of a link type declared outright) are not.
"""

import json
from pathlib import Path

import pytest

from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True
needs_extra_links = [{"option": "checks", "copy": True}]
"""

TOML = """\
[needs.links.blocks]
copy = true

[needs.links.tests]
copy = false

[needs.links.covers]
derive = { kind = "links", where = "type == 'req'" }
copy = true

[needs.types.req]
title = "Requirement"
prefix = "R_"

[needs.types.req.links.verifies]
copy = true

[needs.types.spec]
title = "Specification"
prefix = "S_"

[needs.types.spec.links.verifies]
copy = true

[needs.types.spec.links.blocks]
copy = true

[needs.types.impl]
title = "Implementation"
prefix = "I_"

[needs.types.impl.links.cites]
derive = { kind = "links", where = "type == 'spec'" }
copy = true
"""

INDEX = """\
Copy
====

.. req:: One
   :id: R_001

.. req:: Two
   :id: R_002

.. req:: Three
   :id: R_003

.. req:: Four
   :id: R_004

.. spec:: Copies
   :id: S_001
   :blocks: R_001
   :tests: R_002
   :checks: R_003
   :verifies: R_004
"""


def _deprecated(where: str, name: str) -> str:
    return (
        f"WARNING: {where} sets 'copy = true', which is deprecated and will be removed "
        "in sphinx-needs 10.0; declare a link type deriving the union instead, e.g. "
        f'derive = {{kind = "union", fields = ["links", "{name}"]}}, and read it where '
        "the copies in links were read [needs.deprecated]"
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("ubproject.toml"), TOML),
                (Path("index.rst"), INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_each_declaration_writing_copy_is_deprecated(test_app):
    """One warning per declaration writing ``copy = true``: a ``needs_links`` entry
    (here from ``ubproject.toml``), a ``needs_extra_links`` entry, and each need type's
    entry of a link type need types alone declare, the first root and a later one
    alike. None for ``copy = false`` or the implicit ``links``; none beside a
    ``derive``, where ``copy`` is refused, nor in a need type's entry of a link type
    declared outright, where the key is refused. What is copied is unchanged."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        'WARNING: Config option "needs_extra_links" is deprecated. Please use '
        '"needs_links" instead. [needs.deprecated]',
        _deprecated("needs_links['blocks']", "blocks"),
        _deprecated("needs_extra_links['checks']", "checks"),
        "WARNING: Invalid derive of link type 'cites': by need type: 'copy' is not "
        "available on a derived link type in this release, and is ignored; the rule "
        "applies [needs.derive_invalid]",
        "WARNING: Invalid derive of link type 'covers': kind 'links': 'copy' is not "
        "available on a derived link type in this release, and is ignored; the rule "
        "applies [needs.derive_invalid]",
        _deprecated("needs_types['req'].links['verifies']", "verifies"),
        _deprecated("needs_types['spec'].links['verifies']", "verifies"),
        "WARNING: needs_types['spec'].links['blocks'] sets 'copy', which a need type "
        "gives only a link type declared on need types alone; 'blocks' keeps its own "
        "on every need type and the key is ignored [needs.config]",
    ]
    data = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    spec = data["versions"][data["current_version"]]["needs"]["S_001"]
    # blocks, checks and verifies copied; tests (copy = false) not
    assert spec["links"] == ["R_001", "R_003", "R_004"]
