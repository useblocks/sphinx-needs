"""The relative links between the files of ``design/`` lead to files.

A contract that is replaced leaves a stub at its old path, because released documentation
links there, and the stub is nothing but its link to the successor. This holds every
``](<name>.md)`` link of a design file against the directory, the stub's among them.
"""

from __future__ import annotations

import re
from pathlib import Path

DESIGN = Path(__file__).resolve().parents[1] / "design"
#: A relative link to a Markdown file, with or without a fragment (no scheme, no space).
LINK = re.compile(r"\]\(([^)#:\s]+\.md)(?:#[^)]*)?\)")


def test_every_relative_link_of_a_design_file_resolves():
    links = [
        (path.name, target)
        for path in sorted(DESIGN.glob("*.md"))
        for target in LINK.findall(path.read_text(encoding="utf-8"))
    ]
    # the stub of the replaced draft is read, and its link is one of them
    assert ("v2a1-draft.md", "v2a2-draft.md") in links
    assert [
        f"{name} -> {target}"
        for name, target in links
        if not (DESIGN / target).is_file()
    ] == []
