"""`propagate_floors.py`: the rewrite, `--check`, and what must survive it.

The script exists because a floor that has to be moved by hand is a floor that rots, and
uv can never notice -- it resolves the workspace copy whatever the specifier says, and the
specifier is not in `uv.lock` at all. So the thing being tested is not only "the number
changed" but "nothing else did": a release pull request whose manifest diff is one line per
dependant is reviewable, and one that reflows comments and markers is not.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sn_tools import propagate_floors

pytestmark = pytest.mark.filterwarnings("error")


def run(root: Path, *args: str) -> int:
    return propagate_floors.main([*args, "--root", str(root)])


def test_rewrites_every_dependant(workspace, capsys) -> None:
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=1.0.0,<2"]},
            "acme-other": {"version": "0.3.0", "dependencies": ["acme-core>=1.0.0,<2"]},
        }
    )
    assert run(root, "acme-core") == 0
    out = capsys.readouterr().out
    assert "rewrote 1 specifier(s) in packages/acme-ext/pyproject.toml" in out
    assert "-> acme-core>=2.0.0,<3" in out
    assert "now run `uv lock` and commit both" in out
    for member in ("acme-ext", "acme-other"):
        text = (root / "packages" / member / "pyproject.toml").read_text()
        assert '"acme-core>=2.0.0,<3"' in text
    # the member itself is never rewritten
    assert (
        'version = "2.0.0"' in (root / "packages/acme-core/pyproject.toml").read_text()
    )


def test_check_reports_without_writing(workspace, capsys) -> None:
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=1.0.0,<2"]},
        }
    )
    manifest = root / "packages/acme-ext/pyproject.toml"
    before = manifest.read_text()
    assert run(root, "acme-core", "--check") == 1
    assert "would rewrite 1 specifier(s)" in capsys.readouterr().out
    assert manifest.read_text() == before
    # ... and exits 0 once there is nothing to do
    assert run(root, "acme-core") == 0
    capsys.readouterr()
    assert run(root, "acme-core", "--check") == 0
    assert (
        "every one of the 1 member(s) that declare acme-core already floors on "
        "acme-core>=2.0.0,<3" in capsys.readouterr().out
    )


def test_nothing_depends_on_it(workspace, capsys) -> None:
    root = workspace({"acme-core": {"version": "2.0.0"}})
    assert run(root, "acme-core") == 0
    assert (
        "no member declares acme-core; nothing to propagate" in capsys.readouterr().out
    )


def test_an_explicit_version_overrides_the_tree(workspace) -> None:
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=1.0.0,<2"]},
        }
    )
    assert run(root, "acme-core", "--version", "3.4.5") == 0
    assert (
        '"acme-core>=3.4.5,<4"'
        in (root / "packages/acme-ext/pyproject.toml").read_text()
    )


def test_a_name_that_is_not_a_member(workspace, capsys) -> None:
    root = workspace({"acme-core": {"version": "2.0.0"}})
    assert run(root, "acme-nope") == 2
    assert "is not a member of this workspace" in capsys.readouterr().out


def test_extras_and_markers_survive(workspace) -> None:
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-ext": {
                "version": "0.1.0",
                "dependencies": ["acme-core[cli]>=1.0.0,<2 ; python_version >= '3.12'"],
                "optional_dependencies": {"all": ["acme-core>=1.0.0,<2"]},
            },
        }
    )
    assert run(root, "acme-core") == 0
    text = (root / "packages/acme-ext/pyproject.toml").read_text()
    assert '"acme-core[cli]>=2.0.0,<3 ; python_version >= \\"3.12\\""' in text
    assert '"acme-core>=2.0.0,<3"' in text


def test_extras_are_counted_too(workspace, capsys) -> None:
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-ext": {
                "version": "0.1.0",
                "dependencies": ["acme-core>=1.0.0,<2"],
                "optional_dependencies": {"all": ["acme-core>=1.0.0,<2"]},
            },
        }
    )
    assert run(root, "acme-core") == 0
    assert "rewrote 2 specifier(s)" in capsys.readouterr().out


def test_comments_and_formatting_are_preserved(workspace) -> None:
    """tomlkit, not text munging: the release diff has to be one line."""
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=1.0.0,<2"]},
        }
    )
    manifest = root / "packages/acme-ext/pyproject.toml"
    manifest.write_text(
        "# a header comment\n"
        "[project]\n"
        'name = "acme-ext"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.11,<4"\n'
        "dependencies = [\n"
        '  "acme-core>=1.0.0,<2", # why this floor\n'
        '  "requests~=2.32",\n'
        "]\n",
        encoding="utf-8",
    )
    assert run(root, "acme-core") == 0
    assert manifest.read_text() == (
        "# a header comment\n"
        "[project]\n"
        'name = "acme-ext"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.11,<4"\n'
        "dependencies = [\n"
        '  "acme-core>=2.0.0,<3", # why this floor\n'
        '  "requests~=2.32",\n'
        "]\n"
    )
