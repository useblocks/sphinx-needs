"""Every way a third-party extension gives a need its location through the API.

One directive, ``source-shapes``, creates a need for each call shape of ``add_need``,
``ingest_need_record``, ``add_external_need`` and ``create_need``, and for each of the
five ``NeedItemSource*`` names of sphinx-needs 9.1.0, constructed with the keywords
9.1.0 documents in their classes (with and without ``hops``); and it keeps what
``generate_need`` returns for its location keywords, on ``app.source_shapes_generated``.
It is written as an extension written against 9.1.0 is: the five names imported from
``sphinx_needs.need_item``.
"""

from sphinx.util.docutils import SphinxDirective

from sphinx_needs._need_source import NeedSourceHop, NeedSourcePhysical
from sphinx_needs.api import (
    add_external_need,
    add_need,
    create_need,
    generate_need,
    ingest_need_record,
)
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.need_item import (
    NeedItemSourceDirective,
    NeedItemSourceExternal,
    NeedItemSourceImport,
    NeedItemSourceService,
    NeedItemSourceUnknown,
)


class ProtocolSource:
    """A source of a third party's own, which obeys ``NeedItemSourceProtocol`` only."""

    def __init__(self, docname):
        self.docname = docname

    @property
    def dict_repr(self):
        return {
            "docname": self.docname,
            "lineno": 99,
            "lineno_content": None,
            "external_url": None,
            "is_import": False,
            "is_external": False,
        }


