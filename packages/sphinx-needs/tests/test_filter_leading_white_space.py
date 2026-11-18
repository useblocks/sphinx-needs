"""A filter string is read past the leading characters Python's ``eval`` reads past.

``eval`` of a string reads past its leading spaces and tabs, and nothing else: a form feed
or a newline is the tokenizer's own reading, which ``compile`` shares, and a newline or a
form feed followed by a space is refused by both. The constant check, a constraint and a
link condition (``filter_single_need``) read a filter as ``eval`` does; the views,
``needs_warnings``, ``needs_builder_filter``, a ``needpie`` / ``needbar`` content line and
needuml's ``filter()`` compile it, and now read it the same way, so the same string
selects the same needs at every place, whichever tier answers it. A message quoting the
filter quotes it as written.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from sphinx_needs import filter_common
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs.filter_common import (
    _filter_tier,
    _python_expression_error,
    filter_needs_and_parts,
    filter_needs_parts,
    filter_needs_view,
    filter_single_need,
)
from sphinx_needs_testkit import build_warnings
from tests.util import chart_images, pie_slice_counts

#: what ``eval`` reads past: none, a space, a tab, and a mix
PADS = {"none": "", "space": " ", "two spaces": "  ", "tab": "\t", "mix": " \t "}

#: one filter per tier, as the tier that answers it unpadded (pinned in the test)
TIER_FILTERS = {
    "index": "status == 'open'",
    "fast": "status == 'open' or 'x' in tags",
    "eval": "status == 'open' and [t for t in tags] == []",
}

INDEX = """\
Index
=====

.. req:: One
   :id: REQ_001
   :status: open

.. req:: Two
   :id: REQ_002
   :status: closed

.. needpie:: pie
   :labels: open, closed

   {pie_line}
   status == 'closed'

.. needuml::

   {{% for n in filter({uml_filter!r}) %}}
   card "{{{{ n.id }}}}"
   {{% endfor %}}
"""

CONF = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
needs_build_json = True
needs_warnings = {{"w": {filter!r}}}
needs_warnings_always_warn = True
needs_builder_filter = {filter!r}
"""


def _project(pad: str) -> dict[str, Any]:
    filter_string = f"{pad}status == 'open'"
    # a content line keeps what it is indented by beyond the block; docutils turns a
    # tab into spaces, so a padded line is padded with a space
    pie_line = f"{' ' if pad else ''}status == 'open'"
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), CONF.format(filter=filter_string)),
            (
                Path("index.rst"),
                INDEX.format(pie_line=pie_line, uml_filter=filter_string),
            ),
        ],
    }


@pytest.mark.parametrize(
    ("test_app", "pad"),
    [pytest.param(_project(pad), pad, id=name) for name, pad in PADS.items()],
    indirect=["test_app"],
)
def test_every_place_that_compiles_a_filter_reads_the_padding_past(
    test_app: Any, pad: str
) -> None:
    """``needs_warnings``, ``needs_builder_filter``, a ``needpie`` content line and
    needuml's ``filter()`` select the open need whatever leading spaces and tabs the
    string has, as the unpadded string does; the ``needs_warnings`` report quotes the
    filter as written."""
    app = test_app
    app.build()
    filter_string = f"{pad}status == 'open'"
    assert build_warnings(app) == [
        "WARNING: w: failed\n\t\tfailed needs: 1 (REQ_001)\n\t\t"
        f"used filter: {filter_string} [needs.warnings]"
    ]
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = data["versions"][data["current_version"]]["needs"]
    assert sorted(needs) == ["REQ_001"]
    images = chart_images(Path(app.outdir, "index.html").read_text(encoding="utf-8"))
    svg = Path(app.outdir, "_images", images["pie"]).read_text(encoding="utf-8")
    assert pie_slice_counts(svg) == [1, 1]
    (uml,) = SphinxNeedsData(app.env).get_or_create_umls().values()
    assert 'card "REQ_001"' in uml["content_calculated"]
    assert "REQ_002" not in uml["content_calculated"]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "dummy", "files": _project("")["files"]}],
    indirect=True,
)
def test_each_tier_gives_the_padded_string_the_unpadded_answer(test_app: Any) -> None:
    """For a filter of each tier, with each padding ``eval`` reads past: the views'
    routes (``filter_needs_view``, ``filter_needs_parts``), the delegate they call
    (``filter_needs_and_parts``) and the need-by-need route (``filter_single_need``) all
    select what the unpadded string selects, and nothing is reported."""
    app = test_app
    app.build()
    view = SphinxNeedsData(app.env).get_needs_view()
    config = NeedsSphinxConfig(app.config)
    for tier, unpadded in TIER_FILTERS.items():
        assert _filter_tier(unpadded)[0] == tier, unpadded
        expected = ["REQ_001"]
        for name, pad in PADS.items():
            filter_string = pad + unpadded
            where = f"{tier} tier, {name}"
            with patch.object(filter_common, "log_warning") as warn:
                found = {
                    "view": [
                        n["id"] for n in filter_needs_view(view, config, filter_string)
                    ],
                    "parts": [
                        n["id"]
                        for n in filter_needs_parts(
                            view.to_list_with_parts(), config, filter_string
                        )
                    ],
                    "delegate": [
                        n["id"]
                        for n in filter_needs_and_parts(
                            view.values(), config, filter_string
                        )
                    ],
                    "single": [
                        need["id"]
                        for need in view.values()
                        if filter_single_need(need, config, filter_string)
                    ],
                }
            assert found == dict.fromkeys(found, expected), where
            assert warn.call_args_list == [], where


