"""Tests for the suite's own warning normalisation (``tests/conftest.py``).

Everything else in this suite exercises :func:`build_warnings` indirectly, through call
sites that all feed it well-formed input from a real build. That leaves the boundary
contract -- what starts a record, what continues one, and what is thrown away -- pinned by
nothing, which matters because the shared test layer is about to export this function to
other packages. These are constructed streams, so each rule is asserted on its own.
"""

import os
from pathlib import Path

import pytest

from tests.conftest import assert_no_warnings, build_warnings, warning_count

# in the platform's own form: `build_warnings` normalises the directory through `Path`, so
# on Windows a POSIX literal here would become `\tmp\build\src` and never match the stream
SRCDIR = str(Path("/tmp/build/src"))


def located(text: str) -> str:
    return text.replace("<S>", SRCDIR)


# --------------------------------------------------------------------------- record starts


def test_a_located_warning_is_one_record_with_its_location_attached() -> None:
    stream = located("<S>/index.rst:5: WARNING: first [needs.a]\n")
    assert build_warnings(stream, srcdir=SRCDIR) == [
        "<srcdir>/index.rst:5: WARNING: first [needs.a]"
    ]


def test_two_located_warnings_are_two_records() -> None:
    """The recon's first adversarial stream: the deleted helper returned three entries."""
    stream = located(
        "<S>/index.rst:5: WARNING: first message [needs.a]\n"
        "<S>/index.rst:9: WARNING: second message [needs.b]\n"
    )
    assert build_warnings(stream, srcdir=SRCDIR) == [
        "<srcdir>/index.rst:5: WARNING: first message [needs.a]",
        "<srcdir>/index.rst:9: WARNING: second message [needs.b]",
    ]


def test_an_error_stays_an_error() -> None:
    """The recon's second stream. The deleted helper rewrote ``ERROR:`` to ``WARNING:``."""
    stream = located(
        "<S>/index.rst:2: ERROR: boom [needs.x]\n<S>/index.rst:3: WARNING: mild [needs.y]\n"
    )
    assert build_warnings(stream, srcdir=SRCDIR) == [
        "<srcdir>/index.rst:2: ERROR: boom [needs.x]",
        "<srcdir>/index.rst:3: WARNING: mild [needs.y]",
    ]


def test_a_message_quoting_the_severity_token_is_not_cut_in_half() -> None:
    """The recon's third stream. The deleted helper split it into two entries."""
    stream = "WARNING: needs.json contains 'WARNING: nested' [needs.z]\n"
    assert build_warnings(stream) == [
        "WARNING: needs.json contains 'WARNING: nested' [needs.z]"
    ]


def test_an_unlocated_warning_is_one_record() -> None:
    """The recon's fourth stream, and the one shape the deleted helper got right."""
    assert build_warnings("WARNING: config problem [needs.config]\n") == [
        "WARNING: config problem [needs.config]"
    ]


def test_every_sphinx_severity_starts_a_record() -> None:
    """``SEVERE`` and ``CRITICAL`` are sphinx severities too; dropping them from the pattern
    would glue such a record onto its predecessor and stay green everywhere else."""
    stream = "WARNING: a\nSEVERE: b\nCRITICAL: c\nERROR: d\n"
    assert build_warnings(stream) == [
        "WARNING: a",
        "SEVERE: b",
        "CRITICAL: c",
        "ERROR: d",
    ]


def test_a_location_containing_a_space_still_starts_a_record() -> None:
    """A path with a space in it is a location like any other."""
    stream = "/tmp/my docs/index.rst:3: WARNING: x [needs.a]\n"
    assert build_warnings(stream) == ["/tmp/my docs/index.rst:3: WARNING: x [needs.a]"]


def test_a_windows_location_does_not_split_on_the_drive_letter() -> None:
    """``C:`` is not followed by whitespace, so the non-greedy prefix walks past it."""
    stream = "C:\\a\\b\\index.rst:12: WARNING: x [needs.a]\nC:\\a\\b\\index.rst:20: ERROR: y\n"
    assert build_warnings(stream) == [
        "C:\\a\\b\\index.rst:12: WARNING: x [needs.a]",
        "C:\\a\\b\\index.rst:20: ERROR: y",
    ]


def test_a_severity_token_with_no_trailing_space_does_not_start_a_record() -> None:
    """Sphinx always emits the space; nothing else may claim to be a record start."""
    assert build_warnings("WARNING:no space here\n") == []


