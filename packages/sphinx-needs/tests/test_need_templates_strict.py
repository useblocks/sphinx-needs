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


COUNTER_CONF = """\
import itertools

extensions = ["sphinx_needs"]
needs_build_json = True

_counter = itertools.count(1)
CALLS = []


def next_number(tag=""):
    CALLS.append(tag)
    return next(_counter)


def fails(tag=""):
    CALLS.append("fails:" + tag)
    raise ValueError("no")


needs_render_context = {"next_number": next_number, "fails": fails}
"""

COUNTER_INDEX = """\
Counter
=======

.. req:: A
   :id: REQ_1
   :template: num

.. req:: B
   :id: REQ_2
   :template: numtypo

.. req:: C
   :id: REQ_3
   :template: num

.. req:: D
   :id: REQ_4
   :template: failing
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), COUNTER_CONF),
                (Path("index.rst"), COUNTER_INDEX),
                (Path("needs_templates", "num.need"), "No. {{ next_number(id) }}\n"),
                (Path("needs_templates", "failing.need"), "{{ fails(id) }}\n"),
                (
                    Path("needs_templates", "numtypo.need"),
                    "No. {{ next_number(id) }} {{ titel }} "
                    "{{ next_number(id + 'b') }}\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_a_render_context_function_is_called_once_per_call(test_app: Any) -> None:
    """A template using an undefined value is rendered twice (strictly, then
    leniently), but a render-context function in it is called once per call the
    template makes, as with one render: the lenient render replays the strict one's
    results up to where it failed, then calls through. A counter numbers the needs as
    it always did, the typo's need included; a function that raises is called once
    too, and its template is a render error."""
    import json

    app = test_app
    app.build()
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = data["versions"][data["current_version"]]["needs"]
    assert needs["REQ_1"]["content"] == "No. 1"
    assert needs["REQ_2"]["content"] == "No. 2  3"
    assert needs["REQ_3"]["content"] == "No. 4"
    assert needs["REQ_4"]["content"] == ""
    assert app.config.needs_render_context["next_number"].__globals__["CALLS"] == [
        "REQ_1",
        "REQ_2",
        "REQ_2b",
        "REQ_3",
        "fails:REQ_4",
    ]


def _linked(n: int) -> Any:
    """A render-context helper returning a one-shot iterator (a generator)."""
    return (f"L{i}" for i in range(n))


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("{% for x in linked(3) %}{{ x }},{% endfor %} {{ typo }}", "L0,L1,L2, "),
        ("{% set g = linked(2) %}{{ g|list|join(',') }}{{ typo }}", "L0,L1"),
        ("{% for x in ite(2) %}{{ x }},{% endfor %} {{ typo }}", "I0,I1, "),
    ],
)
def test_an_iterator_a_context_function_returns_is_replayed_whole(
    monkeypatch: pytest.MonkeyPatch, source: str, expected: str
) -> None:
    """The strict render consumes a one-shot iterator a render-context function returns
    before it fails at the undefined name; the lenient render replays the call, and gets
    the same items, not the exhausted iterator: the output is a single render's."""
    from sphinx_needs import _need_templates

    found: list[str] = []
    monkeypatch.setattr(
        _need_templates,
        "_warn",
        lambda message, subtype, location: found.append(subtype),
    )
    context = {"linked": _linked, "ite": lambda n: iter([f"I{i}" for i in range(n)])}
    rendered = _need_templates._render(
        source, context, option="template", name="t", need_id="N", location=None
    )
    assert rendered == expected
    assert found == ["template_undefined"]