#: leading text ``eval`` does not read past, and refuses: no more is read past than it
REFUSED_BY_EVAL = {
    "newline then space": "\n status == 'open'",
    "form feed then space": "\f status == 'open'",
    "vertical tab": "\vstatus == 'open'",
}


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "dummy", "files": _project("")["files"]}],
    indirect=True,
)
def test_no_more_is_read_past_than_eval_reads_past(test_app: Any) -> None:
    """A string ``eval`` refuses is refused at every place: a view reports it, quoting
    it as written, and selects nothing; a need-by-need place raises, as before."""
    app = test_app
    app.build()
    view = SphinxNeedsData(app.env).get_needs_view()
    config = NeedsSphinxConfig(app.config)
    for name, filter_string in REFUSED_BY_EVAL.items():
        with pytest.raises(SyntaxError):
            eval(filter_string, {"status": "open"})
        with patch.object(filter_common, "log_warning") as warn:
            assert filter_needs_view(view, config, filter_string) == [], name
        ((args, _),) = warn.call_args_list
        assert args[1].startswith(f"Filter {filter_string!r} not valid. Error: "), name
        assert args[2] == "filter", name
        with pytest.raises(NeedsInvalidFilter):
            filter_single_need(view["REQ_001"], config, filter_string)


@pytest.mark.parametrize("pad", [" ", "\t", " \t"])
def test_the_check_of_a_string_reads_the_padding_past(pad: str) -> None:
    """The check the views make of a string that fails their delegate reads the padding
    past as the delegate does: a padded expression is one."""
    assert _python_expression_error(f"{pad}status == 'open'") is None
    unpadded = _python_expression_error("status ==")
    padded = _python_expression_error(f"{pad}status ==")
    assert unpadded is not None and padded is not None
    assert str(padded) == str(unpadded)


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "dummy", "files": _project("")["files"]}],
    indirect=True,
)
def test_a_padded_string_that_is_no_expression_is_quoted_as_written(
    test_app: Any,
) -> None:
    """A padded string that is no expression is reported with the error of what follows
    the padding, quoting the string as written."""
    app = test_app
    app.build()
    view = SphinxNeedsData(app.env).get_needs_view()
    config = NeedsSphinxConfig(app.config)
    error = _python_expression_error("status ==")
    for pad in (" ", "\t"):
        filter_string = f"{pad}status =="
        with patch.object(filter_common, "log_warning") as warn:
            assert filter_needs_view(view, config, filter_string) == []
        ((args, _),) = warn.call_args_list
        assert args[1] == f"Filter {filter_string!r} not valid. Error: {error}."


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "dummy", "files": _project("")["files"]}],
    indirect=True,
)
def test_a_padded_string_that_fails_on_a_need_is_quoted_as_written(
    test_app: Any,
) -> None:
    """A padded string that compiles and fails as it is evaluated, need by need, is
    reported once, quoting the string as written, and selects nothing."""
    app = test_app
    app.build()
    view = SphinxNeedsData(app.env).get_needs_view()
    config = NeedsSphinxConfig(app.config)
    for pad in (" ", "\t"):
        filter_string = f"{pad}status == 'open' and nosuch"
        with patch.object(filter_common, "log_warning") as warn:
            assert filter_needs_view(view, config, filter_string) == []
        ((args, _),) = warn.call_args_list
        assert args[1].startswith(f"Filter {filter_string!r} not valid. Error: ")
        assert args[2] == "filter"
