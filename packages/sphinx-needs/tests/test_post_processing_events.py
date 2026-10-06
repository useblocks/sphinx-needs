"""Where ``needs-before-post-processing`` and ``needs-before-sealing`` fire.

An extension that writes into the needs at ``needs-before-post-processing`` writes into
the needs themselves, before every ``needextend``: its write stands where no
``needextend`` touches the field, and a document's ``needextend`` overrides it. A handler
of ``needs-before-sealing`` sees the needs after the ``needextend`` directives are
applied and the dynamic functions are resolved.
Both are emitted in the main process, so a ``-j 2`` build gives the same result.
"""

import json
from pathlib import Path

import pytest
from sphinx.application import Sphinx

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
