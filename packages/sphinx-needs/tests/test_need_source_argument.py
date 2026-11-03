"""What the creation API takes as a need's source: ``create_need`` a ``NeedItemSource``
and nothing else; ``generate_need``, ``add_external_need`` and ``ingest_need_record``
still take an object with the ``NeedItemSourceProtocol`` interface alone, with one
``DeprecationWarning`` at the calling line, until 10.0 refuses it there too."""

from __future__ import annotations

from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

#: the start of the deprecation's message, which a ``-W error:<message>`` filter matches
DEPRECATION = "a need_source that is not a NeedItemSource is deprecated"

SOURCE_ARGUMENT_EXT = '''\
"""Gives each entry point a protocol-only source and a ``NeedItemSource``, and keeps
what each call raised and warned."""

import warnings

from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import (
    NeedItemSource,
    NeedSourceHop,
    NeedSourcePhysical,
    add_external_need,
    add_need,
    create_need,
    generate_need,
    ingest_need_record,
)
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData


class ProtocolSource:
    """A source of a third party's own, with the ``NeedItemSourceProtocol`` interface
    alone."""

    def __init__(self, docname, *, external=False):
        self._dict_repr = {
            "docname": None if external else docname,
            "lineno": 7,
            "lineno_content": None,
            "external_url": "http://example.org/x.html" if external else None,
            "is_import": False,
            "is_external": external,
        }

    @property
    def dict_repr(self):
        return self._dict_repr


def caught(call):
    """What ``call`` returned or raised, and the warnings it gave, but Sphinx's own."""
    with warnings.catch_warnings(record=True) as warned:
        warnings.simplefilter("always")
        try:
            outcome = ("returned", call())
        except Exception as err:  # noqa: BLE001
            outcome = ("raised", type(err).__name__, str(err))
    return outcome, [
        (w.category.__name__, str(w.message), w.filename)
        for w in warned
        if not w.category.__name__.startswith("RemovedInSphinx")
    ]


class SourceArgument(SphinxDirective):
    def run(self):
        app, state, docname = self.env.app, self.state, self.env.docname
        config = NeedsSphinxConfig(app.config)
        schema = SphinxNeedsData(self.env).get_schema()
        external_source = NeedItemSource(
            (
                NeedSourceHop(
                    kind="external",
                    physical=NeedSourcePhysical(url="http://example.org/y.html"),
                ),
            )
        )
        sources = {
            "protocol": lambda external=False: ProtocolSource(
                docname, external=external
            ),
            "class": lambda external=False: (
                external_source
                if external
                else NeedItemSource.on_page(docname, lineno=self.lineno)
            ),
        }
        rows = {}
        out = []
        for kind, make in sources.items():
            suffix = kind.upper()
            rows["create_need", kind] = caught(
                lambda: create_need(
                    app, state, make(), "req", "T", id=f"R_CREATE_{suffix}"
                )
            )
            rows["generate_need", kind] = caught(
                lambda: generate_need(
                    config, schema, "req", "T", id=f"R_GEN_{suffix}",
                    need_source=make(),
                )
            )
            rows["add_external_need", kind] = caught(
                lambda: add_external_need(
                    app, "req", "T", id=f"R_EXT_{suffix}",
                    need_source=make(external=True),
                )
            )
            rows["ingest_need_record", kind] = caught(
                lambda: ingest_need_record(
                    app, state, {"type": "req", "title": "T", "id": f"R_REC_{suffix}"},
                    need_source=make(),
                )
            )
            rows["add_need", kind] = caught(
                lambda: add_need(
                    app, state, need_type="req", title="T", id=f"R_ADD_{suffix}",
                    need_source=make(),
                )
            )
            for name in ("create_need", "ingest_need_record", "add_need"):
                outcome = rows[name, kind][0]
                if outcome[0] == "returned":
                    result = outcome[1]
                    out.extend(result[1] if name == "create_need" else (
                        result[0] if name == "ingest_need_record" else result
                    ))
        # no source at all: each function's default, which is no protocol-only source
        rows["generate_need", "none"] = caught(
            lambda: generate_need(config, schema, "req", "T", id="R_GEN_NONE")
        )
        rows["add_external_need", "none"] = caught(
            lambda: add_external_need(
                app, "req", "T", id="R_EXT_NONE",
                external_url="http://example.org/z.html",
            )
        )
        self.env.source_argument_rows = {
            key: (
                outcome if outcome[0] == "raised"
                else ("returned", type(outcome[1]).__name__),
                warned,
            )
            for key, (outcome, warned) in rows.items()
        }
        return out


def setup(app):
    app.add_directive("source-argument", SourceArgument)
    return {"parallel_read_safe": False}
'''


