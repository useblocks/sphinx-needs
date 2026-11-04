"""The strict-first render of a need template never changes what it outputs.

A need template is rendered strictly first and, only when that fails, leniently again
(``sphinx_needs._need_templates._render``), so that an undefined value can be reported
(``needs.template_undefined``) while it keeps rendering empty. The output must stay
what the lenient render -- the only one before -- gives: a template that rendered
without a warning before must render the same now, and silently.

That holds if a strict render that SUCCEEDS gives the lenient render's output, which
these tests pin over the constructs that touch an undefined value without using it
(``is defined``, ``default``, a guarded branch, a loop over a defined list, ...) and over
every ``.need`` template this repository ships, rendered against a need's context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sphinx_needs._jinja import render_template_string

#: A need's context, as ``filter_context`` gives one: every field, unset ones ``None``.
CONTEXT: dict[str, Any] = {
    "id": "REQ_1",
    "type": "req",
    "type_name": "Requirement",
    "title": "A title",
    "content": "The body.",
    "status": None,
    "tags": ["a", "b"],
    "links": ["SPEC_1"],
    "links_back": [],
    "owner": None,
    "count": 3,
    "weight": 1.5,
    "flag": True,
    "docname": "index",
    "lineno": 4,
    "is_import": False,
    "sections": (),
}

CONSTRUCTS = [
    "{{ id }} {{ title }} {{ status }} {{ count }} {{ weight }} {{ flag }}",
    "{% if extra is defined %}{{ extra }}{% else %}none{% endif %}",
    "{% if extra is undefined %}undefined{% endif %}",
    "{{ extra | default('fallback') }} {{ owner | default('d', true) }}",
    "{% if status %}{{ status }}{% else %}no status{% endif %}",
    "{% if owner is none %}unowned{% endif %}",
    "{% for tag in tags %}[{{ tag }}]{% endfor %}{% for l in links_back %}x{% endfor %}",
    "{% for tag in tags %}{{ loop.index }}{% if not loop.last %},{% endif %}{% endfor %}",
    "{{ tags | join(', ') }} {{ links | length }} {{ sections | length }}",
    "{% set x = title | upper %}{{ x }}{% if x is defined %}!{% endif %}",
    "{{ content }}\n\n{{ content | indent(3) }}",
    "{% raw %}{{ not rendered }}{% endraw %}",
    "{% if extra is defined and extra %}{{ extra }}{% endif %}done",
    "{{ {'a': 1}.get('b', 'none') }} {{ CONTEXT is defined }}",
]


def _both(source: str) -> tuple[str | Exception, str | Exception]:
    results: list[str | Exception] = []
    for strict in (True, False):
        try:
            results.append(
                render_template_string(
                    source, dict(CONTEXT), autoescape=False, strict=strict
                )
            )
        except Exception as error:
            results.append(error)
    return results[0], results[1]


@pytest.mark.parametrize("source", CONSTRUCTS)
def test_a_strict_render_that_succeeds_is_the_lenient_one(source: str) -> None:
    strict, lenient = _both(source)
    assert not isinstance(strict, Exception), strict
    assert strict == lenient


def _shipped_templates() -> list[Path]:
    root = Path(__file__).parents[1]
    return sorted(
        [
            *(root / "docs" / "needs_templates").glob("*.need"),
            *(root / "tests" / "doc_test").rglob("*.need"),
        ]
    )


@pytest.mark.parametrize(
    "path",
    _shipped_templates(),
    ids=lambda path: f"{path.parent.parent.name}/{path.name}",
)
def test_every_shipped_template_renders_the_same(path: Path) -> None:
    """Where the strict render succeeds it is the lenient one; where it fails, the
    lenient one is what the need gets (and an undefined value is reported)."""
    strict, lenient = _both(path.read_text(encoding="utf-8"))
    if not isinstance(strict, Exception):
        assert strict == lenient


def test_the_shipped_templates_are_found() -> None:
    assert len(_shipped_templates()) >= 6


@pytest.mark.parametrize(
    "source",
    ["[{{ typo }}]", "{% if typo %}x{% endif %}", "{{ owner.name }}"],
)
def test_an_undefined_use_fails_strictly_and_renders_empty_leniently(
    source: str,
) -> None:
    strict, lenient = _both(source)
    assert isinstance(strict, Exception)
    assert getattr(strict, "kind", None) == "UndefinedError"
    assert isinstance(lenient, str)
    assert "typo" not in lenient


def test_an_attribute_of_an_undefined_name_fails_both_ways() -> None:
    """Even leniently, MiniJinja refuses an attribute of an undefined value (where one
    of ``None`` is undefined): such a template is a render error, not an undefined."""
    strict, lenient = _both("{{ typo.attr }}")
    assert isinstance(strict, Exception)
    assert isinstance(lenient, Exception)
