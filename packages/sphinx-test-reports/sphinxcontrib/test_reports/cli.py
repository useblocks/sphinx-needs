"""``test-reports`` command line interface.

Converts test-result XML into needs.json *outside* Sphinx, so a build system can
schedule and cache the conversion and the documentation build only imports the
result. Nothing in the import chain of this module may import Sphinx; the test
suite asserts that.
"""

import argparse
import json
import sys
from pathlib import Path

from sphinxcontrib.test_reports.junitparser import JUnitParser
from sphinxcontrib.test_reports.needs_export import DEFAULT_VERSION, build_needs_file
from sphinxcontrib.test_reports.remote import DEFAULT_URL_PATTERN, normalise_remote_url


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="test-reports",
        description="Convert test-result XML into sphinx-needs data.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    convert = subcommands.add_parser(
        "convert",
        help="Convert one or more test-result XML files into needs.json.",
        description=(
            "Convert one or more test-result XML files into a needs.json that "
            "can be consumed with needimport or needs_external_needs."
        ),
    )
    convert.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="Test-result XML files (a build system passes these as a file list).",
    )
    convert.add_argument(
        "--output",
        "-o",
        required=True,
        metavar="PATH",
        help="Where to write the needs.json.",
    )
    convert.add_argument(
        "--project",
        default="",
        help="Project name recorded in the needs.json envelope.",
    )
    convert.add_argument(
        "--version",
        default=DEFAULT_VERSION,
        help=f"Version key in the envelope (default: {DEFAULT_VERSION}).",
    )
    convert.add_argument(
        "--need-type",
        default="testcase",
        help="Need type for each test case (default: testcase).",
    )
    convert.add_argument(
        "--tags",
        default="",
        help="Comma-separated tags applied to every created need.",
    )
    convert.add_argument(
        "--link-property",
        action="append",
        default=[],
        metavar="PROPERTY=LINK_FIELD",
        help=(
            "Promote an XML property to a link field, comma-splitting its value "
            "(repeatable), e.g. PartiallyVerifies=partially_verifies."
        ),
    )
    convert.add_argument(
        "--remote-url",
        default="",
        help="Repository URL used to synthesize source links; git remotes are accepted.",
    )
    convert.add_argument(
        "--commit",
        default="",
        help="Commit-ish the reports were produced from.",
    )
    convert.add_argument(
        "--url-pattern",
        default=DEFAULT_URL_PATTERN,
        help=f"Source-URL template (default: {DEFAULT_URL_PATTERN}).",
    )
    return parser


def _parse_link_properties(values: list[str]) -> dict[str, str]:
    mapping = {}
    for value in values:
        property_name, separator, link_field = value.partition("=")
        if not separator or not property_name.strip() or not link_field.strip():
            raise ValueError(
                f"--link-property expects PROPERTY=LINK_FIELD, got {value!r}"
            )
        mapping[property_name.strip()] = link_field.strip()
    return mapping


def _warn_about_absent_source_lines(path: Path, suites: list) -> None:
    """Report the most common cause of a missing source location.

    pytest emits ``file``/``line`` as ``<testcase>`` attributes only under
    ``junit_family = xunit1`` (or ``legacy``); its default ``xunit2`` filters
    them out, which silently costs the source location of every case.
    """
    cases = [case for suite in suites for case in suite.get("testcases", [])]
    if cases and all(case.get("line", -1) == -1 for case in cases):
        print(
            f"warning: {path}: no <testcase> carries a 'line' attribute, so no "
            "source location could be recorded. pytest emits file/line only "
            "with junit_family = xunit1 (or legacy); its default xunit2 drops "
            "them.",
            file=sys.stderr,
        )


def _convert(arguments: argparse.Namespace) -> int:
    try:
        link_properties = _parse_link_properties(list(arguments.link_property))
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if bool(arguments.remote_url) != bool(arguments.commit):
        print(
            "error: --remote-url and --commit must be given together; without "
            "both, no source URL can be synthesized.",
            file=sys.stderr,
        )
        return 2

    suites: list = []
    for name in arguments.files:
        path = Path(name)
        if not path.is_file():
            print(f"error: no such file: {path}", file=sys.stderr)
            return 1
        try:
            parsed = JUnitParser(str(path)).parse()
        except Exception as error:  # noqa: BLE001 - report, never traceback
            print(f"error: {path}: {error}", file=sys.stderr)
            return 1
        _warn_about_absent_source_lines(path, parsed)
        suites.extend(parsed)

    payload = build_needs_file(
        suites,
        project=arguments.project,
        version=arguments.version,
        need_type=arguments.need_type,
        tags=[tag.strip() for tag in arguments.tags.split(",") if tag.strip()],
        link_properties=link_properties,
        base_url=normalise_remote_url(arguments.remote_url),
        commit=arguments.commit,
        url_pattern=arguments.url_pattern,
    )

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
    if arguments.command == "convert":
        return _convert(arguments)
    return 2  # pragma: no cover - argparse rejects unknown commands


if __name__ == "__main__":
    sys.exit(main())
