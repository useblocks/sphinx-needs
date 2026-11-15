"""Only ``need_id.py`` knows the separator ``::``.

The grammar of a need id is written once, in ``ub_needs_exchange.need_id``; a second
module that splits or joins at ``::`` by itself is a second grammar, which drifts from the
first and from the corpus. This fence walks every module of the package with ``ast`` and
fails on a string constant EQUAL to ``"::"`` (or a ``bytes`` constant equal to ``b"::"``)
anywhere but ``need_id.py``: the literal any such code starts from (``x.split("::")``,
``"::".join(...)``, ``x.rpartition("::")``).

What it cannot see: a separator built at run time (``":" * 2``, ``":" + ":"``, a
``chr(58)``), one inside a longer string (a regex such as ``r"(.*)::(.*)"``, an f-string
``f"{ns}::{local}"``, whose literal parts are not ``"::"`` alone), and one taken from
:data:`~ub_needs_exchange.SEPARATOR` itself, which is the way to do it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import ub_needs_exchange

#: The one module allowed to spell the separator.
OWNER = "need_id.py"
LITERALS: tuple[str | bytes, ...] = ("::", b"::")


def _modules() -> list[Path]:
    root = Path(ub_needs_exchange.__file__).parent
    modules = sorted(root.rglob("*.py"))
    assert modules, f"no module found under {root}"
    return modules


def test_the_fence_sees_the_owner() -> None:
    """The positive control: the walk reaches ``need_id.py``, and finds the separator
    there -- a walk that saw nothing would pass the test below."""
    owner = [module for module in _modules() if module.name == OWNER]
    assert len(owner) == 1
    tree = ast.parse(owner[0].read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.Constant) and node.value in LITERALS
        for node in ast.walk(tree)
    )


def test_no_other_module_spells_the_separator() -> None:
    found: list[str] = []
    for module in _modules():
        if module.name == OWNER:
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"))
        found.extend(
            f"{module.name}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str | bytes)
            and node.value in LITERALS
        )
    assert found == [], (
        "the separator '::' is spelled outside need_id.py; split, join or test it "
        "through ub_needs_exchange.need_id instead"
    )
