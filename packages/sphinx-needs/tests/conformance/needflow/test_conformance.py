"""The sphinx-needs half of the shared needflow conformance corpus.

The corpus exists because the portable needflow vocabulary is implemented twice -- here
and in ubCode -- and nothing else would make the two drift visibly.  Its cases are
language neutral: each states some needs, some portable configuration and some directive
options, and the diagram source every engine is expected to emit for them.  ubCode reads
the same files and checks its mermaid emitter against the same expectations.

The format is specified in ``README.md`` beside this module, which ships verbatim in both
repositories.  This module implements the harness contract of that spec; anything it
asserts beyond the spec would be drift of its own, so the rules it enforces are exactly
the ones written down there:

- a case may not use an unknown top-level key, or an unknown portable option or
  configuration key -- the corpus is a closed vocabulary, and a typo that is silently
  ignored here is a case that quietly tests nothing;
- a ``degradations`` entry may not claim tier 1, which is silent by definition;
- every case file's checksum must match ``manifest.json``, so that editing a case without
  restamping the manifest is a red test rather than invisible divergence between the two
  copies.

**The corpus format is wider than this repository's surface, deliberately.** The format
is the shared one; what Sphinx-Needs can express today is a subset of it, and the subset
grows one slice at a time. The two are kept apart on purpose: the ``SPEC_*`` names below
are the format's closed vocabulary (a key outside them is a typo, wherever it appears),
and the mapping tables beside them are what *this* repository can currently build a
project from. A case using a key the format defines but this repository has no surface
for is refused with a message saying so -- never silently built as if the key were not
there -- and the slice that implements the option adds its row to the mapping table along
with the case that needs it.

Regenerating expectations: set ``UBC_UPDATE_CORPUS=1`` to write the emitted sources back
into the case files, then **read the diff** -- an expectation accepted without reading is
a snapshot, and a snapshot cannot tell you that the thing it recorded is wrong.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from sphinx.util.console import strip_colors

CORPUS_ROOT = Path(__file__).parent
CASES_DIR = CORPUS_ROOT / "cases"
MANIFEST = CORPUS_ROOT / "manifest.json"

#: The engines this repository draws with.  ``mermaid`` expectations belong to ubCode and
#: are absent from this copy until that slice adds them and both copies re-sync.
ENGINES = ("plantuml", "graphviz")

#: Every engine the corpus format knows.  A case may carry expectations for an engine
#: this repository does not draw with; they are validated here and asserted there.
SPEC_ENGINES = (*ENGINES, "mermaid")

# --- the corpus format's closed vocabulary -------------------------------------------
#
# These are the format's, not this repository's: they say what a case file may contain,
# in either repository, and a key outside them is a typo.

#: Top level keys a case file may use (spec, "Case file schema").
CASE_KEYS = frozenset(
    (
        "id",
        "title",
        "purpose",
        "needs",
        "types",
        "links",
        "legends",
        "config",
        "options",
        "expect",
    )
)

#: Keys one engine's entry under ``expect`` may use.
EXPECT_KEYS = frozenset(("source", "legend", "degradations", "skip"))

#: Portable configuration keys (spec, "config").
SPEC_CONFIG_KEYS = frozenset(
    ("direction", "show_legend", "link_labels", "styles", "engine_config")
)

#: Portable directive options (spec, "options").  The selection options are neutral
#: already, and are part of the vocabulary so that a case can filter what it draws.
SPEC_OPTION_KEYS = frozenset(
    (
        "direction",
        "show_legend",
        "link_labels",
        "styles",
        "engine_config",
        "filter",
        "types",
        "tags",
        "status",
        "link_types",
        "root_id",
        "root_direction",
        "root_depth",
        "max_items",
    )
)

#: Keys a case's ``needs`` entries may set.
NEED_KEYS = frozenset(("id", "type", "title", "status", "tags", "links"))

#: Keys a case's ``types`` entries may set.
SPEC_TYPE_KEYS = frozenset(("directive", "title", "prefix", "color", "shape"))

#: Keys a case's ``links`` entries may set.
SPEC_LINK_KEYS = frozenset(("option", "incoming", "outgoing", "line", "arrow", "color"))

#: The sections ``expect.<engine>.legend`` may name.
LEGEND_SECTIONS = frozenset(("types", "links"))

#: The neutral degradation ids of the spec's registry.  This is the format's list, so it
#: ships whole; which of them *this* repository can observe is :data:`DEGRADATIONS`.
DEGRADATION_IDS = frozenset(
    (
        "direction-vertical-unsupported",
        "direction-horizontal-unsupported",
        "shape-unmapped",
        "arrow-unsupported",
        "style-class-unknown",
        "option-conflict-direction",
    )
)

# --- what this repository can express today ------------------------------------------
#
# The seam. Each table holds only what a shipped case uses; a slice that adds an option
# adds its row here together with the case that needs it, and a case naming anything else
# is refused rather than quietly built without it.

#: Portable configuration keys, mapped to the ``conf.py`` name that carries the same
#: intent.  The neutral names are the corpus's, not this repository's user-facing
#: spelling: ``link_labels`` is what the corpus calls the label selector that
#: Sphinx-Needs spells ``needs_flow_show_links``, the flag it widened.
#:
#: ``styles`` is absent -- there is no ``needs_flow_styles`` here yet.
CONFIG_KEYS: dict[str, str] = {
    "direction": "needs_flow_direction",
    "show_legend": "needs_flow_show_legend",
    "link_labels": "needs_flow_show_links",
}

#: The portable ``engine_config`` configuration, mapped per engine.
#:
#: It is not a row of :data:`CONFIG_KEYS` because it is *split* rather than renamed:
#: Sphinx-Needs keeps the two engines' registries in two separate configuration values
#: instead of under one engine-keyed roof, so a case naming this key only ever reaches
#: the registry of the engine being drawn with.
ENGINE_CONFIG_KEYS = {
    "plantuml": "needs_flow_configs",
    "graphviz": "needs_graphviz_styles",
}

#: Portable directive options, mapped to the Sphinx-Needs option of the same intent.
#: The neutral names are the corpus's, not either repository's user-facing spelling:
#: ``link_labels`` is what the corpus calls the label selector that both tools spell
#: ``:show_link_names:``, and ``engine_config`` the escape hatch spelled ``:config:``.
OPTION_NAMES = {
    "direction": "direction",
    "show_legend": "show_legend",
    "link_labels": "show_link_names",
    "engine_config": "config",
}

#: Written after the option name to mean "emit it as a bare flag, with no value".
_BARE: str | None = None

#: The portable *values* each mapped option accepts here, and how to write each one.
#:
#: A closed enumeration is listed exhaustively, so that a value this repository cannot
#: express is refused rather than written through and silently ignored.
OPTION_VALUES: dict[str, dict[str, str | None]] = {
    "direction": {
        "down": "down",
        "up": "up",
        "right": "right",
        "left": "left",
    },
    "link_labels": {
        "none": "none",
        # the bare flag is what this value has always meant, and the merged
        # `legend-engine-default`/`edge-empty-label` cases pin those bytes, so it is
        # deliberately still written bare rather than spelled out
        "outgoing": _BARE,
        "incoming": "incoming",
        "type": "type",
    },
}

#: Mapped options whose value is a *name* rather than a member of an enumeration -- a
#: legend key, an engine config name -- and so is written through verbatim.
#: An empty value stays special: it means the option was written bare.
OPTION_FREE_VALUES = frozenset(("show_legend", "engine_config"))

#: Keys of a ``types`` entry this repository can put into ``needs_types``.  ``shape`` is
#: absent: the portable shape enum has no counterpart here yet, only the legacy plantuml
#: ``style`` keyword it is meant to replace.
TYPE_KEYS = frozenset(("directive", "title", "prefix", "color"))

#: Keys of a ``links`` entry this repository can put into ``needs_links``.  ``line`` and
#: ``arrow`` have no counterpart yet; ``color`` has one in the configuration but no
#: emitter reads it, so mapping it would let a case claim a colour that never renders.
LINK_KEYS = frozenset(("option", "incoming", "outgoing"))

#: The degradations of the registry this repository can observe, each mapped to its
#: tier, to the Sphinx-Needs warning subtype it is reported under, and to a pattern
#: matching the message.
#:
#: The subtype is part of the mapping rather than assumed, because a warning that says
#: the right thing under the wrong subtype cannot be suppressed by the documented
#: ``suppress_warnings`` entry -- so the pair is the contract, not the message alone.
#: Several ids here share one subtype, which is why the message is matched too.
#: ubCode maps the same ids onto its own ``needs.option_*`` diagnostic codes.
#:
#: The rest of the registry degrades options this repository does not have yet -- no
#: portable shape enum to leave unmapped, no style classes to miss -- so a warning
#: matching none of these is an unexpected one, which is the fence the shipped cases
#: assert.
DEGRADATIONS: dict[str, tuple[int, str, re.Pattern[str]]] = {
    "direction-vertical-unsupported": (
        2,
        "needs.needflow",
        re.compile(r"cannot draw 'up'"),
    ),
    "direction-horizontal-unsupported": (
        2,
        "needs.needflow",
        re.compile(r"cannot draw 'left'"),
    ),
    "option-conflict-direction": (
        3,
        "needs.needflow",
        re.compile(r"disagrees with the direction"),
    ),
}

#: Warnings that are not degradations and must not be counted as unexpected ones.
#: Nothing in the corpus may use a deprecated spelling, so a deprecation notice here
#: would itself be a bug -- these are the notices a *project* emits regardless.
_IGNORED_WARNINGS = re.compile(r"WARNING: (?:document isn't included|.*toctree)")

#: The class the corpus reserves for out-of-diagram legend markup, and so what
#: :func:`_legend_rows` reads.  Both engines here render one for a legend whose
#: ``placement`` is ``external``, and draw their own inside the diagram otherwise --
#: where ``source`` asserts it byte-exactly and this reader correctly finds nothing.
_LEGEND_CLASS = "needflow_legend"


def _sha256(path: Path) -> str:
    """Return the lowercase hex sha256 of a file's content.

    Line endings are normalised to LF before hashing, because the manifest stamps
    *content*, not transport encoding. Git rewrites LF to CRLF on checkout under
    ``text=auto``, so a corpus checked out on Windows holds different bytes for the same
    content -- and a checksum over raw bytes would make the same corpus fail there while
    passing on Linux, in either repository. The repositories additionally pin the corpus
    to LF in ``.gitattributes``; this normalisation is what keeps the contract true when
    that pin is missing, or when a file arrives by some other route.

    :param path: The file to hash.
    :return: The lowercase hex digest of its normalised content.
    """
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def _build_manifest(corpus_version: int) -> dict[str, Any]:
    """Compute what ``manifest.json`` should hold for the corpus on disk.

    Verification and regeneration both go through this, so the checksums a run *asserts*
    and the checksums a run *writes* can never be computed two different ways.

    :param corpus_version: The version to stamp.
    :return: The manifest contents.
    """
    return {
        "corpus_version": corpus_version,
        "readme": _sha256(CORPUS_ROOT / "README.md"),
        "cases": {path.name: _sha256(path) for path in _case_files()},
    }


def _load_manifest() -> dict[str, Any]:
    """Read ``manifest.json``."""
    return json.loads(MANIFEST.read_text("utf8"))  # type: ignore[no-any-return]


def _case_files() -> list[Path]:
    """Every case file, in a stable order."""
    return sorted(CASES_DIR.glob("*.yaml"))


def _check_keys(actual: Any, allowed: frozenset[str] | set[str], what: str) -> None:
    """Reject any key outside the closed vocabulary.

    :param actual: The mapping to check.
    :param allowed: The keys the spec permits.
    :param what: What is being checked, for the message.
    :raises AssertionError: If an unknown key is present.
    """
    assert isinstance(actual, dict), f"{what} must be a mapping, got {type(actual)}"
    if unknown := set(actual) - set(allowed):
        raise AssertionError(
            f"{what} uses unknown key(s) {sorted(unknown)}; allowed: {sorted(allowed)}"
        )


def _require_mapped(
    keys: Any, mapped: frozenset[str] | set[str] | dict[str, Any], what: str
) -> None:
    """Reject a key the corpus format defines but this repository cannot express.

    The alternative is worse than a failure: a portable key with no counterpart here
    would be dropped while building the project, and the case would then assert the
    output of a diagram that was never asked for the thing the case is about.

    :param keys: The keys used, e.g. a case's ``options`` mapping.
    :param mapped: The keys this repository maps.
    :param what: What is being checked, for the message.
    :raises AssertionError: If a key of the format has no mapping here.
    """
    if missing := sorted(set(keys) - set(mapped)):
        raise AssertionError(
            f"{what}: the corpus format defines {missing}, but this repository has no "
            "surface for it yet; the slice that implements it maps the key here"
        )


def validate_case(case: dict[str, Any], path: Path) -> None:
    """Check a case against the spec's schema rules.

    Only the *format* is checked here, never what this repository can express: a case
    that is well formed but names an option no slice has implemented yet is a valid
    corpus case, and it is refused when a project is built from it (see
    :func:`_require_mapped`) rather than when it is read.  The distinction matters
    because the file is shared: a case whose engines are all skipped here is never built
    here, and must not be rejected for naming vocabulary only the other repository has.

    :param case: The parsed case file.
    :param path: Where it came from, for messages.
    :raises AssertionError: If the case violates the spec.
    """
    _check_keys(case, CASE_KEYS, f"{path.name}")
    assert case.get("id") == path.stem, (
        f"{path.name}: 'id' must equal the filename stem, got {case.get('id')!r}"
    )
    for required in ("title", "purpose", "needs"):
        assert case.get(required), f"{path.name}: '{required}' is required"
    assert "expect" in case, f"{path.name}: 'expect' is required"
    if not os.environ.get("UBC_UPDATE_CORPUS"):
        assert case["expect"], (
            f"{path.name}: 'expect' is empty, so the case asserts nothing; "
            "regenerate it with UBC_UPDATE_CORPUS=1 and review the result"
        )

    for need in case["needs"]:
        _check_keys(need, NEED_KEYS, f"{path.name}: needs entry")
    for type_ in case.get("types", []):
        _check_keys(type_, SPEC_TYPE_KEYS, f"{path.name}: types entry")
    for link in case.get("links", []):
        _check_keys(link, SPEC_LINK_KEYS, f"{path.name}: links entry")
    _check_keys(case.get("config", {}), SPEC_CONFIG_KEYS, f"{path.name}: config")
    _check_keys(case.get("options", {}), SPEC_OPTION_KEYS, f"{path.name}: options")

    for engine, expected in case["expect"].items():
        assert engine in SPEC_ENGINES, (
            f"{path.name}: unknown engine {engine!r} in 'expect'"
        )
        _check_keys(expected, EXPECT_KEYS, f"{path.name}: expect.{engine}")
        if "skip" in expected:
            continue
        assert expected.get("source") is not None, (
            f"{path.name}: expect.{engine} has no 'source'; give one, or 'skip' the "
            "engine with a reason"
        )
        _validate_legend_expectation(expected.get("legend"), engine, path)
        for entry in expected.get("degradations", []):
            assert entry.get("id") in DEGRADATION_IDS, (
                f"{path.name}: unknown degradation id {entry.get('id')!r}"
            )
            assert entry.get("tier") != 1, (
                f"{path.name}: tier 1 is silent by definition, "
                f"so {entry['id']!r} cannot be listed as one"
            )


def _validate_legend_expectation(legend: Any, engine: str, path: Path) -> None:
    """Check the shape of one engine's ``expect.<engine>.legend``.

    The key is per engine rather than shared, because the default legend is engine
    specific: an engine that can draw a good legend inside the diagram does, and that one
    is already asserted byte-exactly by ``source``.  Absence is therefore meaningful --
    it asserts that *this* engine renders no external legend -- so a present key naming
    nothing would claim one while asserting nothing about it, which is a hard error
    rather than a silent pass.

    :param legend: The engine's ``legend`` expectation, if it has one.
    :param engine: The engine it belongs to, for messages.
    :param path: Where it came from, for messages.
    :raises AssertionError: If the key is malformed.
    """
    if legend is None:
        return
    where = f"{path.name}: expect.{engine}.legend"
    _check_keys(legend, LEGEND_SECTIONS, where)
    assert legend, (
        f"{where} is present but names no section; "
        "omit the key to assert that this engine renders no external legend"
    )
    for part, labels in legend.items():
        assert isinstance(labels, list), f"{where}.{part} must be a list"
        assert labels, (
            f"{where}.{part} is an empty list; omit the section, or omit the whole key "
            "to assert no external legend"
        )


def _conf_py(case: dict[str, Any], engine: str, plantuml_command: str) -> str:
    """Build the ``conf.py`` of a case's minimal project.

    Only the portable vocabulary reaches the configuration: a case cannot name a
    ``needs_flow_*`` key itself, so a rename here cannot silently break the corpus.

    :param case: The parsed case file.
    :param engine: The engine to draw with.
    :param plantuml_command: How to run plantuml, from the suite-wide fixture. A project
        left on the default command renders only where a ``plantuml`` happens to be
        installed, and the render failure everywhere else arrives as a warning that this
        harness -- correctly -- refuses as outside the degradation registry.
    :return: The ``conf.py`` source.
    :raises AssertionError: If the case names configuration with no surface here.
    """
    config = dict(case.get("config") or {})
    # split rather than renamed, so it is popped before the simple renames are checked
    engine_config = config.pop("engine_config", None)
    _require_mapped(config, CONFIG_KEYS, "config")

    types = case.get("types") or [
        {"directive": "req", "title": "Requirement", "prefix": "R_"}
    ]
    for type_ in types:
        _require_mapped(type_, TYPE_KEYS, "types entry")
    links = {}
    for link in case.get("links", []):
        _require_mapped(link, LINK_KEYS, "links entry")
        links[link["option"]] = {k: v for k, v in link.items() if k != "option"}

    lines = [
        'extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]',
        'plantuml_output_format = "svg"',
        'graphviz_output_format = "svg"',
        # ids in the corpus deliberately include punctuation (node-id injectivity)
        'needs_id_regex = "^[A-Za-z0-9_=.-]+$"',
        "needs_id_required = True",
        f"needs_flow_engine = {engine!r}",
        f"needs_types = {types!r}",
        f"plantuml = {plantuml_command!r}",
    ]
    if links:
        lines.append(f"needs_links = {links!r}")
    if legends := case.get("legends"):
        lines.append(f"needs_flow_legends = {legends!r}")
    if engine_config is not None:
        # only this engine's half of the registry, which is where the split shows: a
        # case naming an engine config for one engine says nothing about the other
        lines.append(
            f"{ENGINE_CONFIG_KEYS[engine]} = {(engine_config.get(engine) or {})!r}"
        )
    for key, value in config.items():
        lines.append(f"{CONFIG_KEYS[key]} = {value!r}")
    return "\n".join(lines) + "\n"


def _index_rst(case: dict[str, Any]) -> str:
    """Build the document of a case's minimal project.

    :param case: The parsed case file.
    :return: The reStructuredText source.
    :raises AssertionError: If the case names an option with no surface here.
    """
    lines = ["Corpus case", "===========", ""]
    for need in case["needs"]:
        lines.append(f".. {need['type']}:: {need.get('title', need['id'])}")
        lines.append(f"   :id: {need['id']}")
        if status := need.get("status"):
            lines.append(f"   :status: {status}")
        if tags := need.get("tags"):
            lines.append(f"   :tags: {', '.join(tags)}")
        for link_type, targets in (need.get("links") or {}).items():
            lines.append(f"   :{link_type}: {', '.join(targets)}")
        lines.append("")

    lines.append(".. needflow::")
    lines.append("   :debug:")
    for key, value in (case.get("options") or {}).items():
        _require_mapped([key], OPTION_NAMES, "options")
        if key in OPTION_FREE_VALUES:
            # a name rather than an enumeration member, so it is written through as it
            # stands; an empty one means the option was written bare
            written = str(value) or _BARE
        else:
            accepted = OPTION_VALUES[key]
            if value not in accepted:
                raise AssertionError(
                    f"options: this repository cannot express {key}: {value!r} yet, only "
                    f"{sorted(accepted)}; the slice that widens the option maps it here"
                )
            written = accepted[value]
        name = OPTION_NAMES[key]
        lines.append(f"   :{name}:" if written is _BARE else f"   :{name}: {written}")
    lines.append("")
    return "\n".join(lines)


def _normalise(source: str, need_ids: list[str]) -> str:
    """Apply the spec's normalisation to an emitted diagram source.

    Node hyperlink targets are repository specific -- they depend on the builder, the
    output format and where the document sits -- so each is replaced by a token naming
    the need it points at.  Everything else, indentation and ordering included, is
    contract.

    :param source: The emitted diagram source.
    :param need_ids: Every id the case draws, longest first when substituted so that an
        id which is a prefix of another is never matched in its place.
    :return: The normalised source.
    """
    for need_id in sorted(need_ids, key=len, reverse=True):
        quoted = re.escape(need_id)
        # plantuml: `[[<url>]]`, graphviz: `href="<url>"`
        source = re.sub(
            rf"\[\[[^\]]*#{quoted}\]\]", f"[[<NODE_URL:{need_id}>]]", source
        )
        source = re.sub(
            rf'href="[^"]*#{quoted}"', f'href="<NODE_URL:{need_id}>"', source
        )
    lines = [line.rstrip() for line in source.splitlines()]
    return "\n".join(lines).rstrip("\n") + "\n"


def _emitted_source(app: Any) -> str:
    """Pull the generated diagram source out of a built project.

    The ``:debug:`` option is what exposes it, exactly as the spec says, but it is read
    from the doctree rather than from rendered HTML so that how the block is *rendered*
    cannot change what the corpus compares.

    :param app: The built Sphinx application.
    :return: The single diagram's source.
    """
    from sphinx_needs.directives.needflow._directive import (
        NeedflowGraphiz,
        NeedflowPlantuml,
    )

    doctree = app.env.get_and_resolve_doctree("index", app.builder)
    for node in doctree.findall(NeedflowPlantuml):  # pragma: no cover - engine specific
        raise AssertionError(f"unresolved plantuml needflow: {node}")
    sources = [node["resolved_content"] for node in doctree.findall(NeedflowGraphiz)]
    if sources:
        assert len(sources) == 1, "a corpus case draws exactly one diagram"
        return str(sources[0])

    # plantuml keeps its source on the `plantuml` node the engine replaced itself with
    from sphinxcontrib.plantuml import plantuml

    umls = [node["uml"] for node in doctree.findall(plantuml)]
    assert len(umls) == 1, f"a corpus case draws exactly one diagram, got {len(umls)}"
    return str(umls[0])


def _legend_rows(app: Any) -> dict[str, list[str]] | None:
    """Read the rendered out-of-diagram legend, section by section.

    :param app: The built Sphinx application.
    :return: The row labels of each section present, in document order, or ``None`` if
        the page renders no legend at all.
    """
    from lxml import html as html_parser

    tree = html_parser.parse(Path(str(app.outdir)) / "index.html")
    legends = tree.xpath(
        "//div[contains(concat(' ', normalize-space(@class), ' '), "
        f"' {_LEGEND_CLASS} ')]"
    )
    if not legends:
        return None
    assert len(legends) == 1, "a case draws one diagram, so it renders one legend"

    # the label column differs per section, because a type row leads with its colour
    # swatch and a link row with the link name
    columns = {"types": 2, "links": 1}

    # iterated in DOCUMENT order rather than in a fixed order, because `parts` is an
    # ordered list: a legend asked for `[links, types]` must render links first, and a
    # reader that collected the sections in a fixed order could never see the difference
    rows: dict[str, list[str]] = {}
    for table in legends[0].xpath(
        "..//table[contains(concat(' ', normalize-space(@class), ' '), "
        f"' {_LEGEND_CLASS}_table ')]"
    ):
        classes = str(table.get("class", "")).split()
        parts = [part for part in columns if f"{_LEGEND_CLASS}_{part}" in classes]
        assert len(parts) == 1, f"a legend table names one section, got {classes}"
        part = parts[0]
        rows[part] = [
            cell.text_content().strip()
            for cell in table.xpath(f".//tbody/tr/td[{columns[part]}]")
        ]
    return rows


def _compare_legend(
    rendered: dict[str, list[str]] | None, expected: dict[str, Any] | None
) -> None:
    """Check a rendered EXTERNAL legend against this engine's expectation.

    Only the out-of-diagram legend is checked here.  A legend an engine draws *inside*
    the diagram is already part of that engine's ``source`` and is compared byte-exactly
    there, so giving it a key of its own would state the same contract twice and let the
    two drift.  A case where an engine draws its legend internally therefore has no
    ``legend`` key for that engine, and this asserts that nothing external appeared.

    :param rendered: What the page rendered, from :func:`_legend_rows`.
    :param expected: The engine's ``legend`` expectation, if it has one.
    :raises AssertionError: If the two disagree.
    """
    if expected is None:
        assert rendered is None, (
            "this engine has no 'legend' expectation, so it must render no external "
            f"legend, but rendered {rendered}"
        )
        return

    assert rendered is not None, "expected an external legend, but none was rendered"
    # sections compared as a SEQUENCE, not a set: `parts` is an ordered list, so which
    # section comes first is contract and a set comparison would silently accept either
    assert list(rendered) == list(expected), (
        f"legend sections differ: expected {list(expected)}, rendered {list(rendered)}"
    )
    for part, labels in expected.items():
        # exact rows, in order -- the drawn-only scope rule is what makes this an
        # assertion rather than a containment check
        assert rendered[part] == labels, (
            f"legend {part!r} rows differ: expected {labels}, got {rendered[part]}"
        )


def _classify_warnings(text: str) -> tuple[list[str], list[str]]:
    """Classify a build's warnings against the degradation registry.

    :param text: The build's warning stream.
    :return: The neutral ids observed, and any warning that matched none of them.
    """
    observed: list[str] = []
    unexpected: list[str] = []
    for line in strip_colors(text).splitlines():
        if not line.strip() or _IGNORED_WARNINGS.search(line):
            continue
        for name, (_tier, subtype, pattern) in DEGRADATIONS.items():
            if subtype in line and pattern.search(line):
                observed.append(name)
                break
        else:
            unexpected.append(line)
    return observed, unexpected


def _wanted_degradations(expected: dict[str, Any], engine: str) -> list[str]:
    """The degradation ids a case declares for an engine this repository draws with.

    :param expected: The engine's expectation.
    :param engine: The engine, for messages.
    :return: The neutral ids declared.
    :raises AssertionError: If one of them is not observable here.
    """
    wanted = [entry["id"] for entry in expected.get("degradations", [])]
    _require_mapped(wanted, DEGRADATIONS, f"expect.{engine}.degradations")
    return wanted


@pytest.mark.parametrize("path", _case_files(), ids=lambda p: p.stem)
def test_case_checksum_is_stamped(path: Path) -> None:
    """Every case file must be checksummed in the manifest, at its current bytes.

    This is what makes an unsynchronised edit visible: the two repositories hold the same
    files, and a change that skips the manifest turns red here rather than becoming a
    silent difference between them.
    """
    if os.environ.get("UBC_UPDATE_CORPUS"):
        # a regeneration run rewrites both the case files and the manifest, so which of
        # the two this test happens to read first would decide whether it passes; the
        # stamp is checked on the ordinary run that follows, which is the one that counts
        pytest.skip("regenerating; checksums are checked on the next ordinary run")
    manifest = _load_manifest()
    assert path.name in manifest["cases"], (
        f"{path.name} is not stamped in manifest.json"
    )
    assert manifest["cases"][path.name] == _sha256(path), (
        f"{path.name} does not match its manifest checksum; "
        "regenerate the manifest and bump corpus_version"
    )


def test_readme_checksum_is_stamped() -> None:
    """The spec travels with the corpus, so it is stamped like any case."""
    if os.environ.get("UBC_UPDATE_CORPUS"):
        pytest.skip("regenerating; checksums are checked on the next ordinary run")
    manifest = _load_manifest()
    assert manifest["readme"] == _sha256(CORPUS_ROOT / "README.md"), (
        "README.md does not match its manifest checksum; "
        "regenerate the manifest and bump corpus_version"
    )


def test_manifest_has_no_orphans() -> None:
    """The manifest may not stamp a case that no longer exists.

    Skipped while regenerating for the same reason as the checksum tests: adding or
    removing a case makes the manifest and the case directory disagree until the rewrite
    lands, so whether this ran before or after it would decide the result.
    """
    if os.environ.get("UBC_UPDATE_CORPUS"):
        pytest.skip("regenerating; the manifest is checked on the next ordinary run")
    manifest = _load_manifest()
    assert set(manifest["cases"]) == {p.name for p in _case_files()}


@pytest.fixture(scope="session", autouse=True)
def _restamp_the_manifest() -> Any:
    """Rewrite ``manifest.json`` when the run regenerated the corpus.

    This is the only supported way to restamp it, and it goes through
    :func:`_build_manifest` -- the same function the assertion uses -- so the checksums a
    run *writes* can never be computed differently from the checksums a run *checks*.

    It is a session finaliser rather than a test because of the order: a test would have
    to run after every case rewrite to stamp the bytes those rewrites produced, and no
    test can promise that. Stamping too early is not a harmless race but a wrong file --
    it records the corpus as it was before the run changed it, and one regeneration pass
    could then never converge. ``corpus_version`` is never touched: bumping it is a
    deliberate act, and the standing rule is that any case or README change bumps it.
    """
    yield
    if os.environ.get("UBC_UPDATE_CORPUS"):
        expected = _build_manifest(_load_manifest()["corpus_version"])
        MANIFEST.write_text(json.dumps(expected, indent=2) + "\n", "utf8")


def test_manifest_matches_the_corpus() -> None:
    """The whole manifest must describe the corpus that is actually on disk."""
    if os.environ.get("UBC_UPDATE_CORPUS"):
        pytest.skip("regenerating; the manifest is restamped when the run finishes")
    manifest = _load_manifest()
    assert manifest == _build_manifest(manifest["corpus_version"]), (
        "manifest.json does not describe the corpus on disk; regenerate it with "
        "UBC_UPDATE_CORPUS=1 and bump corpus_version"
    )


@pytest.mark.parametrize("path", _case_files(), ids=lambda p: p.stem)
@pytest.mark.parametrize("engine", ENGINES)
def test_conformance_case(
    make_app,
    tmp_path: Path,
    plantuml_command: str,
    path: Path,
    engine: str,
) -> None:
    """Draw a corpus case and compare it with the expected source and degradations."""
    case = yaml.safe_load(path.read_text("utf8"))
    validate_case(case, path)

    updating = bool(os.environ.get("UBC_UPDATE_CORPUS"))
    expected = case["expect"].get(engine)
    if expected is None and not updating:
        pytest.skip(f"{path.stem}: no {engine} expectation")
    if expected and (reason := expected.get("skip")):
        pytest.skip(f"{path.stem}: {reason}")

    (tmp_path / "conf.py").write_text(_conf_py(case, engine, plantuml_command), "utf8")
    (tmp_path / "index.rst").write_text(_index_rst(case), "utf8")

    app = make_app(srcdir=tmp_path, buildername="html")
    app.build()

    # the warnings are read before the source is, because reading the source re-resolves
    # the doctree and so runs the needflow post-transform (and its warnings) a second time
    observed, unexpected = _classify_warnings(app._warning.getvalue())

    need_ids = [need["id"] for need in case["needs"]]
    source = _normalise(_emitted_source(app), need_ids)

    if updating:
        # recorded, never asserted: under regeneration the rendered legend IS the new
        # expectation, so checking it against the old one would only ever reject the
        # rewrite this run exists to produce
        _rewrite_expectation(path, engine, source, _legend_rows(app), observed)
        pytest.skip(f"{path.stem}: {engine} expectation rewritten")

    _compare_legend(_legend_rows(app), expected.get("legend"))

    wanted = _wanted_degradations(expected, engine)

    assert unexpected == [], (
        f"{path.stem} produced warnings outside the degradation registry"
    )
    assert sorted(observed) == sorted(wanted), (
        f"{path.stem}: degradations differ on {engine}"
    )
    assert source == expected["source"], f"{path.stem}: {engine} source differs"


def _rewrite_expectation(
    path: Path,
    engine: str,
    source: str,
    legend: dict[str, list[str]] | None,
    observed: list[str],
) -> None:
    """Write a freshly emitted source back into a case file.

    Only ever reached under ``UBC_UPDATE_CORPUS``; the result is a diff to read, not an
    expectation to accept.

    The observed degradations are written too, and have to be: a regeneration that kept
    only the source would silently *delete* the degradation entries of every case whose
    point is a degradation, leaving them asserting the fallback source and nothing about
    the warning that produced it.  ``tier`` comes from :data:`DEGRADATIONS` rather than
    from the build, since a warning does not carry its own tier, and ``once`` from
    whether the tier is 2 (warn once per project) -- both are properties of the registry
    entry, so a regenerated case states them as the registry does.

    :param path: The case file.
    :param engine: The engine whose expectation to replace.
    :param source: The emitted source.
    :param legend: The external legend rows rendered, if any.
    :param observed: The neutral degradation ids the build emitted.
    """
    case = yaml.safe_load(path.read_text("utf8"))
    entry: dict[str, Any] = {"source": source}
    if legend:
        entry["legend"] = legend
    if observed:
        entry["degradations"] = [
            {
                "id": name,
                "tier": DEGRADATIONS[name][0],
                "once": DEGRADATIONS[name][0] == 2,
            }
            for name in sorted(set(observed))
        ]
    case.setdefault("expect", {})[engine] = entry
    # engines in a stable order, so that a re-sync diff is about content
    case["expect"] = {
        name: case["expect"][name] for name in SPEC_ENGINES if name in case["expect"]
    }
    path.write_text(_dump_case(case), "utf8")


class _CorpusDumper(yaml.SafeDumper):
    """A dumper that keeps a diagram source readable.

    The corpus is reviewed by people in two repositories, and an expectation nobody can
    read is an expectation nobody checks -- so a multi-line string is written as a
    literal block rather than escaped onto one line.
    """


def _str_representer(dumper: yaml.SafeDumper, data: str) -> Any:
    """Represent a multi-line string as a literal block."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_CorpusDumper.add_representer(str, _str_representer)


