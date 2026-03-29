"""Benchmark resolve_links with many constrained links."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsMutable
from sphinx_needs.directives.need import resolve_links
from sphinx_needs.filter_common import _try_build_simple_predicate, filter_single_need
from sphinx_needs.need_item import NeedItem, NeedLink, NeedsContent
from sphinx_needs.needs_schema import FieldsSchema, LinkDisplayConfig, LinkSchema


def _make_needs_with_constrained_links(
    need_cnt: int,
    *,
    unique_conditions: bool = False,
) -> tuple[NeedsMutable, NeedsSphinxConfig, FieldsSchema]:
    """Create ``need_cnt`` needs, each with 2 conditional links to other needs.

    Every need links to the two "next" needs (wrapping around)
    with simple filter conditions like ``status == "open"``
    and ``type == "requirement"``.

    :param unique_conditions: If True, every link gets a unique condition string
        so the LRU cache in ``_try_build_simple_predicate`` never hits.
    """
    conditions = [
        'status == "open"',
        'type == "requirement"',
        '"safety" in tags',
        'status != "closed"',
        'type in ["requirement", "spec"]',
        'not status == "closed"',
        'type == "requirement" and status == "open"',
        'type == "spec" or type == "requirement"',
    ]

    core_base = {
        "type": "requirement",
        "type_name": "Req",
        "type_prefix": "REQ_",
        "type_color": "#000000",
        "type_style": "node",
        "status": "open",
        "tags": ["safety", "important"],
        "constraints": (),
        "title": "Test Requirement",
        "collapse": False,
        "arch": {},
        "style": None,
        "layout": None,
        "hide": False,
        "external_css": "external_link",
        "has_dead_links": False,
        "has_forbidden_dead_links": False,
        "sections": (),
        "signature": None,
    }
    content = NeedsContent(content="", doctype=".rst")

    need_ids = [f"REQ_{i:04d}" for i in range(need_cnt)]

    needs_dict: dict[str, NeedItem] = {}
    for i, nid in enumerate(need_ids):
        target1 = need_ids[(i + 1) % need_cnt]
        target2 = need_ids[(i + 2) % need_cnt]
        if unique_conditions:
            # Each link gets a unique condition so the LRU cache never hits
            cond1 = f'status == "v{2 * i}"'
            cond2 = f'status == "v{2 * i + 1}"'
        else:
            cond1 = conditions[i % len(conditions)]
            cond2 = conditions[(i + 1) % len(conditions)]

        need = NeedItem(
            core=core_base | {"id": nid},
            extras={},
            links={
                "links": [
                    NeedLink(id=target1, condition=cond1),
                    NeedLink(id=target2, condition=cond2),
                ],
            },
            source=None,
            content=content,
            parts=(),
        )
        needs_dict[nid] = need

    needs = NeedsMutable(needs_dict)

    config = Mock(spec=NeedsSphinxConfig)
    config.filter_data = {}
    config.report_dead_links = False

    schema = FieldsSchema()
    schema.add_link_field(
        LinkSchema(
            name="links",
            schema={"type": "array", "items": {"type": "string"}},
            display=LinkDisplayConfig(
                outgoing="links",
                incoming="linked by",
            ),
        )
    )

    return needs, config, schema


@pytest.mark.benchmark
@pytest.mark.parametrize("need_cnt", [100, 500, 1000])
def test_resolve_links_constrained(need_cnt: int, benchmark) -> None:
    """Benchmark resolve_links with many constrained links."""
    needs, config, schema = _make_needs_with_constrained_links(need_cnt)

    def run() -> None:
        # Reset backlinks before each run so resolve_links can be called again
        for need in needs.values():
            need.reset_backlinks()
        resolve_links(needs, config, schema)

    benchmark.pedantic(run, iterations=3, rounds=5)


@pytest.mark.benchmark
@pytest.mark.parametrize("need_cnt", [100, 500, 1000])
def test_resolve_links_unique_conditions(need_cnt: int, benchmark) -> None:
    """Benchmark resolve_links where every condition is unique (no LRU cache benefit)."""
    needs, config, schema = _make_needs_with_constrained_links(
        need_cnt, unique_conditions=True
    )

    def run() -> None:
        _try_build_simple_predicate.cache_clear()
        for need in needs.values():
            need.reset_backlinks()
        resolve_links(needs, config, schema)

    benchmark.pedantic(run, iterations=3, rounds=5)


@pytest.mark.benchmark
@pytest.mark.parametrize("need_cnt", [100, 500, 1000])
def test_filter_single_need_simple(need_cnt: int, benchmark) -> None:
    """Benchmark filter_single_need with simple_filter=True vs False."""
    needs, config, _ = _make_needs_with_constrained_links(need_cnt)
    need_list = list(needs.values())
    filter_string = 'status == "open"'

    def run() -> None:
        for need in need_list:
            filter_single_need(need, config, filter_string, simple_filter=True)

    benchmark.pedantic(run, iterations=3, rounds=5)
