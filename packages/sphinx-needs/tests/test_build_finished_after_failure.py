"""A build that fails keeps its own error: the output writers sphinx-needs connects to
``build-finished`` write nothing when the build has already failed.

Sphinx emits ``build-finished`` with the exception that stopped the build and then
re-raises it, unless a handler raises in turn: the handler's error then replaces the
build's. A writer that went on to read a schema the failed build never created raised
``Needs schema has not been initialized yet``, so the user saw that message, and the real
cause only in the chained traceback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sphinx.errors import ExtensionError

from sphinx_needs import builder

CONF = """\
extensions = ["sphinx_needs"]
{option}


def _fail(app, env, docnames):
    raise RuntimeError("the real cause")


def setup(app):
    app.connect("env-before-read-docs", _fail, priority=1)
"""


def _project(option: str) -> dict[str, Any]:
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), CONF.format(option=option)),
            (Path("index.rst"), "Case\n====\n\n.. req:: A\n   :id: REQ_1\n"),
        ],
    }


@pytest.mark.parametrize(
    "test_app",
    [
        _project("needs_build_json = True"),
        _project("needs_build_json_per_id = True"),
        _project('needs_build_needumls = "umls"'),
    ],
    indirect=True,
    ids=["build_json", "build_json_per_id", "build_needumls"],
)
def test_a_failed_build_raises_its_own_error(
    test_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each output writer returns at once when the build has failed, so the build's own
    exception is the one raised, not a writer's complaint about the missing schema.

    The needumls writer reads no schema, so it went on quietly and wrote whatever a
    failed build left behind; its ``finish`` is made to raise here, so that a writer
    that runs after a failure shows up as the error the build raises.
    """
    monkeypatch.setattr(builder.NeedumlsBuilder, "finish", _written_after_failure)
    with pytest.raises(ExtensionError) as exc_info:
        test_app.build()
    assert "for event 'env-before-read-docs'" in str(exc_info.value)
    cause = exc_info.value.orig_exc
    assert isinstance(cause, RuntimeError)
    assert str(cause) == "the real cause"


def _written_after_failure(self: Any) -> None:
    raise AssertionError("an output writer ran after the build failed")
