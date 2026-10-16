"""Where ``needs-before-post-processing`` and ``needs-before-sealing`` fire.

An extension that writes into the needs at ``needs-before-post-processing`` writes into
the needs themselves, before every ``needextend``: its write stands where no
``needextend`` touches the field, and a document's ``needextend`` overrides it. A handler
of ``needs-before-sealing`` sees the needs after the ``needextend`` directives are
applied and the dynamic functions are resolved.
Both are emitted in the main process, so a ``-j 2`` build gives the same result.
A handler of either cannot set a derived field: it holds what its rule computes, and
the write raises ``KeyError``, which fails the build.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from sphinx.application import Sphinx
from sphinx.errors import ExtensionError

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings
from tests.util import needs_by_id, serial_and_parallel

CONF = """\
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

extensions = ["sphinx_needs", "event_order_ext"]
needs_build_json = True
needs_fields = {"copied": {"schema": {"type": "string"}}}
"""

# what each handler saw of REQ_1, in the order they were called; written by the last of
# them. REQ_2 is written by the extension and touched by no needextend
EXTENSION = """\
import json
from pathlib import Path


def setup(app):
    seen = []

    def record(event, need):
        seen.append([event, need["status"], need["copied"]])

    def before_post_processing(app, needs):
        record("needs-before-post-processing", needs["REQ_1"])
        needs["REQ_1"]["status"] = "ext"
        needs["REQ_2"]["status"] = "ext"

    def before_sealing(app, needs):
        record("needs-before-sealing", needs["REQ_1"])
        Path(app.outdir, "seen.json").write_text(json.dumps(seen), encoding="utf-8")

    app.connect("needs-before-post-processing", before_post_processing)
    app.connect("needs-before-sealing", before_sealing)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
"""

INDEX = """\
Index
=====

.. toctree::

   a

.. req:: One
   :id: REQ_1
   :status: open
   :copied: [[copy("id")]]

.. req:: Two
   :id: REQ_2
"""

A = """\
A
=

.. needextend:: REQ_1
   :status: user
"""


@pytest.mark.parametrize(
    "test_app",
    serial_and_parallel(
        [
            (Path("conf.py"), CONF),
            (Path("event_order_ext.py"), EXTENSION),
            (Path("index.rst"), INDEX),
            (Path("a.rst"), A),
        ]
    ),
    indirect=True,
)
def test_needextend_overrides_an_extension_and_is_seen_at_sealing(test_app: Sphinx):
    """The extension writes into the needs first, the ``needextend`` wins, sealing sees it.

    M5 and M6 move one emit across ``extend_needs_data``; MR1 hands the first handler a
    copy, which only ``REQ_2`` shows; MR2 emits ``needs-before-sealing`` before the
    dynamic functions are resolved, which only ``copied`` shows.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []

    needs = needs_by_id(app)
    assert needs["REQ_1"]["status"] == "user"
    assert needs["REQ_1"]["modifications"] == 1
    assert needs["REQ_1"]["copied"] == "REQ_1"
    assert needs["REQ_2"]["status"] == "ext"
    assert needs["REQ_2"]["modifications"] == 0

    seen = json.loads(Path(app.outdir, "seen.json").read_text(encoding="utf-8"))
    assert seen == [
        ["needs-before-post-processing", "open", None],
        ["needs-before-sealing", "user", "REQ_1"],
    ]


DERIVED_CONF = """\
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

extensions = ["sphinx_needs", "{extension}"]
needs_fields = {
    "plain": {"schema": {"type": "string"}, "nullable": True},
    "copied": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "title"},
    },
}
"""

DERIVED_INDEX = """\
Index
=====

.. req:: One
   :id: REQ_1
"""


def _writing_extension(event: str, field: str) -> str:
    """An extension whose ``event`` handler writes ``field`` of ``REQ_1``."""
    return (
        "def setup(app):\n"
        "    def write(app, needs):\n"
        f"        needs['REQ_1'][{field!r}] = 'ext'\n"
        "\n"
        f"    app.connect({event!r}, write)\n"
        "    return {'parallel_read_safe': True, 'parallel_write_safe': True}\n"
    )


def _derived_write_project(event: str, field: str) -> dict[str, Any]:
    # a module of its own for each project: an extension module is imported once
    extension = f"write_{field}_{event.replace('-', '_')}"
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), DERIVED_CONF.replace("{extension}", extension)),
            (Path(f"{extension}.py"), _writing_extension(event, field)),
            (Path("index.rst"), DERIVED_INDEX),
        ],
    }


EVENTS = ("needs-before-post-processing", "needs-before-sealing")


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(_derived_write_project(event, "copied"), id=event)
        for event in EVENTS
    ],
    indirect=True,
)
def test_an_extension_cannot_set_a_derived_field(test_app: Sphinx):
    """A handler of either event writing a derived field fails the build, the field
    named: before post-processing the rule would overwrite the value, before sealing
    it would keep it."""
    app = test_app
    with pytest.raises(ExtensionError) as excinfo:
        app.build()
    cause = excinfo.value.__cause__
    assert isinstance(cause, KeyError)
    assert cause.args == (
        "Cannot set derived field 'copied' in NeedItem: its value is computed by its "
        "derive rule.",
    )


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(_derived_write_project(event, "plain"), id=event)
        for event in EVENTS
    ],
    indirect=True,
)
def test_an_extension_sets_a_field_without_a_rule(test_app: Sphinx):
    """The same handler writing a field without a rule sets it; every need of the build
    refuses a write to the derived field, with the schema's one set of names."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = needs_by_id(app)
    assert needs["REQ_1"]["plain"] == "ext"
    assert needs["REQ_1"]["copied"] == "One"

    data = SphinxNeedsData(app.env)
    need = data.get_needs_view()["REQ_1"]
    assert need._derived is data.get_schema().derived_names
    with pytest.raises(KeyError, match=r"Cannot set derived field 'copied'"):
        need["copied"] = "other"
