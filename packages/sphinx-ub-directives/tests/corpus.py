"""The runner half both corpora share: a case is one project, built with the ``needs``
builder, and its products, needs and findings are read back the way the corpus headers
say (``design/directives-contract.md`` §1, §9)."""

from __future__ import annotations

import json
import re
import tomllib
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings
from sphinx_needs_testkit.conformance import check_values, inside, match_findings

FIXTURES = Path(__file__).parent / "fixtures"

#: The configuration the runner gives every case besides its ``ubproject.toml``.
CONF_PY = """\
extensions = ["sphinx_needs", "sphinx_design", "myst_parser", "sphinx_ub_directives"]
needs_from_toml = "ubproject.toml"
needs_build_json = True
# sphinx 7 does not append `[type.subtype]` to a warning by default; 8 and 9 do
show_warning_types = True
"""

#: The title the runner puts above every case's page.
TITLES = {"rst": "Case\n====\n\n", "md": "# Case\n\n"}

#: One finding record of this package: ``[attribution] message [ub_directives.code]``.
_FINDING = re.compile(
    r"(?:WARNING|ERROR): \[(?P<attribution>[^\]]+)\] (?P<message>.*) "
    r"\[ub_directives\.(?P<code>[a-z_]+)\]$",
    re.DOTALL,
)
_MENTION = re.compile(r"\[ub_directives\.([a-z_]+)\]")

#: Keys of a need record that are positions, dropped before two pages are compared.
_POSITION = re.compile(r"lineno|line_number|^content_offset$")

#: The keys a case may carry, and the keys of its expectation.
CASE_KEYS = frozenset(
    {
        "name",
        "why",
        "markup",
        "config",
        "source",
        "equivalent",
        "files",
        "python_only",
        "ubcode_only",
        "expect",
    }
)


def load(name: str) -> list[dict[str, Any]]:
    """The cases of corpus ``name``."""
    with (FIXTURES / name).open("rb") as handle:
        return tomllib.load(handle)["case"]


def project(case: Mapping[str, Any], page: str) -> list[tuple[Path, str]]:
    """The files of a case's project, with ``page`` as its one document."""
    markup = case.get("markup", "rst")
    return [
        (Path("conf.py"), CONF_PY),
        (Path("ubproject.toml"), case["config"]),
        (Path(f"index.{markup}"), TITLES[markup] + page),
        *((inside(rel), text) for rel, text in case.get("files", {}).items()),
    ]


@dataclass
class Built:
    """What one build of a case gives."""

    app: SphinxTestApp
    needs: dict[str, dict[str, Any]]
    findings: Counter[tuple[str, str | None, str | None]] = field(
        default_factory=Counter
    )
    unread: list[str] = field(default_factory=list)

    def products(self) -> tuple[str, dict[str, dict[str, Any]]]:
        """The page (the read doctree, the source directory written out) and the needs
        (positions dropped): what an ``equivalent`` page must give too."""
        doctree = self.app.env.get_doctree("index").pformat()
        doctree = doctree.replace(str(self.app.srcdir), "<srcdir>")
        needs = {
            need_id: {k: v for k, v in record.items() if not _POSITION.search(k)}
            for need_id, record in self.needs.items()
        }
        return doctree, needs


def build(
    make_app: Callable[..., SphinxTestApp],
    root: Path,
    files: Iterable[tuple[Path, str]],
    codes: frozenset[str],
) -> Built:
    """Write ``files`` under ``root`` and build them with the ``needs`` builder."""
    for relative, text in files:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    app = make_app("needs", srcdir=root, freshenv=True)
    app.build()
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    built = Built(app, data["versions"][data["current_version"]]["needs"])
    for record in build_warnings(app):
        match = _FINDING.search(record)
        if match is None:
            if any(code in codes for code in _MENTION.findall(record)):
                built.unread.append(record)
            continue
        if match["code"] not in codes:
            continue
        attribution = match["attribution"]
        if attribution.startswith("parse."):
            built.findings[(match["code"], attribution, None)] += 1
        else:
            built.findings[(match["code"], None, attribution)] += 1
    return built


def problems(built: Built, expect: Mapping[str, Any]) -> list[str]:
    """Everything about a build that its case's expectation does not say."""
    found = [
        f"a record naming a contract code is unreadable: {w!r}" for w in built.unread
    ]
    found += check_values(built.needs, expect)
    found += match_findings(
        built.findings, expect["findings"], keys=("code", "path", "directive")
    )
    return found


def complete(
    case: Mapping[str, Any], *, codes: frozenset[str], expect_keys: frozenset[str]
) -> None:
    """Assert one case says why, what it builds, and everything it expects."""
    name = case["name"]
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), name
    assert set(case) <= CASE_KEYS, (name, set(case) - CASE_KEYS)
    assert case["why"] and "config" in case and case["source"], name
    assert case.get("markup", "rst") in TITLES, name
    assert not (case.get("python_only") and case.get("ubcode_only")), name
    expect = case["expect"]
    assert "findings" in expect, name
    assert set(expect) <= expect_keys, (name, set(expect) - expect_keys)
    for finding in expect["findings"]:
        assert set(finding) <= {"code", "path", "directive"}, name
        assert finding["code"] in codes, (name, finding["code"])
        assert not ("path" in finding and "directive" in finding), name
