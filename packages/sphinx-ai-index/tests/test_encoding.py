"""Every text read and write in this suite names its encoding.

Without ``encoding=``, ``Path.read_text``, ``Path.write_text`` and ``open`` use the locale's
preferred encoding -- cp1252 on a default Windows install -- so a payload outside it fails to
write or decodes wrongly, while the extension writes ``ai_docs_index.json`` as UTF-8 (#2032).
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS_DIR = Path(__file__).parent


def _is_binary_mode(call: ast.Call) -> bool:
    mode: ast.expr | None = call.args[1] if len(call.args) > 1 else None
    for keyword in call.keywords:
        if keyword.arg == "mode":
            mode = keyword.value
    return (
        isinstance(mode, ast.Constant)
        and isinstance(mode.value, str)
        and "b" in mode.value
    )


def _needs_encoding(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr in {"read_text", "write_text"}
    if isinstance(func, ast.Name) and func.id == "open":
        return not _is_binary_mode(call)
    return False


def _violations() -> list[str]:
    found: list[tuple[str, int]] = []
    for path in sorted(TESTS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and _needs_encoding(node)
                and not any(keyword.arg == "encoding" for keyword in node.keywords)
            ):
                found.append((path.name, node.lineno))
    return [f"{name}:{line}" for name, line in sorted(found)]


def test_every_text_read_and_write_names_its_encoding() -> None:
    """A static walk over every ``tests/*.py`` module of this package (not ``tests/roots/``).

    It flags a call to an attribute named ``read_text`` or ``write_text``, or to a bare
    ``open`` whose mode is not a binary literal, that passes no ``encoding`` keyword
    (``read_bytes`` / ``write_bytes`` take none and are not checked). It is a syntactic check,
    so it cannot see: ``open`` called through an alias or as ``io.open`` / ``Path.open`` /
    ``codecs.open``; an encoding passed positionally or inside ``**kwargs`` (both are reported
    as missing, so pass it by keyword); a mode held in a variable (treated as text); and text
    I/O done by a helper outside these modules on the test's behalf.
    """
    violations = _violations()
    assert not violations, "text I/O without encoding=: " + ", ".join(violations)