def _dump_case(case: dict[str, Any]) -> str:
    """Serialise a case file.

    :param case: The case to write.
    :return: Its YAML text.
    """
    return yaml.dump(  # type: ignore[no-any-return]
        case,
        Dumper=_CorpusDumper,
        sort_keys=False,
        allow_unicode=True,
        width=100,
        default_flow_style=False,
    )


# --- the harness's own contract ------------------------------------------------------
#
# The spec lists what the runner must refuse. A corpus whose runner quietly accepts a
# malformed case is worse than no corpus: the case still appears in the count, still
# looks green, and asserts nothing. These pin each refusal.

_MINIMAL_CASE = {
    "id": "probe",
    "title": "probe",
    "purpose": "probe",
    "needs": [{"id": "REQ_1", "type": "req", "title": "One"}],
    "expect": {"plantuml": {"source": "@startuml\n@enduml\n"}},
}


def _probe(**overrides: Any) -> dict[str, Any]:
    """A minimal valid case, with the given keys replaced."""
    return {**_MINIMAL_CASE, **overrides}


@pytest.mark.parametrize(
    "case,fragment",
    [
        (_probe(nonsuch="x"), "unknown key(s) ['nonsuch']"),
        (_probe(options={"nonsuch": "x"}), "options uses unknown key(s) ['nonsuch']"),
        (_probe(config={"nonsuch": "x"}), "config uses unknown key(s) ['nonsuch']"),
        (
            _probe(types=[{"directive": "req", "nonsuch": 1}]),
            "types entry uses unknown key(s) ['nonsuch']",
        ),
        (
            _probe(links=[{"option": "links", "nonsuch": 1}]),
            "links entry uses unknown key(s) ['nonsuch']",
        ),
        (
            _probe(needs=[{"id": "R", "type": "req", "nonsuch": 1}]),
            "needs entry uses unknown key(s) ['nonsuch']",
        ),
        (_probe(id="wrong"), "'id' must equal the filename stem"),
        (_probe(purpose=""), "'purpose' is required"),
        (_probe(expect={}), "'expect' is empty"),
        (
            _probe(expect={"plantuml": {"nonsuch": "x"}}),
            "expect.plantuml uses unknown key(s) ['nonsuch']",
        ),
        (_probe(expect={"plantuml": {"legend": {"types": ["R"]}}}), "has no 'source'"),
        (
            _probe(
                expect={
                    "plantuml": {
                        "source": "x",
                        "degradations": [{"id": "shape-unmapped", "tier": 1}],
                    }
                }
            ),
            "tier 1 is silent by definition",
        ),
        (
            _probe(
                expect={
                    "plantuml": {
                        "source": "x",
                        "degradations": [{"id": "made-up", "tier": 2}],
                    }
                }
            ),
            "unknown degradation id 'made-up'",
        ),
        (_probe(expect={"crayon": {"source": "x"}}), "unknown engine 'crayon'"),
        (
            _probe(expect={"plantuml": {"source": "x", "legend": {"types": []}}}),
            "expect.plantuml.legend.types is an empty list",
        ),
        (
            _probe(expect={"plantuml": {"source": "x", "legend": {}}}),
            "present but names no section",
        ),
        (
            _probe(expect={"plantuml": {"source": "x", "legend": {"nosuch": ["x"]}}}),
            "expect.plantuml.legend uses unknown key(s) ['nosuch']",
        ),
    ],
    ids=[
        "top-level-key",
        "option-key",
        "config-key",
        "type-key",
        "link-key",
        "need-key",
        "id-mismatch",
        "missing-purpose",
        "empty-expect",
        "expect-entry-key",
        "missing-source",
        "tier-1-entry",
        "unknown-degradation",
        "unknown-engine",
        "empty-legend-list",
        "empty-legend-key",
        "unknown-legend-section",
    ],
)
def test_validator_refuses_malformed_cases(
    case: dict[str, Any], fragment: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each rule the spec's harness contract lists must actually be enforced."""
    monkeypatch.delenv("UBC_UPDATE_CORPUS", raising=False)
    with pytest.raises(AssertionError, match=re.escape(fragment)):
        validate_case(case, Path("probe.yaml"))


def test_validation_ignores_what_only_the_other_repository_can_draw() -> None:
    """A well formed case may name vocabulary this repository has no surface for.

    The file is shared, and the repository of record lands a case first. Reading it must
    therefore not fail on an option or a degradation only the other copy can exercise --
    that is refused when a project is *built* from the case, so that a case skipped here
    stays readable here.
    """
    validate_case(
        _probe(
            id="probe",
            config={"direction": "up"},
            options={"styles": "[status == 'open']:warn"},
            expect={
                "plantuml": {"skip": "no :direction: upstream yet"},
                "mermaid": {
                    "source": "flowchart TB\n",
                    "degradations": [
                        {
                            "id": "direction-vertical-unsupported",
                            "tier": 2,
                            "once": True,
                        }
                    ],
                },
            },
        ),
        Path("probe.yaml"),
    )


@pytest.mark.parametrize(
    "case,fragment",
    [
        (
            _probe(config={"styles": {"critical": {"fill": "#FF0000"}}}),
            "config: the corpus format defines ['styles']",
        ),
        (
            _probe(types=[{"directive": "req", "shape": "rectangle"}]),
            "types entry: the corpus format defines ['shape']",
        ),
        (
            _probe(links=[{"option": "links", "arrow": "open"}]),
            "links entry: the corpus format defines ['arrow']",
        ),
    ],
    ids=["config-key", "type-shape", "link-arrow"],
)
def test_conf_py_refuses_configuration_with_no_surface_here(
    case: dict[str, Any], fragment: str
) -> None:
    """Configuration this repository cannot express must fail, not be dropped.

    Silently building the project without it would leave the case asserting the output of
    a diagram that was never asked for the thing the case exists to check.
    """
    with pytest.raises(AssertionError, match=re.escape(fragment)):
        _conf_py(case, "plantuml", "plantuml")


@pytest.mark.parametrize(
    "options,fragment",
    [
        (
            {"styles": "[type == 'req']:critical"},
            "options: the corpus format defines ['styles']",
        ),
        ({"link_labels": "incomming"}, "cannot express link_labels: 'incomming' yet"),
        ({"direction": "sideways"}, "cannot express direction: 'sideways' yet"),
    ],
    ids=["unmapped-option", "misspelt-value", "unmapped-value"],
)
def test_index_rst_refuses_options_with_no_surface_here(
    options: dict[str, str], fragment: str
) -> None:
    """An option, or an option *value*, this repository cannot express must fail.

    The value half matters as much as the name.  For an option that is still a bare flag
    a wrong value would be built as the flag -- which can mean the opposite -- and for an
    enumerated one it would be written through to a directive that then reports it, so
    the case would assert the fallback rather than what it asked for.  A value outside the
    enumeration is refused here instead, whether it is a typo or a member only the other
    tool has.
    """
    with pytest.raises(AssertionError, match=re.escape(fragment)):
        _index_rst(_probe(options=options))


@pytest.mark.parametrize(
    "options,written",
    [
        ({"show_legend": "compact"}, ":show_legend: compact"),
        ({"engine_config": "corporate"}, ":config: corporate"),
    ],
    ids=["legend-key", "engine-config-name"],
)
def test_index_rst_writes_a_name_valued_option_verbatim(
    options: dict[str, str], written: str
) -> None:
    """A legend key and an engine config name are names, not enumeration members.

    Neither is a closed set -- a project calls its legends and its engine configs
    whatever it likes -- so the value is written through as it stands, and there is no
    table of accepted values to keep in step with every project's ``conf.py``.
    """
    assert written in _index_rst(_probe(options=options))


def test_index_rst_writes_a_mapped_option_as_the_bare_flag() -> None:
    """The two mapped options are written with this repository's spelling.

    The corpus calls the label selector ``link_labels``; both tools spell the option
    ``:show_link_names:``, and upstream it is still a bare flag whose meaning is exactly
    the portable ``outgoing``.
    """
    text = _index_rst(_probe(options={"link_labels": "outgoing", "show_legend": ""}))
    assert ":show_link_names:" in text
    assert ":show_link_names: " not in text
    assert ":show_legend:" in text
    assert "link_labels" not in text


def test_declared_degradations_must_be_observable_here() -> None:
    """A case may not claim a degradation this repository cannot emit.

    It would be a comparison that can only fail, and it would fail with a message about
    a missing warning rather than about the option that does not exist yet.
    """
    with pytest.raises(AssertionError, match=re.escape("has no surface for it yet")):
        _wanted_degradations(
            {"degradations": [{"id": "shape-unmapped", "tier": 2}]}, "plantuml"
        )


def test_a_warning_outside_the_registry_is_unexpected() -> None:
    """Every warning a build emits is either a mapped degradation or a failure.

    A warning that matches no registry entry is what makes the no-warning fence of the
    shipped cases a fence at all: it cannot be absorbed as "some degradation".
    """
    observed, unexpected = _classify_warnings(
        "index.rst:4: WARNING: something happened [needs.needflow]\n"
        "WARNING: document isn't included in any toctree\n"
    )
    assert observed == []
    assert unexpected == ["index.rst:4: WARNING: something happened [needs.needflow]"]


@pytest.mark.parametrize(
    "rendered,expected,fragment",
    [
        ({"types": ["Requirement"]}, None, "must render no external legend"),
        (None, {"types": ["Requirement"]}, "none was rendered"),
        (
            {"links": ["links to"], "types": ["Requirement"]},
            {"types": ["Requirement"], "links": ["links to"]},
            "legend sections differ",
        ),
        (
            {"types": ["Specification", "Requirement"]},
            {"types": ["Requirement", "Specification"]},
            "legend 'types' rows differ",
        ),
    ],
    ids=["unexpected-legend", "missing-legend", "section-order", "row-order"],
)
def test_legend_comparison_is_ordered(
    rendered: dict[str, list[str]] | None,
    expected: dict[str, Any] | None,
    fragment: str,
) -> None:
    """The legend expectation is a SEQUENCE of sections, each an ordered list of rows.

    ``parts`` is an ordered list, so which section comes first and which row comes first
    are both contract. A set or containment comparison would accept either order, and the
    order would then be untestable.
    """
    with pytest.raises(AssertionError, match=re.escape(fragment)):
        _compare_legend(rendered, expected)


def test_legend_comparison_accepts_the_expected_order() -> None:
    """...and the expectation it does accept is the one written down."""
    _compare_legend(
        {"types": ["Requirement"], "links": ["links to"]},
        {"types": ["Requirement"], "links": ["links to"]},
    )
    _compare_legend(None, None)


def test_checksum_mismatch_is_detected(tmp_path: Path) -> None:
    """A case edited without restamping the manifest must be caught.

    This is the whole mechanism by which the two repositories' copies stay comparable:
    the checksum is the only thing that notices an edit which never reached the manifest.
    """
    if os.environ.get("UBC_UPDATE_CORPUS"):
        # the manifest on disk still describes the corpus as it was before this run
        # rewrote it, so what this compares against is stale until the finaliser lands
        pytest.skip("regenerating; the stamp is checked on the next ordinary run")
    case = next(iter(_case_files()))
    original = _sha256(case)
    tampered = tmp_path / case.name
    tampered.write_bytes(case.read_bytes() + b"\n# edited\n")

    assert _sha256(tampered) != original
    manifest = _load_manifest()
    assert manifest["cases"][case.name] == original
    assert manifest["cases"][case.name] != _sha256(tampered)


def test_line_endings_do_not_change_a_checksum(tmp_path: Path) -> None:
    """The same content must hash the same however its lines happen to end.

    Git hands a Windows checkout CRLF under ``text=auto``, so hashing raw bytes made the
    same corpus fail there while passing on Linux. The two halves of the contract are
    pinned together here: a line-ending rewrite must NOT move the checksum, and a real
    edit must still move it -- otherwise normalisation would have bought portability by
    giving up the tamper detection it exists to serve.
    """
    case = next(iter(_case_files()))
    # derived from whatever the working tree happens to hold, because that is precisely
    # what varies: a Windows checkout of this very file may already be CRLF
    content = case.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    variants = {
        "lf.yaml": content,
        "crlf.yaml": content.replace(b"\n", b"\r\n"),
        "cr.yaml": content.replace(b"\n", b"\r"),
    }
    digests = set()
    for name, encoded in variants.items():
        path = tmp_path / name
        path.write_bytes(encoded)
        digests.add(_sha256(path))
    assert len(digests) == 1, "the same content hashed differently per line ending"
    assert digests == {_sha256(case)}, "and differently again from the corpus file"

    # ...and a change to the content itself is still caught, whatever the endings
    edited = tmp_path / "edited.yaml"
    edited.write_bytes(variants["crlf.yaml"] + b"\r\n# edited\r\n")
    assert _sha256(edited) != _sha256(case)
