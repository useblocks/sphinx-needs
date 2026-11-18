"""Only ``need_id.py`` knows the separator ``::``.

The grammar of a need id is written once, in ``ub_needs_exchange.need_id``; a second
module that splits or joins at ``::`` by itself is a second grammar, which drifts from the
first and from the corpus. This fence walks every module of the package with ``ast`` and
fails on a string constant EQUAL to ``"::"`` (or a ``bytes`` constant equal to ``b"::"``)
anywhere but ``need_id.py``: the literal any such code starts from (``x.split("::")``,
``"::".join(...)``, ``x.rpartition("::")``). An f-string whose only literal part is ``::``
(``f"{ns}::{local}"``) IS seen: that part is a constant ``"::"`` of its own.

What it cannot see: a separator built at run time (``":" * 2``, ``":" + ":"``,
``chr(58) * 2``); one inside a longer literal (an f-string such as ``f"ns::{local}"``, a
``"%s::%s"`` format, a regex such as ``r"(.*)::(.*)"``) or spelled as a regex quantifier
(``":{2}"``); and one taken from :data:`~ub_needs_exchange.SEPARATOR` itself, which is the
way to do it. Nor does it see a module that splits an id through ``need_id`` where it
should not: ``test_reader.py::test_an_id_holding_the_separator_is_read_as_written`` pins
that the reader does not.
"""

from __future__ import annotations

import ast
from pathlib import Path

import ub_needs_exchange

#: The one module allowed to spell the separator.
OWNER = "need_id.py"
LITERALS: tuple[str | bytes, ...] = ("::", b"::")


def _spellings(source: str) -> list[int]:
    """The line of every constant in *source* equal to ``"::"`` or ``b"::"``."""
    return sorted(
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str | bytes)
        and node.value in LITERALS
    )


def _modules() -> list[Path]:
    root = Path(ub_needs_exchange.__file__).parent
    modules = sorted(root.rglob("*.py"))
    assert modules, f"no module found under {root}"
    return modules


def test_the_fence_sees_a_spelling() -> None:
    """The positive control, through the fence's own detector: it sees ``"::"`` and
    ``b"::"`` and not ``":"`` in a small source, and the walk reaches ``need_id.py``
    and finds the separator there -- a detector or a walk that saw nothing would pass
    the test below."""
    assert _spellings('x.split("::")\ny.split(b"::")\nz.split(":")\n') == [1, 2]
    owner = [module for module in _modules() if module.name == OWNER]
    assert len(owner) == 1
    assert _spellings(owner[0].read_text(encoding="utf-8")) != []


def test_no_other_module_spells_the_separator() -> None:
    found = [
        f"{module.name}:{line}"
        for module in _modules()
        if module.name != OWNER
        for line in _spellings(module.read_text(encoding="utf-8"))
    ]
    assert found == [], (
        "the separator '::' is spelled outside need_id.py; split, join or test it "
        "through ub_needs_exchange.need_id instead"
    )