@pytest.fixture
def source_argument(test_app: SphinxTestApp) -> tuple[dict, str, SphinxTestApp]:
    """The rows the extension kept, the path of the extension's file (the line every
    call is made from), and the application."""
    test_app.build()
    assert build_warnings(test_app) == []
    return (
        test_app.env.source_argument_rows,
        str(Path(test_app.srcdir, "source_argument_ext.py")),
        test_app,
    )


SOURCE_ARGUMENT_FILES = [
    (
        Path("conf.py"),
        "import sys\nfrom pathlib import Path\n\n"
        "sys.path.insert(0, str(Path(__file__).parent))\n"
        'sys.modules.pop("source_argument_ext", None)\n'
        'extensions = ["sphinx_needs", "source_argument_ext"]\n',
    ),
    (Path("source_argument_ext.py"), SOURCE_ARGUMENT_EXT),
    (Path("index.rst"), "Sources\n=======\n\n.. source-argument::\n"),
]

pytestmark = pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "files": SOURCE_ARGUMENT_FILES}], indirect=True
)


def _deprecations(warned: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    return [w for w in warned if w[1].startswith(DEPRECATION)]


def test_create_need_refuses_a_protocol_only_source(source_argument):
    """``create_need`` takes a ``NeedItemSource`` alone: any other object is a
    ``TypeError`` naming the two stable constructors, raised before anything is
    recorded, and with no deprecation warning beside it."""
    rows, _, app = source_argument
    outcome, warned = rows["create_need", "protocol"]
    assert outcome == (
        "raised",
        "TypeError",
        "create_need takes a NeedItemSource as its source, not 'ProtocolSource': "
        "NeedItemSource.from_directive(self) in a directive, or "
        "NeedItemSource.on_page(docname, lineno=...) for a need on a page at a line "
        "the caller gives",
    )
    assert _deprecations(warned) == []
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert "R_CREATE_PROTOCOL" not in needs
    # the control: a NeedItemSource creates the need
    assert rows["create_need", "class"][0] == ("returned", "tuple")
    assert "R_CREATE_CLASS" in needs


@pytest.mark.parametrize(
    "entry_point", ["generate_need", "add_external_need", "ingest_need_record"]
)
def test_a_protocol_only_source_is_deprecated_on_the_other_entry_points(
    source_argument, entry_point
):
    """A protocol-only ``need_source`` is one ``DeprecationWarning``, from the line
    that calls the entry point (the extension's file, not sphinx-needs'), naming the
    two stable constructors and the release that refuses it; the need is created as
    before."""
    rows, ext_file, app = source_argument
    outcome, warned = rows[entry_point, "protocol"]
    assert outcome[0] == "returned"
    assert _deprecations(warned) == [
        (
            "DeprecationWarning",
            "a need_source that is not a NeedItemSource is deprecated, and is refused "
            f"from sphinx-needs 10.0 ({entry_point} was given a 'ProtocolSource'): use "
            "NeedItemSource.from_directive(self) in a directive, or "
            "NeedItemSource.on_page(docname, lineno=...)",
            ext_file,
        )
    ]
    needs = SphinxNeedsData(app.env).get_needs_view()
    if entry_point == "add_external_need":
        assert needs["R_EXT_PROTOCOL"]["is_external"] is True
    elif entry_point == "ingest_need_record":
        assert needs["R_REC_PROTOCOL"]["docname"] == "index"


@pytest.mark.parametrize(
    "entry_point",
    ["generate_need", "add_external_need", "ingest_need_record", "create_need"],
)
def test_a_need_item_source_is_not_deprecated(source_argument, entry_point):
    """A ``NeedItemSource`` gives no such warning, on any entry point."""
    rows, _, _ = source_argument
    outcome, warned = rows[entry_point, "class"]
    assert outcome[0] == "returned"
    assert _deprecations(warned) == []


@pytest.mark.parametrize("entry_point", ["generate_need", "add_external_need"])
def test_no_source_is_not_deprecated(source_argument, entry_point):
    """``None``, the default ``need_source`` of the two that have one, gives no such
    warning: the function builds its own ``NeedItemSource``."""
    rows, _, _ = source_argument
    outcome, warned = rows[entry_point, "none"]
    assert outcome[0] == "returned"
    assert _deprecations(warned) == []


def test_add_need_gives_no_second_warning(source_argument):
    """``add_need`` is deprecated whole: a protocol-only source given to it is its own
    deprecation alone, and the need is created."""
    rows, _, app = source_argument
    outcome, warned = rows["add_need", "protocol"]
    assert outcome == ("returned", "list")
    assert [w[1].split(":")[0] for w in warned] == [
        "add_need is deprecated and will be removed in sphinx-needs 10.0"
    ]
    assert "R_ADD_PROTOCOL" in SphinxNeedsData(app.env).get_needs_view()
