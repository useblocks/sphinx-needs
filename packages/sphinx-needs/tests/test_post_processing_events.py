"""Where ``needs-before-post-processing`` and ``needs-before-sealing`` fire.

An extension that writes into the needs at ``needs-before-post-processing`` is applied
before every ``needextend``, so a document's ``needextend`` overrides it; a handler of
``needs-before-sealing`` sees the needs after the ``needextend`` directives are applied.
Both are emitted in the main process, so a ``-j 2`` build gives the same result.
"""

import json
from pathlib import Path

import pytest
from sphinx.application import Sphinx

from sphinx_needs_testkit import build_warnings
from tests.test_needextend_priority import needs_by_id, serial_and_parallel

CONF = """\
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

extensions = ["sphinx_needs", "event_order_ext"]
needs_build_json = True
"""

# what each handler saw, in the order they were called; written by the last of them
EXTENSION = """\
import json
from pathlib import Path


def setup(app):
    seen = []

    def before_post_processing(app, needs):
        seen.append(["needs-before-post-processing", needs["REQ_1"]["status"]])
        needs["REQ_1"]["status"] = "ext"

    def before_sealing(app, needs):
        seen.append(["needs-before-sealing", needs["REQ_1"]["status"]])
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
    """M5, M6: the extension writes first, the ``needextend`` wins, sealing sees it."""
    app = test_app
    app.build()
    assert build_warnings(app) == []

    need = needs_by_id(app)["REQ_1"]
    assert need["status"] == "user"
    assert need["modifications"] == 1

    seen = json.loads(Path(app.outdir, "seen.json").read_text(encoding="utf-8"))
    assert seen == [
        ["needs-before-post-processing", "open"],
        ["needs-before-sealing", "user"],
    ]
