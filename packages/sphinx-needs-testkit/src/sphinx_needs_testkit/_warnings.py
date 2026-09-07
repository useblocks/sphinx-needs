"""One normalisation of a build's warning stream, for every suite in this workspace.

Free functions rather than an application attribute, deliberately: they work over an app,
over a ``make_app`` caller's app, and over CAPTURED TEXT -- a real ``sphinx-build``
subprocess' stderr -- which is what the three suites here and sphinx-test-reports' three
subprocess tests between them need. The attribute this replaced (``app.warning_list``) was
snapshotted during fixture setup, so every assertion on it was an assertion about
application construction rather than about the build.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

#: A line STARTS a warning record when it carries a severity token, optionally behind the
#: location sphinx puts in front of it (``<path>: `` or ``<path>:<line>: ``). Everything
#: after such a line and before the next one is a continuation of that record.
#:
#: This is a HEURISTIC over what sphinx and docutils happen to emit, not a boundary either
#: of them defines, and it is worth knowing where it parts company from the truth: a
#: continuation line at column 0 that itself carries a severity token, or that merely reads
#: ``something: WARNING: …``, starts a new record. Every continuation this suite provokes is
#: indented -- docutils indents its literal blocks, sphinx-needs indents its violation
#: reports -- and the anchored ``^`` plus the non-greedy ``.*?:\s`` cannot reach a token
#: behind leading whitespace, so the heuristic holds here. It is a much narrower failure
#: than splitting on the substring ``"WARNING: "``, which is what this suite used to do:
#: that detached every location from its message, turned N located warnings into N+1
#: entries, erased the WARNING/ERROR distinction, and cut in half any message that merely
#: quoted the token anywhere at all.
_RECORD_START = re.compile(r"^(?:.*?:\s)?(?:WARNING|ERROR|SEVERE|CRITICAL):\s")


def _warning_stream_text(app: SphinxTestApp) -> str:
    """The raw warning stream of a built application.

    Raises rather than returning ``""`` when there is no readable stream. The attribute
    this API replaced set ``warning_list = None`` in that case, so an assertion on it
    FAILED; returning empty text instead would make :func:`assert_no_warnings` pass on an
    application whose warnings were never read, which is the one failure mode this whole
    change exists to remove.

    :param app: A built application.
    :return: Everything written to its warning stream.
    :raises TypeError: If neither ``_warning`` nor ``warning`` is a readable stream.
    """
    stream = getattr(app, "_warning", None)
    if not hasattr(stream, "getvalue"):
        stream = getattr(app, "warning", None)
    if not hasattr(stream, "getvalue"):
        builder = getattr(getattr(app, "builder", None), "name", "<unknown>")
        raise TypeError(
            f"the {builder!r} application has no readable warning stream: its `_warning` "
            f"attribute is {getattr(app, '_warning', None)!r}. Reading warnings from it "
            "would silently report none."
        )
    return str(stream.getvalue())


def build_warnings(
    source: SphinxTestApp | str, *, srcdir: str | Path | None = None
) -> list[str]:
    """Every warning a build emitted, normalised, one entry per RECORD.

    The one normalisation this suite has, in one place:

    * ANSI colour codes stripped (``strip_colors``);
    * the source directory rewritten to ``<srcdir>/``, so an assertion can name a file
      without knowing which temporary directory the fixture chose;
    * one entry per warning record, **including its location**, with a multi-line message
      kept whole rather than split into one entry per line -- see :data:`_RECORD_START` for
      what "record" means here and where the heuristic stops holding;
    * the severity token kept as it was emitted, so an ``ERROR`` never reads as a
      ``WARNING``;
    * anything before the first record DROPPED, so a capture that carries a build's status
      lines ("Running Sphinx v…", "build succeeded") reports the warnings in it and not the
      noise around them.

    Read AFTER the build, never snapshotted during fixture setup: the attribute this
    replaced was computed before the test called ``app.build()``, so every assertion on it
    was really an assertion about application construction.

    :param source: A built application, or captured text (a subprocess' ``stderr``).
    :param srcdir: The directory to rewrite to ``<srcdir>/``. Taken from the application
        when ``source`` is one; give it explicitly for captured text if the rewrite matters.
    :return: One string per warning record, in emission order.
    """
    if isinstance(source, str):
        text = source
    else:
        text = _warning_stream_text(source)
        if srcdir is None:
            srcdir = source.srcdir

    text = strip_colors(text)
    if srcdir is not None:
        # through `Path`, so a caller that passes a string with a trailing separator still
        # gets the rewrite (`app.srcdir` is a Path and never has one)
        root = str(Path(srcdir))
        for separator in (os.sep, "/"):
            text = text.replace(root + separator, "<srcdir>/")

    records: list[str] = []
    for line in text.splitlines():
        if _RECORD_START.match(line):
            records.append(line)
        elif records:
            records[-1] += "\n" + line
    return records


def assert_no_warnings(
    source: SphinxTestApp | str, *, srcdir: str | Path | None = None
) -> None:
    """Assert a build emitted nothing at all, and print everything it did emit if it did.

    :param source: A built application, or captured text.
    :param srcdir: Passed through to :func:`build_warnings`.
    """
    emitted = build_warnings(source, srcdir=srcdir)
    assert not emitted, "the build emitted {} warning(s):\n{}".format(
        len(emitted), "\n".join(emitted)
    )


def warning_count(
    source: SphinxTestApp | str,
    warning_type: str | None = None,
    *,
    srcdir: str | Path | None = None,
) -> int:
    """How many warnings a build emitted, optionally only those of one warning type.

    :param source: A built application, or captured text.
    :param warning_type: Count only records carrying exactly this warning type, matched
        against the ``[type]`` token sphinx emits -- brackets included, so
        ``"needs.variant"`` does not also count ``needs.variants``. It is one type, not a
        family: there is no prefix matching here, deliberately, because this codebase has
        live collisions (``needs.link_outgoing`` / ``needs.link_ref`` /
        ``needs.link_condition_failed``) that a prefix would silently merge.
    :param srcdir: Passed through to :func:`build_warnings`.
    :return: The number of matching warning records.
    """
    emitted = build_warnings(source, srcdir=srcdir)
    if warning_type is None:
        return len(emitted)
    token = f"[{warning_type}]"
    return sum(1 for record in emitted if token in record)
