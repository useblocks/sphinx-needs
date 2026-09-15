"""``test-reports`` command line interface.

``test-reports build needs`` turns test-result XML into needs.json *outside* Sphinx, so a build system can
schedule and cache the conversion and the documentation build only imports the
result. Nothing in the import chain of this module may import Sphinx; the test
suite asserts that.

The conversion settings come from three places, highest precedence first: a
command-line flag, the ``[test_reports.build.needs]`` table of the project's
``ubproject.toml``, the built-in default. The file is the declarative
description of the project that the Sphinx build reads too, so the two
consumers cannot drift apart; the flags stay for per-invocation values such as
the commit a CI job is converting for.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

from sphinxcontrib.test_reports.junitparser import JUnitParser
from sphinxcontrib.test_reports.needs_export import (
    DEFAULT_VERSION,
    Report,
    build_needs_file,
    iter_cases,
    optional,
)
from sphinxcontrib.test_reports.projectconfig import (
    CONVERSION_KEYS,
    DEFAULT_NEED_TYPE,
    DEFAULT_TOML_FILENAME,
    NEEDS_TABLE_PATH,
    SECTION,
    TomlConfigError,
    case_need_type,
    field_names,
    find_project_config,
    load_project_config,
    needs_settings,
)
from sphinxcontrib.test_reports.remote import (
    DEFAULT_URL_PATTERN,
    check_url_pattern,
    normalise_remote_url,
)

#: How the table is spelled in help texts and diagnostics.
TABLE = f"[{NEEDS_TABLE_PATH}]"


def _warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


# The conversion settings are resolved key by key in a loop (see
# `_resolve_settings`), which a TypedDict cannot express, so the mapping stays
# `dict[str, object]`. These two state at the point of use the type
# `_NEEDS_KEY_TYPES` already enforces when the file is read.
def _text(value: object) -> str:
    """A setting the validation pins to a string."""
    return value if isinstance(value, str) else ""


def _texts(value: object) -> "list[str]":
    """A setting the validation pins to a list of strings."""
    return [str(item) for item in value] if isinstance(value, list) else []


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="test-reports",
        description="Convert test-result XML into sphinx-needs data.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    # `build <artifact>`, as ubCode spells it (`ubc build needs`): the command
    # names what gets produced, and leaves room for further artifacts.
    build = subcommands.add_parser(
        "build",
        help="Build an artifact from test-result XML.",
        description="Build an artifact from one or more test-result XML files.",
    )
    artifacts = build.add_subparsers(dest="artifact", required=True)
    needs = artifacts.add_parser(
        "needs",
        help="Build a needs.json from one or more test-result XML files.",
        description=(
            "Build a needs.json from one or more test-result XML files, ready "
            "to be consumed with needimport or needs_external_needs. Settings "
            f"default to the {TABLE} table of {DEFAULT_TOML_FILENAME}; a flag "
            "overrides the file's value for that key."
        ),
    )
    needs.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="Test-result XML files (a build system passes these as a file list).",
    )
    needs.add_argument(
        "--output",
        "-o",
        required=True,
        metavar="PATH",
        help="Where to write the needs.json.",
    )
    # Every setting the TOML file can supply defaults to None here and is
    # resolved in _resolve_settings: a given flag beats the file, which beats
    # the built-in default. None is safe because each key resolves to a
    # concrete value there.
    needs.add_argument(
        "--project",
        default=None,
        help="Project name recorded in the needs.json envelope (default: empty).",
    )
    needs.add_argument(
        "--version",
        default=None,
        help=f"Version key in the envelope (default: {DEFAULT_VERSION}).",
    )
    needs.add_argument(
        "--need-type",
        default=None,
        help=(
            f"Need type for each test case (default: {DEFAULT_NEED_TYPE}). Must "
            f"agree with the type of case in [{SECTION}] when a config file "
            "applies."
        ),
    )
    needs.add_argument(
        "--tags",
        default=None,
        help="Comma-separated tags applied to every created need.",
    )
    needs.add_argument(
        "--link-property",
        action="append",
        default=None,
        metavar="PROPERTY=LINK_FIELD",
        help=(
            "Promote an XML property to a link field, comma-splitting its value "
            "(repeatable), e.g. PartiallyVerifies=partially_verifies. Given at "
            "all, it replaces the file's link_properties table."
        ),
    )
    needs.add_argument(
        # Named after `tr_extra_options`, which the flag defaults from.
        # sphinx-needs has since renamed `needs_extra_options` to
        # `needs_fields`; realigning this extension's vocabulary is issue #157.
        "--extra-option",
        action="append",
        default=None,
        metavar="NAME",
        help=(
            "Export the XML property NAME as a need field (repeatable), in "
            f"addition to the extra_options of [{SECTION}] -- the same list that "
            "makes the build accept the field. A NAME that list lacks is "
            "reported. Properties named by neither are reported and left out."
        ),
    )
    needs.add_argument(
        "--remote-url",
        default=None,
        help="Repository URL used to synthesize source links; git remotes are accepted.",
    )
    needs.add_argument(
        "--commit",
        default=None,
        help="Commit-ish the reports were produced from.",
    )
    needs.add_argument(
        "--url-pattern",
        default=None,
        help=f"Source-URL template (default: {DEFAULT_URL_PATTERN}).",
    )
    needs.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help=(
            "Say on stderr where the search for the declarative config file "
            "ended when it found none, and name a --config file. Off by "
            "default: most runs have no file and should stay quiet, but a "
            "misplaced one must be diagnosable. A file the search did find is "
            "always named -- it may sit directories above, and the output "
            "depends on it."
        ),
    )
    config_source = needs.add_mutually_exclusive_group()
    config_source.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help=(
            f"Declarative config file to read the {TABLE} table from. By "
            f"default {DEFAULT_TOML_FILENAME} is searched for in the working "
            "directory and its parents, up to the project root; an explicitly "
            "given path is used as-is and must exist."
        ),
    )
    config_source.add_argument(
        "--no-config",
        action="store_true",
        help=(
            "Ignore the declarative config file entirely, so the output "
            "depends only on the arguments given here."
        ),
    )
    return parser


def _parse_link_properties(values: object) -> dict[str, str]:
    """Normalise the link-property mapping from any input spelling.

    Flags provide ``PROPERTY=LINK_FIELD`` strings; the TOML file provides a
    ``PROPERTY = "LINK_FIELD"`` table; neither given is ``None``. Both spellings
    must yield non-empty keys and values -- a silently dropped mapping would
    send link fields into needs.json as plain fields instead. This is the only
    place the mapping is normalised, so the two spellings cannot drift.

    The parameter is ``object`` because the value arrives from a flag or from
    the TOML file; this function is where its shape is established.
    """
    if values is None:
        return {}
    if isinstance(values, dict):
        mapping = {}
        for property_name, link_field in values.items():
            if not str(property_name).strip() or not str(link_field).strip():
                raise ValueError(
                    f'link_properties expects PROPERTY = "LINK_FIELD", got '
                    f"{property_name!r} = {link_field!r}"
                )
            mapping[str(property_name).strip()] = str(link_field).strip()
        return mapping

    if not isinstance(values, list):
        raise ValueError(
            f'link_properties expects a PROPERTY = "LINK_FIELD" table, got {values!r}'
        )

    mapping = {}
    for value in values:
        property_name, separator, link_field = str(value).partition("=")
        if not separator or not property_name.strip() or not link_field.strip():
            raise ValueError(
                f"--link-property expects PROPERTY=LINK_FIELD, got {value!r}"
            )
        mapping[property_name.strip()] = link_field.strip()
    return mapping


def _warn_about_absent_source_lines(
    path: Path, suites: Sequence[Mapping[str, object]]
) -> None:
    """Report the most common cause of a missing source location.

    pytest emits ``file``/``line`` as ``<testcase>`` attributes only under
    ``junit_family = xunit1`` (or ``legacy``); its default ``xunit2`` filters
    them out, which silently costs the source location of every case.
    """
    # Walk the report the way the export does: the parser files the cases of
    # a suite with nested <testsuite> elements under testsuite_nested only, so
    # looking at the top-level testcases alone goes quiet on nested reports.
    cases = [case for _suite_name, case in iter_cases(suites)]
    if cases and all(optional(case.get("line"), -1) == "" for case in cases):
        print(
            f"warning: {path}: no <testcase> carries a 'line' attribute, so no "
            "source location could be recorded. pytest emits file/line only "
            "with junit_family = xunit1 (or legacy); its default xunit2 drops "
            "them.",
            file=sys.stderr,
        )


def _warn_about_empty_report(
    path: Path, suites: Sequence[Mapping[str, object]]
) -> None:
    """A report without a single test case contributes nothing -- say so.

    A file that is not a test report at all (a ``pom.xml``, a ``coverage.xml``)
    parses as one empty suite, and a genuine report may have had every case
    filtered out. Either way the artifact ends up with fewer needs than the
    caller expects, and for a cached build output "0 needs" is the one outcome
    that must never be silent.
    """
    if not any(True for _ in iter_cases(suites)):
        _warn(
            f"{path}: no test cases found, so it adds no needs. A file that is "
            f"not a test report parses as an empty one."
        )


def _load_section(
    arguments: argparse.Namespace,
) -> "tuple[dict[str, object], Path | None, str | None]":
    """Load the ``[test_reports]`` section, honouring ``--config``/``--no-config``.

    Returns ``(section, path, error_message)``. ``section`` is ``{}`` and
    ``path`` ``None`` when no file applies: an absent *default* file is not an
    error, an explicitly given path that cannot be read is.

    The whole section is loaded, not only the converter's table: validation
    covers the file as the build sees it, and the build's ``case`` entry is
    needed to check the need type against.

    The default file is searched for upwards from the working directory, since
    it conventionally sits at the project root while the converter runs from
    wherever CI invoked it. That is also where the Sphinx side looks, so both
    consumers read the same file. A file the search finds is always named on
    stderr: it may sit directories above the invocation, and the bytes written
    depend on it, so a cached artifact has to be traceable to the file that
    shaped it -- the Sphinx bridge logs the same at INFO on every build. With
    ``--verbose`` a fruitless search also reports where it ended, and an
    explicitly given file is named too.
    """
    if arguments.no_config:
        return {}, None, None

    def verbose(message: str) -> None:
        if arguments.verbose:
            print(message, file=sys.stderr)

    if arguments.config is not None:
        path = Path(arguments.config)
        if not path.is_file():
            return {}, None, f"error: no such config file: {path}"
        verbose(f"reading [{SECTION}] from {path}")
    else:
        found = find_project_config(Path.cwd(), report=verbose)
        if found is None:
            return {}, None, None
        path = found
        print(f"reading [{SECTION}] from {path}", file=sys.stderr)

    try:
        section = load_project_config(path, _warn) or {}
    except TomlConfigError as error:
        return {}, path, f"error: {error}"
    return section, path, None


#: Built-in value of every conversion setting, used when neither a flag nor
#: the TOML file supplies one. Keyed by :data:`CONVERSION_KEYS`, and checked
#: against it at import time, so a key cannot be added to the table without
#: also being given a default here.
_DEFAULTS: "dict[str, object]" = {
    "project": "",
    "version": DEFAULT_VERSION,
    "need_type": DEFAULT_NEED_TYPE,
    "tags": "",
    "link_properties": None,
    "remote_url": "",
    "commit": "",
    "url_pattern": DEFAULT_URL_PATTERN,
}
if set(_DEFAULTS) != set(CONVERSION_KEYS):  # pragma: no cover - import-time guard
    raise RuntimeError("every [test_reports.build.needs] key needs a built-in default")

#: argparse destination per conversion key, where it differs from the key.
#: Only the repeatable ``--link-property`` flag does.
_DESTS = {"link_properties": "link_property"}

#: Command-line spelling of a conversion key, for diagnostics.
_FLAGS = {key: "--" + key.replace("_", "-") for key in CONVERSION_KEYS}
_FLAGS["link_properties"] = "--link-property"


def _resolve_settings(
    arguments: argparse.Namespace, table: "dict[str, object]"
) -> "tuple[dict[str, object], dict[str, str]]":
    """Merge the conversion settings: flag > TOML table > built-in default.

    Flags default to ``None``, so ``None`` means "not given"; every key resolves
    to a concrete value here. Also returns, per key, where the value came from,
    because a diagnostic has to name the flag or the TOML key the user actually
    wrote.
    """
    resolved: "dict[str, object]" = {}
    sources: "dict[str, str]" = {}
    for key in CONVERSION_KEYS:
        flag = getattr(arguments, _DESTS.get(key, key))
        if flag is not None:
            resolved[key], sources[key] = flag, "flag"
        elif key in table:
            resolved[key], sources[key] = table[key], "toml"
        else:
            resolved[key], sources[key] = _DEFAULTS[key], "default"

    tags = resolved["tags"]
    if isinstance(tags, str):  # comma-separated, from the flag
        resolved["tags"] = [tag.strip() for tag in tags.split(",") if tag.strip()]
    else:  # array from the TOML file, or the key is absent
        resolved["tags"] = _texts(tags)

    return resolved, sources


def _spell(key: str, sources: "dict[str, str]") -> str:
    """The key as the user wrote it: the flag, the TOML key, or the default."""
    source = sources.get(key)
    if source == "toml":
        return key
    if source == "default":
        return f"the default {key}"
    return _FLAGS[key]


def _pair_requirement(sources: "dict[str, str]", path: "Path | None") -> str:
    """Name the remote-url/commit pair the way the user actually spelled it.

    Either half can come from the TOML file, so naming only the flags would
    point at options that appear nowhere in the invocation.
    """
    # The half that is missing is named by the flag that would supply it --
    # that is the actionable spelling -- and the half that was given by however
    # the user gave it.
    names = [
        key if sources.get(key) == "toml" else _FLAGS[key]
        for key in ("remote_url", "commit")
    ]
    requirement = f"{names[0]} and {names[1]}"
    if "toml" in (sources.get("remote_url"), sources.get("commit")):
        requirement += f" (the bare names are {TABLE} keys in {path})"
    return requirement


def _extra_options(
    arguments: argparse.Namespace,
    section: "dict[str, object]",
    config_path: "Path | None",
) -> "list[str]":
    """Properties exported as fields: the section's ``extra_options`` plus the flag's.

    The flag adds to the file's list rather than replacing it: a repeatable
    flag reads as additive, and ``--no-config`` is the way to leave the file
    out. A flag name the section's list does not contain is exported all the
    same -- the flag may stand in for a build configured elsewhere -- but
    reported: the build registers exactly the section's list, so an import of
    the produced file drops every other field as an unknown key.
    """
    configured = _texts(section.get("extra_options", []))
    if arguments.extra_option is None:
        return configured
    added = [str(name) for name in arguments.extra_option]
    names = list(dict.fromkeys([*configured, *added], True))
    unlisted = [name for name in names if name not in configured]
    if unlisted and config_path is not None:
        _warn(
            f"--extra-option {', '.join(unlisted)}: not in the extra_options of "
            f"[{SECTION}] in {config_path}. The build registers only the fields "
            f"listed there, so a needimport of the produced file drops these; "
            f"list them in the file."
        )
    return names


def _build_needs(arguments: argparse.Namespace) -> int:
    section, config_path, error = _load_section(arguments)
    if error:
        print(error, file=sys.stderr)
        return 2

    settings, sources = _resolve_settings(
        arguments, dict(needs_settings(section) or {})
    )

    # The loader already rejects a file whose build.needs.need_type disagrees
    # with case's type. A --need-type flag (or the built-in default) is not in
    # the file, so the merged value has to be checked here as well, or the
    # converter writes needs of a type the build does not register. As in the
    # loader, a side that is not set is compared at its default: a file that
    # leaves case alone configures the build with the default type. Without a
    # file the rule has nothing to hold against, and the output depends on
    # the arguments alone.
    if config_path is not None:
        case_type = case_need_type(section)
        if settings["need_type"] != (case_type or DEFAULT_NEED_TYPE):
            build_side = (
                f"[{SECTION}] case's type is {case_type!r}"
                if case_type is not None
                else f"[{SECTION}] does not set case, so the build's test-case "
                f"type is the default {DEFAULT_NEED_TYPE!r},"
            )
            print(
                f"error: {_spell('need_type', sources)} is "
                f"{settings['need_type']!r} but {build_side} in {config_path}. "
                f"Both name the need type of a test case -- need_type for this "
                f"converter, case for the Sphinx build -- so they must agree.",
                file=sys.stderr,
            )
            return 2

    try:
        link_properties = _parse_link_properties(settings["link_properties"])
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    problem = check_url_pattern(str(settings["url_pattern"]))
    if problem is not None:
        # Checked before any report is read: str.format would otherwise fail
        # on the first case that carries a file, as a traceback.
        print(
            f"error: {_spell('url_pattern', sources)} {settings['url_pattern']!r}: "
            f"{problem}",
            file=sys.stderr,
        )
        return 2

    if bool(settings["remote_url"]) != bool(settings["commit"]):
        print(
            f"error: {_pair_requirement(sources, config_path)} must be given "
            f"together; without both, no source URL can be synthesized.",
            file=sys.stderr,
        )
        return 2

    reports: "list[Report]" = []
    for name in arguments.files:
        path = Path(name)
        if not path.is_file():
            print(f"error: no such file: {path}", file=sys.stderr)
            return 1
        try:
            # The parser is not typed yet (#114), so both calls are
            # untyped to mypy; nothing to fix from this side.
            parsed = JUnitParser(str(path)).parse()  # type: ignore[no-untyped-call]
        except Exception as error:  # noqa: BLE001 - report, never traceback
            print(f"error: {path}: {error}", file=sys.stderr)
            return 1
        _warn_about_empty_report(path, parsed)
        _warn_about_absent_source_lines(path, parsed)
        # The path as given, like the build records the path given to its
        # directives; it is a label for the report, not something resolved.
        reports.append((str(path), parsed))

    try:
        payload = build_needs_file(
            reports,
            project=_text(settings["project"]),
            version=_text(settings["version"]),
            need_type=_text(settings["need_type"]),
            tags=_texts(settings["tags"]),
            link_properties=link_properties,
            base_url=normalise_remote_url(_text(settings["remote_url"])),
            commit=_text(settings["commit"]),
            url_pattern=_text(settings["url_pattern"]),
            # The renameable field names and the accepted extra fields come
            # from the same section the build reads, so an imported need has
            # the shape of a local one.
            fields=field_names(section),
            extra_options=_extra_options(arguments, section, config_path),
            warn=_warn,
        )
    except ValueError as error:  # duplicate test cases across the inputs
        print(f"error: {error}", file=sys.stderr)
        return 2

    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Sorted keys and a fixed indent keep the output byte-stable across runs.
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


def main(argv: "list[str] | None" = None) -> int:
    """Entry point. Returns a process exit code instead of raising."""
    arguments = _build_parser().parse_args(argv)
    if arguments.command == "build" and arguments.artifact == "needs":
        return _build_needs(arguments)
    return 2  # pragma: no cover - argparse rejects unknown commands


if __name__ == "__main__":
    sys.exit(main())