class SourceShapes(SphinxDirective):
    def run(self):
        app, state, d, ln = self.env.app, self.state, self.env.docname, self.lineno
        # a page hop with the directive's own, true line, and one without a line
        lined = NeedSourceHop(
            kind="page",
            document=d,
            physical=NeedSourcePhysical(
                root="srcdir", path="index.rst", start_line=ln, end_line=ln
            ),
            language=".rst",
        )
        page = NeedSourceHop(kind="page", document=d)
        generated = NeedSourceHop(kind="generated")
        imported = NeedSourceHop(kind="file", language=".json")

        def external(url):
            return NeedSourceHop(kind="external", physical=NeedSourcePhysical(url=url))

        out = []

        def add(need_id, *args, **kwargs):
            out.extend(add_need(app, state, *args, id=need_id, **kwargs))

        def add_external(need_id, **kwargs):
            add_need(app, None, need_type="req", title=need_id, id=need_id, **kwargs)

        # add_need, its location as its own arguments
        add("SHAPE_ADD_POSITIONAL", d, ln, "req", "positional", status="open")
        add(
            "SHAPE_ADD_KEYWORDS",
            docname=d,
            lineno=ln,
            need_type="req",
            title="keywords",
            lineno_content=ln + 1,
        )
        add("SHAPE_ADD_NO_LOCATION", None, None, "req", "no location")
        add("SHAPE_ADD_DOCNAME_ONLY", d, None, "req", "docname only")
        add("SHAPE_ADD_LINENO_ONLY", None, ln, "req", "lineno only")
        add("SHAPE_ADD_IS_IMPORT", d, ln, "req", "is_import", is_import=True)
        add(
            "SHAPE_ADD_URL_NOT_EXTERNAL",
            d,
            ln,
            "req",
            "an external_url without is_external",
            external_url="http://example.org/a.html",
        )
        add_external(
            "SHAPE_ADD_IS_EXTERNAL",
            is_external=True,
            external_url="http://example.org/b.html",
        )
        add_external("SHAPE_ADD_IS_EXTERNAL_NO_URL", is_external=True)
        add_external(
            "SHAPE_ADD_IS_EXTERNAL_PLACED",
            docname=d,
            lineno=ln,
            is_external=True,
            external_url="http://example.org/c.html",
        )
        # add_need, its location as a source of each of the five names
        sources = {
            "SHAPE_ADD_SRC_UNKNOWN": NeedItemSourceUnknown(docname=d, lineno=ln),
            "SHAPE_ADD_SRC_UNKNOWN_FULL": NeedItemSourceUnknown(
                docname=d, lineno=ln, lineno_content=ln + 1, is_import=True
            ),
            "SHAPE_ADD_SRC_UNKNOWN_HOPS": NeedItemSourceUnknown(
                hops=(lined,), lineno=ln
            ),
            "SHAPE_ADD_SRC_UNKNOWN_EMPTY": NeedItemSourceUnknown(),
            "SHAPE_ADD_SRC_DIRECTIVE": NeedItemSourceDirective(
                docname=d, lineno=ln, lineno_content=ln + 2, parser_lineno=ln
            ),
            "SHAPE_ADD_SRC_DIRECTIVE_HOPS": NeedItemSourceDirective(
                hops=(lined,), lineno_content=ln + 2
            ),
            "SHAPE_ADD_SRC_DIRECTIVE_UNLINED": NeedItemSourceDirective(
                hops=(page,), lineno=ln, lineno_content=ln + 2
            ),
            "SHAPE_ADD_SRC_SERVICE": NeedItemSourceService(docname=d, lineno=ln),
            "SHAPE_ADD_SRC_SERVICE_HOPS": NeedItemSourceService(
                lineno=ln, hops=(generated, page)
            ),
            "SHAPE_ADD_SRC_IMPORT": NeedItemSourceImport(
                docname=d, lineno=ln, path="x.json"
            ),
            "SHAPE_ADD_SRC_IMPORT_HOPS": NeedItemSourceImport(
                lineno=ln, path="y.json", hops=(imported, page)
            ),
            "SHAPE_ADD_SRC_PROTOCOL": ProtocolSource(d),
        }
        for need_id, source in sources.items():
            add(need_id, need_type="req", title=need_id, need_source=source)
        # the source wins over the location keywords
        add(
            "SHAPE_ADD_SRC_AND_KEYWORDS",
            "elsewhere",
            99,
            "req",
            "source and keywords",
            need_source=NeedItemSourceUnknown(docname=d, lineno=ln),
        )
        add_external(
            "SHAPE_ADD_SRC_EXTERNAL",
            need_source=NeedItemSourceExternal(url="http://example.org/d.html"),
        )
        add_external(
            "SHAPE_ADD_SRC_EXTERNAL_HOPS",
            need_source=NeedItemSourceExternal(
                hops=(external("http://example.org/e.html"),)
            ),
        )
        # ingest_need_record, as sphinx-codelinks 2.0 and needimport call it
        records = {
            "SHAPE_REC_UNKNOWN": NeedItemSourceUnknown(docname=d, lineno=ln),
            "SHAPE_REC_DIRECTIVE": NeedItemSourceDirective(
                docname=d, lineno=ln, lineno_content=ln + 1
            ),
            "SHAPE_REC_SERVICE": NeedItemSourceService(docname=d, lineno=ln),
            "SHAPE_REC_IMPORT": NeedItemSourceImport(
                docname=d, lineno=ln, path="z.json"
            ),
            "SHAPE_REC_IMPORT_HOPS": NeedItemSourceImport(
                lineno=ln, path="z.json", hops=(imported, page)
            ),
        }
        for need_id, source in records.items():
            nodes, _ = ingest_need_record(
                app,
                state,
                {"type": "req", "title": need_id, "id": need_id},
                need_source=source,
            )
            out.extend(nodes)
        # add_external_need
        add_external_need(
            app, "req", "url", id="SHAPE_EXT_URL", external_url="http://example.org/f"
        )
        add_external_need(app, "req", "no url", id="SHAPE_EXT_NO_URL")
        add_external_need(
            app,
            "req",
            "is_import",
            id="SHAPE_EXT_IS_IMPORT",
            external_url="http://example.org/g",
            is_import=True,
        )
        add_external_need(
            app,
            "req",
            "lineno_content",
            id="SHAPE_EXT_LINENO_CONTENT",
            external_url="http://example.org/h",
            lineno_content=7,
        )
        add_external_need(
            app,
            "req",
            "an external source",
            id="SHAPE_EXT_SRC_EXTERNAL",
            need_source=NeedItemSourceExternal(url="http://example.org/i"),
        )
        add_external_need(
            app,
            "req",
            "an unknown source",
            id="SHAPE_EXT_SRC_UNKNOWN",
            need_source=NeedItemSourceUnknown(
                is_external=True, external_url="http://example.org/j"
            ),
        )
        # create_need with one of the five names as its source
        _, nodes = create_need(
            app,
            state,
            NeedItemSourceUnknown(docname=d, lineno=ln),
            "req",
            "create_need",
            id="SHAPE_CREATE_UNKNOWN",
        )
        out.extend(nodes)
        create_need(
            app,
            None,
            NeedItemSourceExternal(url="http://example.org/k"),
            "req",
            "create_need, external",
            id="SHAPE_CREATE_EXTERNAL",
        )
        # generate_need: the need item it returns, never added
        config = NeedsSphinxConfig(app.config)
        schema = SphinxNeedsData(self.env).get_schema()
        generated_needs: dict[str, dict] = {
            "SHAPE_GEN_LOCATION": {
                "docname": d,
                "lineno": ln,
                "lineno_content": ln + 1,
            },
            "SHAPE_GEN_NO_LOCATION": {},
            "SHAPE_GEN_IS_EXTERNAL": {
                "is_external": True,
                "external_url": "http://example.org/l",
            },
            "SHAPE_GEN_IS_IMPORT": {"docname": d, "lineno": ln, "is_import": True},
            "SHAPE_GEN_SRC_SERVICE": {
                "need_source": NeedItemSourceService(docname=d, lineno=ln)
            },
        }
        app.source_shapes_generated = {
            need_id: generate_need(config, schema, "req", need_id, id=need_id, **kwargs)
            for need_id, kwargs in generated_needs.items()
        }
        return out


def setup(app):
    app.add_directive("source-shapes", SourceShapes)
    return {"parallel_read_safe": False, "parallel_write_safe": True}