# ----------------------------------------------------------------------- continuation lines


def test_a_multi_line_message_is_kept_whole() -> None:
    stream = located(
        "<S>/index.rst:1: WARNING: line one [needs.m]\n    continued\n    more\n"
    )
    assert build_warnings(stream, srcdir=SRCDIR) == [
        "<srcdir>/index.rst:1: WARNING: line one [needs.m]\n    continued\n    more"
    ]


def test_an_indented_severity_token_is_a_continuation_not_a_record() -> None:
    """The anchored ``^`` cannot reach a token behind leading whitespace."""
    stream = "WARNING: could not parse:\n  ERROR: nested token, indented [needs.x]\n"
    assert len(build_warnings(stream)) == 1


def test_a_blank_line_inside_a_record_stays_with_it() -> None:
    """docutils reports an unknown directive as a message, a blank line and a literal block."""
    stream = 'WARNING: Unknown directive type "nope".\n\n.. nope::\n   body\n'
    assert build_warnings(stream) == [
        'WARNING: Unknown directive type "nope".\n\n.. nope::\n   body'
    ]


# ------------------------------------------------------------------- everything else is noise


def test_status_lines_before_the_first_warning_are_not_a_record() -> None:
    """A ``sphinx-build`` capture is mostly status output; none of it is a warning."""
    stream = "Running Sphinx v9.0.0\nloading translations [en]... done\nbuilding [html]: ...\n"
    assert build_warnings(stream) == []
    assert_no_warnings(stream)


def test_a_trailing_summary_is_attached_to_nothing_when_there_is_no_warning() -> None:
    assert build_warnings("build succeeded.\n") == []


def test_noise_around_a_real_warning_leaves_exactly_one_record() -> None:
    stream = located(
        "Running Sphinx v9.0.0\n"
        "building [html]: targets for 1 source file\n"
        "<S>/index.rst:3: WARNING: real one [needs.a]\n"
    )
    assert build_warnings(stream, srcdir=SRCDIR) == [
        "<srcdir>/index.rst:3: WARNING: real one [needs.a]"
    ]


def test_an_empty_stream_has_no_records() -> None:
    assert build_warnings("") == []
    assert_no_warnings("")


# --------------------------------------------------------------------------- the srcdir rewrite


def test_a_srcdir_given_with_a_trailing_separator_still_rewrites() -> None:
    stream = located("<S>/index.rst:5: WARNING: x [needs.a]\n")
    assert build_warnings(stream, srcdir=SRCDIR + os.sep) == [
        "<srcdir>/index.rst:5: WARNING: x [needs.a]"
    ]


def test_no_srcdir_means_no_rewrite() -> None:
    stream = located("<S>/index.rst:5: WARNING: x [needs.a]\n")
    assert build_warnings(stream) == [f"{SRCDIR}/index.rst:5: WARNING: x [needs.a]"]


# ------------------------------------------------------------------------------ warning_count


def test_warning_count_counts_records() -> None:
    stream = "WARNING: a [needs.a]\nWARNING: b [needs.b]\n"
    assert warning_count(stream) == 2


def test_warning_count_matches_the_exact_type_not_a_prefix() -> None:
    """``needs.variant`` and ``needs.variants`` are both live types in this codebase."""
    stream = "WARNING: a [needs.variant]\nWARNING: b [needs.variants]\n"
    assert warning_count(stream, "needs.variant") == 1
    assert warning_count(stream, "needs.variants") == 1
    assert warning_count(stream, "needs.link") == 0


def test_warning_count_does_not_match_a_type_by_its_suffix() -> None:
    """``[needs.link]`` must not be found inside ``[x.needs.link]``: the match is the whole
    bracketed token, not its tail."""
    stream = "WARNING: a [x.needs.link]\nWARNING: b [needs.link]\n"
    assert warning_count(stream, "needs.link") == 1


# ------------------------------------------------------------------- a stream that is not one


class _NoStreamApp:
    """A stand-in for the case the deleted attribute was loud about."""

    _warning = True
    warning = True

    class builder:  # noqa: N801
        name = "latex"

    srcdir = Path("/tmp/build/src")


def test_an_application_with_no_readable_stream_raises_rather_than_reporting_none() -> (
    None
):
    with pytest.raises(TypeError, match=r"'latex' application has no readable warning"):
        build_warnings(_NoStreamApp())  # type: ignore[arg-type]
