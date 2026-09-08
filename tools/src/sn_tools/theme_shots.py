"""Screenshot the needtable examples out of the theme docs builds, light and dark.

sphinx-needs ships CSS that has to look right in five themes -- furo, alabaster,
sphinx-immaterial, pydata-sphinx-theme and sphinx_rtd_theme -- each of which the docs can be
built against (``poe docs-needs``, ``docs-needs-alabaster``, ``docs-needs-im``,
``docs-needs-pds``, ``docs-needs-rtd``; each writes ``docs/_build/html/<theme>/``). Whether
that CSS *integrates* with a theme is a judgement nobody can make from a diff, and re-making
it by hand for five themes x two colour schemes x a handful of widget states is thirty
screenshots somebody has to take the same way twice. So this takes them.

It screenshots **existing** builds and never runs sphinx: the builds are ~2 minutes each and
making them a dependency would put ten minutes in front of every re-shoot. ``poe
docs-needs-themes`` is the task that produces them, so the recipe is two commands::

    uv run poe docs-needs-themes      # ~10 min, the five builds one after another
    uv run poe docs-needs-shots       # seconds per theme

What comes out is ``<out>/<theme>/<mode>/<label>.png``, a ``manifest.json`` and a
self-contained ``index.html`` gallery. With ``--compare <other out dir>`` the gallery puts a
BEFORE next to every AFTER, which is what makes it a review instrument rather than an album:
shoot the docs on master, shoot them on the branch with ``--compare``, and the regression is
the pair that stopped matching.

Four decisions in here are load-bearing, and each was made because the obvious alternative
fails on this repository's actual DOM:

* **The pages are served over HTTP, not opened as ``file://``.** Chromium gives every
  ``file://`` document an opaque origin, so anything a theme loads as an ES module -- and
  anything at all that a page ``fetch``es -- fails with a CORS error that has nothing to do
  with the CSS under review. A ``ThreadingHTTPServer`` on a random port costs nothing and
  makes the console-error list mean what it says.

* **A widget is located by its TABLE and photographed by its WRAPPER.** The wrapper is created
  by JavaScript at load time and its class differs between the DataTables DOM
  (``div.dataTables_wrapper``) and an enhancer that replaces it (``div.needstable``), so
  neither can be the thing that is searched for. ``table.NEEDS_DATATABLES`` is in the built
  HTML either way; ``closest()`` from there finds whichever wrapper this build has, and falls
  back to the table itself so a build whose JavaScript never ran still shoots. Which wrapper
  fired is recorded -- when a comparison shows a widget change, that is the first thing a
  reviewer wants to know.

* **Interactions are lists of candidate selectors, not one selector.** "Click the second
  column's sort control" is a stable *intent* across DOMs; ``thead th:nth-child(2)`` (the whole
  header cell is the control in DataTables) and ``thead th:nth-child(2) button`` (a real button
  in a modern one) are not the same selector. The first candidate that resolves wins and is
  recorded, so a before/after gallery stays comparable even when the DOM underneath moved.

* **A theme with no dark mode is detected, not assumed.** alabaster and sphinx_rtd_theme
  ignore ``prefers-color-scheme``, so emulating it produces a "dark" shot byte-identical to the
  light one -- a third of the gallery being the same picture twice. The test is evidential
  rather than a hard-coded list of theme names: every shot's bytes, plus the sampled page
  background. Both unchanged means no dark mode, the duplicate files are removed, and the
  gallery says ``dark: n/a (theme has no dark mode)`` in their place.

Everything else is a review aid, so **a page error is data, never a failure**: the exit code is
non-zero only when the instrument itself cannot run (no builds to shoot, no playwright, no
browser). Console errors are collected, printed as a summary line, and listed in both the
manifest and the gallery.

Usage::

    uv run poe docs-needs-shots
    uv run poe docs-needs-shots --themes furo,pydata_sphinx_theme --modes dark
    uv run --group js python tools/src/sn_tools/theme_shots.py \\
        --build-root /elsewhere/docs/_build/html --out /tmp/after --compare /tmp/before

playwright is imported **lazily**, inside the one function that drives a browser, so
``--help``, ``--list-targets`` and the whole of ``tools/tests/test_theme_shots.py`` run in an
environment that has never heard of it.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

#: The manifest and everything in it is JSON-shaped, and every consumer of it here is a
#: writer of HTML or a test. `Any` rather than a nest of TypedDicts: the shape is documented
#: by `write_manifest`'s output, and a schema would be a second place to keep it correct.
Json = dict[str, Any]

#: Where the five theme tasks write, relative to the repository root. Each of them ends in a
#: directory named for its `DOCS_THEME`, which is why one build root holds all five.
DEFAULT_BUILD_ROOT = Path("packages/sphinx-needs/docs/_build/html")

#: Beside the builds rather than inside one: `<build-root>/shots` would be served by the same
#: HTTP server and swept away by `docs-needs-clean`.
DEFAULT_OUT = Path("packages/sphinx-needs/docs/_build/shots")

#: The tasks that produce the builds this reads, named in the "nothing to shoot" message and
#: used to order the gallery. In task order.
BUILD_TASKS = (
    ("furo", "docs-needs"),
    ("alabaster", "docs-needs-alabaster"),
    ("sphinx_immaterial", "docs-needs-im"),
    ("pydata_sphinx_theme", "docs-needs-pds"),
    ("sphinx_rtd_theme", "docs-needs-rtd"),
)

#: A directory under the build root is a theme build if it has this in it. `_static`,
#: `.doctrees` and this instrument's own output can be siblings of the theme directories, so
#: "is a directory" is not enough.
THEME_MARKER = "index.html"

MODES = ("light", "dark")

#: The page every default target is on.
NEEDTABLE_PAGE = "directives/needtable.html"

#: What is in the BUILT HTML for every needtable widget, in every build, whatever JavaScript
#: later does to it. The search always starts here.
WIDGET_TABLE = "table.NEEDS_DATATABLES"

#: `closest()` candidates, in preference order: the DataTables wrapper as master builds it,
#: then an enhancer's. Neither is in the built HTML -- both are created at load time -- so
#: this is resolved in the browser, per shot, and the winner is recorded.
WIDGET_WRAPPERS = ("div.dataTables_wrapper", "div.needstable")

#: "The second column's header control, whatever it is." DataTables makes the whole `<th>` the
#: control and marks it `.sorting`; a DOM with a real button puts one inside the cell. Most
#: specific first, so a button is preferred to the cell that contains it.
SORT_CONTROLS = (
    "thead th:nth-child(2) button",
    "thead th:nth-child(2) [role='button']",
    "thead th:nth-child(2) a",
    "thead th:nth-child(2)",
)

#: "The widget's search input, whatever it is." DataTables wraps it in `.dataTables_filter`;
#: anything else is likely to type it as a search input or give it a class of its own.
SEARCH_INPUTS = (
    "div.dataTables_filter input",
    ".needstable__search input",
    "input[type='search']",
    "input[type='text']",
)

#: Typed into the search input for the `filtered` shot, and it is chosen rather than obvious.
#: The shot has to be recognisably *filtered*: `spec` matches 23 of the first table's 225 rows
#: on master, which moves the first visible row (`ACT_ANALYSIS` -> `CON_SPEC_1`), leaves the
#: body a full page so the row CSS is still what is being looked at, and shortens the
#: pagination. A string matching everything on page one -- `ACT` does, the table being sorted
#: by id -- produces a shot indistinguishable from a broken filter, and one matching a handful
#: produces an empty widget. `--filter-text` overrides it.
DEFAULT_FILTER_TEXT = "spec"


@dataclass(frozen=True)
class Interaction:
    """One declarative act on a widget, said so that two different DOMs can satisfy it.

    `selectors` are candidates searched **inside the resolved widget**, most specific first;
    the first that resolves is used, and recorded. `kind` is `click` or `fill`.
    """

    kind: str
    selectors: tuple[str, ...]
    text: str | None = None


@dataclass(frozen=True)
class Target:
    """One screenshot: where to look, what to photograph, and what to do to it first."""

    label: str
    page: str
    #: A CSS selector for the section to search inside, or None for the whole document. This
    #: is how "the widget in the #style-row example section" is said without naming an element
    #: that a theme or a rewrite might rename.
    scope: str | None = None
    #: The element to find (inside `scope`). The FIRST match wins -- "the first widget on the
    #: page" is a target, not an accident.
    element: str = WIDGET_TABLE
    #: `closest()` candidates for the wrapper actually photographed, in preference order.
    wrappers: tuple[str, ...] = ()
    interaction: Interaction | None = None
    #: True for the whole-page shot: photograph the viewport rather than an element.
    viewport: bool = False
    help: str = ""


DEFAULT_TARGETS: tuple[Target, ...] = (
    Target(
        label="first",
        page=NEEDTABLE_PAGE,
        wrappers=WIDGET_WRAPPERS,
        help="the first needtable widget on the page, untouched",
    ),
    Target(
        label="style-row",
        page=NEEDTABLE_PAGE,
        # the section's own id, which sphinx derives from the `style_row` heading; the
        # `needtable_style_row` label above it becomes a bare anchor, not the section id
        scope="section#style-row",
        wrappers=WIDGET_WRAPPERS,
        help="the widget in the style_row example, whose rows carry theme-fighting colours",
    ),
    Target(
        label="sorted",
        page=NEEDTABLE_PAGE,
        wrappers=WIDGET_WRAPPERS,
        interaction=Interaction("click", SORT_CONTROLS),
        help="the first widget after clicking the second column's sort control",
    ),
    Target(
        label="filtered",
        page=NEEDTABLE_PAGE,
        wrappers=WIDGET_WRAPPERS,
        interaction=Interaction("fill", SEARCH_INPUTS),
        help="the first widget after typing into its search input",
    ),
    Target(
        label="full",
        page=NEEDTABLE_PAGE,
        element="body",
        viewport=True,
        help="the whole page above the fold, so the theme's own chrome is visible",
    ),
)


# --- pure resolution, so the tests need no browser -----------------------------------------
# Everything a browser is needed for arrives as a one-line callable. That is not test
# scaffolding for its own sake: the selection rules ARE the contract this instrument makes
# with two different DOMs, and a rule that can only be exercised by launching chromium at a
# two-minute sphinx build is a rule nobody checks.


def resolve_selector(
    candidates: Sequence[str], exists: Callable[[str], bool]
) -> str | None:
    """The first candidate that resolves, or None. `exists` answers "is there one of these?"."""
    for candidate in candidates:
        if exists(candidate):
            return candidate
    return None


def closest_wrapper(
    wrappers: Sequence[str], has_ancestor: Callable[[str], bool]
) -> str | None:
    """The first wrapper the element sits inside, or None -- then the element itself is shot.

    `has_ancestor` is `el.closest(selector) !== null` in the browser. None is a legitimate
    answer rather than a failure: a build whose JavaScript did not run (or has none) still has
    a table, and a photograph of the bare table is exactly the right evidence for that.
    """
    return resolve_selector(wrappers, has_ancestor)


def scoped(scope: str | None, element: str) -> str:
    """The CSS the page is actually queried with."""
    return element if scope is None else f"{scope} {element}"


def select_targets(
    names: Sequence[str] | None, targets: Sequence[Target] = DEFAULT_TARGETS
) -> list[Target]:
    """`--targets` resolved against the table above, in the order the caller asked for.

    An unknown label is a usage error naming what there is; a silent skip would produce a
    gallery with a column missing and nothing to say why.
    """
    if names is None:
        return list(targets)
    by_label = {target.label: target for target in targets}
    unknown = [name for name in names if name not in by_label]
    if unknown:
        raise SystemExit(
            f"error: no such target: {', '.join(unknown)}. "
            f"Known targets: {', '.join(by_label)}"
        )
    return [by_label[name] for name in names]


def discover_themes(
    build_root: Path, requested: Sequence[str] | None
) -> tuple[list[str], list[str]]:
    """`(present, missing)`. With no `--themes`, every theme build under the root, sorted.

    A requested theme that was never built is **reported and skipped**, never an error: the
    normal way to use this is to shoot whatever builds a machine happens to have, and a
    reviewer looking at four themes because the fifth build was skipped is better served by a
    gallery plus a note than by no gallery at all.
    """

    def is_build(name: str) -> bool:
        return (build_root / name / THEME_MARKER).is_file()

    if requested is None:
        entries = sorted(build_root.iterdir()) if build_root.is_dir() else []
        return [
            path.name for path in entries if path.is_dir() and is_build(path.name)
        ], []
    present = [name for name in requested if is_build(name)]
    missing = [name for name in requested if not is_build(name)]
    return present, missing


def theme_order(themes: Sequence[str]) -> list[str]:
    """The five known themes in task order first, then anything else alphabetically."""
    rank = {name: index for index, (name, _) in enumerate(BUILD_TASKS)}
    return sorted(themes, key=lambda name: (rank.get(name, len(rank)), name))


# --- what "is this actually dark?" means ---------------------------------------------------


def parse_rgb(colour: str | None) -> tuple[int, int, int] | None:
    """`rgb(r, g, b)` / `rgba(r, g, b, a)` as integers, or None for anything else."""
    if not colour:
        return None
    numbers = re.findall(r"[\d.]+", colour)
    if len(numbers) < 3:
        return None
    try:
        red, green, blue = (int(float(value)) for value in numbers[:3])
    except ValueError:
        return None
    return red, green, blue


def is_dark(colour: str | None) -> bool | None:
    """Whether a sampled background reads as dark. None when it could not be parsed.

    Relative luminance with the sRGB coefficients, thresholded at the midpoint. This is the
    check behind "verify each dark shot IS dark": furo, pydata-sphinx-theme and
    sphinx-immaterial all honour `prefers-color-scheme`, and a dark gallery full of light
    screenshots -- which is what a theme upgrade that dropped the media query would produce --
    is otherwise invisible in a page of thumbnails.
    """
    parsed = parse_rgb(colour)
    if parsed is None:
        return None
    red, green, blue = parsed
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255 < 0.5


def dark_verdict(light: Json, dark: Json) -> tuple[bool, str, list[str]]:
    """Does this theme have a dark mode? `(supported, reason, labels that came out identical)`.

    TWO signals, and both have to say "nothing changed" before a theme is called dark-less,
    because either alone can lie. Byte equality alone would call a theme dark-less if a build
    happened to render identically for some other reason; a background sample alone would miss
    a theme that darkens its content area and not its page. Together they are the observable
    difference between "the emulation did nothing" and "the theme responded".
    """
    light_shots = {shot["label"]: shot for shot in light.get("shots", [])}
    dark_shots = {shot["label"]: shot for shot in dark.get("shots", [])}
    shared = [label for label in light_shots if label in dark_shots]
    identical = [
        label for label in shared if light_shots[label].get("sha") == dark_shots[label].get("sha")
    ]
    background_light = light.get("background")
    background_dark = dark.get("background")
    if not shared:
        return False, "no shots were captured in dark mode", identical
    if len(identical) == len(shared) and background_light == background_dark:
        return (
            False,
            "every dark shot is byte-identical to its light counterpart and the page "
            f"background is unchanged ({background_light})",
            identical,
        )
    if background_light != background_dark:
        reason = f"the page background moved from {background_light} to {background_dark}"
    else:
        reason = f"{len(shared) - len(identical)} of {len(shared)} shots changed"
    return True, reason, identical


def sha256_of(path: Path) -> str:
    """The shot's bytes, as one comparable value. Comparing these IS the byte comparison."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- where the build came from -------------------------------------------------------------


def built_version(build_root: Path, theme: str) -> str | None:
    """The sphinx-needs version, out of the build's own `documentation_options.js`.

    `docs/conf.py` sets `version = release = sphinx_needs.__version__`, and sphinx writes that
    into `_static/documentation_options.js` as `VERSION`. So this is derived from the built
    HTML rather than from the checkout doing the screenshotting -- which is the whole point
    when the build root is somebody else's worktree.
    """
    path = build_root / theme / "_static" / "documentation_options.js"
    if not path.is_file():
        return None
    match = re.search(
        r"VERSION:\s*['\"]([^'\"]+)['\"]", path.read_text(encoding="utf-8")
    )
    return match.group(1) if match else None


def git_sha(path: Path) -> str | None:
    """The HEAD of whatever checkout the build sits in, or None.

    Not derivable from the HTML -- nothing sphinx writes carries it -- but the build root's own
    checkout is the honest next best thing, and it is what tells two galleries apart. A linked
    worktree answers correctly; a directory that is in no checkout answers None.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return result.stdout.strip() or None


# --- serving the build ---------------------------------------------------------------------


class _QuietHandler(SimpleHTTPRequestHandler):
    """`SimpleHTTPRequestHandler` without a request log on stderr."""

    def log_message(self, format: str, *args: Any) -> None:
        return


@contextmanager
def serve(directory: Path) -> Iterator[str]:
    """Serve `directory` on a random loopback port for the life of the block.

    Not `file://`: see the module docstring. One server covers every theme, because the theme
    directories are siblings under the build root.
    """
    handler = functools.partial(_QuietHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# --- the browser half ----------------------------------------------------------------------

PLAYWRIGHT_MISSING = (
    "error: playwright is not installed in this environment.\n"
    "  uv sync --frozen --group js     # the driver (the root `js` dependency group)\n"
    "  uv run poe install-browser      # the browser itself, once per machine\n"
    "Or run `uv run poe docs-needs-shots`, which uses the default environment (`dev` "
    "includes `js`)."
)

BROWSER_MISSING = (
    "error: playwright has no browser to drive.\n"
    "  uv run poe install-browser      # fetches exactly the chromium this playwright pins\n"
    "A browser already on the machine is not necessarily the revision playwright looks for."
)

#: `el.closest(selector) !== null`, for `closest_wrapper`.
JS_HAS_ANCESTOR = "(el, selector) => el.closest(selector) !== null"

#: The first non-transparent background walking up from `<body>`. A theme that paints the page
#: on `<html>` and leaves `<body>` transparent is the common case for exactly the themes whose
#: dark mode matters, so stopping at `<body>` would sample nothing.
JS_PAGE_BACKGROUND = """() => {
  let el = document.body;
  while (el) {
    const colour = getComputedStyle(el).backgroundColor;
    if (colour && colour !== 'transparent' && !/^rgba\\(0,\\s*0,\\s*0,\\s*0\\)$/.test(colour)) {
      return colour;
    }
    el = el.parentElement;
  }
  return null;
}"""

#: Visible data rows, and the first one's text. Cheap evidence that an interaction did
#: something: a `filtered` shot whose row count never moved is a broken selector, and a
#: screenshot alone cannot say so.
JS_ROW_EVIDENCE = """(el) => {
  const rows = Array.from(el.querySelectorAll('tbody tr'))
    .filter((row) => row.offsetParent !== null);
  const first = rows[0];
  return {
    rows: rows.length,
    first: first ? first.innerText.replace(/\\s+/g, ' ').trim().slice(0, 90) : null,
  };
}"""


@dataclass
class PageLog:
    """Console errors and uncaught exceptions from one page, deduplicated."""

    entries: list[dict[str, str]] = field(default_factory=list)

    def add(self, kind: str, text: str) -> None:
        record = {"kind": kind, "text": " ".join(text.split())[:400]}
        if record not in self.entries:
            self.entries.append(record)


def _import_playwright() -> Any:
    """Imported here and nowhere else, so `--help` and the tests never need the driver."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(PLAYWRIGHT_MISSING) from None
    return sync_playwright


def capture(
    *,
    build_root: Path,
    out: Path,
    themes: Sequence[str],
    targets: Sequence[Target],
    modes: Sequence[str],
    viewport: tuple[int, int],
    filter_text: str,
    settle_ms: int,
) -> Json:
    """Drive the browser over every theme x mode x target, and return the manifest."""
    sync_playwright = _import_playwright()
    width, height = viewport
    version = next(
        (v for theme in themes if (v := built_version(build_root, theme))), None
    )
    themes_entry: Json = {}
    manifest: Json = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "build_root": str(build_root),
        "out": str(out),
        "viewport": {"width": width, "height": height},
        "modes": list(modes),
        "filter_text": filter_text,
        "targets": [
            {"label": target.label, "page": target.page, "help": target.help}
            for target in targets
        ],
        "source": {
            "sphinx_needs_version": version,
            "git_sha": git_sha(build_root),
        },
        "themes": themes_entry,
    }

    with serve(build_root) as base_url, sync_playwright() as driver:
        try:
            browser = driver.chromium.launch()
        except Exception as error:
            if "Executable doesn't exist" in str(error):
                raise SystemExit(BROWSER_MISSING) from None
            raise
        try:
            for theme in theme_order(themes):
                modes_entry: Json = {}
                theme_entry: Json = {"modes": modes_entry}
                themes_entry[theme] = theme_entry
                for mode in modes:
                    context = browser.new_context(
                        viewport={"width": width, "height": height},
                        color_scheme=mode,
                        # the shots are for a reviewer's eye, not for pixel diffing across
                        # machines, and 1x keeps thirty PNGs to a few MB
                        device_scale_factor=1,
                    )
                    try:
                        modes_entry[mode] = _capture_mode(
                            context=context,
                            base_url=base_url,
                            theme=theme,
                            mode=mode,
                            out=out,
                            targets=targets,
                            filter_text=filter_text,
                            settle_ms=settle_ms,
                        )
                    finally:
                        context.close()
                finish_dark(out, theme, theme_entry)
        finally:
            browser.close()
    return manifest


def _capture_mode(
    *,
    context: Any,
    base_url: str,
    theme: str,
    mode: str,
    out: Path,
    targets: Sequence[Target],
    filter_text: str,
    settle_ms: int,
) -> Json:
    """Every target for one theme in one colour scheme, on one page object."""
    log = PageLog()
    page = context.new_page()
    page.on("pageerror", lambda error: log.add("pageerror", str(error)))
    page.on(
        "console",
        lambda message: log.add("console.error", message.text)
        if message.type == "error"
        else None,
    )
    directory = out / theme / mode
    directory.mkdir(parents=True, exist_ok=True)
    shots: list[Json] = []
    background: str | None = None
    loaded: str | None = None
    dirty = False
    try:
        for target in targets:
            url = f"{base_url}/{theme}/{target.page}"
            # A load per target would be tidier but doubles the run; one is only actually
            # needed when the page changes or the previous target left the DOM interacted-with
            if loaded != url or dirty:
                _load(page, url, settle_ms)
                loaded, dirty = url, False
                if background is None:
                    background = page.evaluate(JS_PAGE_BACKGROUND)
            shots.append(
                _capture_target(
                    page=page,
                    target=target,
                    directory=directory,
                    theme=theme,
                    mode=mode,
                    filter_text=filter_text,
                )
            )
            if target.interaction is not None:
                dirty = True
    finally:
        page.close()
    return {
        "background": background,
        "background_is_dark": is_dark(background),
        "console_errors": log.entries,
        "shots": shots,
    }


def _load(page: Any, url: str, settle_ms: int) -> None:
    """Navigate, and wait for the widget's JavaScript to have had its turn."""
    page.goto(url, wait_until="load")
    # neither wait is a precondition for a shot: a page that never goes idle, or that has no
    # needtable on it at all, is a thing this should photograph and report rather than skip
    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle", timeout=15000)
    with contextlib.suppress(Exception):
        page.wait_for_selector(WIDGET_TABLE, timeout=15000)
    # the enhancement is a `$(document).ready` handler on master, and will be something
    # similar on any replacement: neither fires an event this could wait for instead
    page.wait_for_timeout(settle_ms)


def _capture_target(
    *,
    page: Any,
    target: Target,
    directory: Path,
    theme: str,
    mode: str,
    filter_text: str,
) -> Json:
    """One screenshot, plus everything a reviewer needs in order to trust it."""
    path = directory / f"{target.label}.png"
    selector = scoped(target.scope, target.element)
    record: Json = {
        "label": target.label,
        "theme": theme,
        "mode": mode,
        "page": target.page,
        "file": f"{theme}/{mode}/{target.label}.png",
        "selector": selector,
    }
    handle = page.query_selector(selector)
    if handle is None:
        record["error"] = f"no element matched {selector!r}"
        return record

    if target.viewport:
        page.evaluate("() => window.scrollTo(0, 0)")
        page.screenshot(path=str(path), animations="disabled", caret="hide")
        record.update(bytes=path.stat().st_size, sha=sha256_of(path), wrapper=None)
        return record

    wrapper = closest_wrapper(
        target.wrappers,
        lambda candidate: bool(handle.evaluate(JS_HAS_ANCESTOR, candidate)),
    )
    record["wrapper"] = wrapper
    element = handle
    if wrapper is not None:
        found = handle.evaluate_handle(
            "(el, selector) => el.closest(selector)", wrapper
        ).as_element()
        if found is not None:
            element = found

    if target.interaction is not None:
        record["interaction"] = _interact(
            page, element, target.interaction, filter_text, record
        )

    element.scroll_into_view_if_needed()
    element.screenshot(path=str(path), animations="disabled", caret="hide")
    record.update(bytes=path.stat().st_size, sha=sha256_of(path))
    return record


def _interact(
    page: Any,
    element: Any,
    interaction: Interaction,
    filter_text: str,
    record: Json,
) -> Json:
    """Run one declarative interaction; record which selector fired and what changed."""
    selector = resolve_selector(
        interaction.selectors,
        lambda candidate: element.query_selector(candidate) is not None,
    )
    result: Json = {
        "kind": interaction.kind,
        "selector": selector,
        "candidates": list(interaction.selectors),
        "before": element.evaluate(JS_ROW_EVIDENCE),
    }
    if selector is None:
        result["error"] = "none of the candidate selectors resolved"
        record["error"] = f"no {interaction.kind} control found in the widget"
        return result
    control = element.query_selector(selector)
    if interaction.kind == "click":
        control.click()
    else:
        text = interaction.text if interaction.text is not None else filter_text
        result["text"] = text
        control.fill(text)
        # DataTables filters on keyup; anything else will listen for `input`. `fill` fires
        # `input` but no key events, so both are dispatched
        control.evaluate(
            "(el) => el.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}))"
        )
        # a blinking caret in the shot is noise, and it would also make the light/dark byte
        # comparison that detects a theme with no dark mode flap
        control.evaluate("(el) => el.blur()")
    page.wait_for_timeout(600)
    result["after"] = element.evaluate(JS_ROW_EVIDENCE)
    return result


def finish_dark(out: Path, theme: str, entry: Json) -> None:
    """Decide whether this theme has a dark mode; drop the duplicate shots if it has not."""
    modes = entry.get("modes", {})
    light, dark = modes.get("light"), modes.get("dark")
    if light is None or dark is None:
        return
    supported, reason, identical = dark_verdict(light, dark)
    verdict: Json = {
        "supported": supported,
        "reason": reason,
        "identical": identical,
        "background_light": light.get("background"),
        "background_dark": dark.get("background"),
    }
    entry["dark"] = verdict
    if not supported:
        shutil.rmtree(out / theme / "dark", ignore_errors=True)
        verdict["files_removed"] = True


# --- the outputs ---------------------------------------------------------------------------


def import_before(compare: Path, out: Path) -> Json:
    """Copy a BEFORE run's images into `<out>/_before/` and return its manifest, rebased.

    The gallery has to survive being copied somewhere else -- which is most of the reason it is
    written at all -- so it cannot reach its images through a relative path that climbs out of
    its own directory. The before images are brought inside instead, and that manifest's `file`
    entries are rewritten to match.
    """
    path = compare / "manifest.json"
    if not path.is_file():
        raise SystemExit(f"error: --compare {compare} has no manifest.json in it")
    manifest: Json = json.loads(path.read_text(encoding="utf-8"))
    destination = out / "_before"
    shutil.rmtree(destination, ignore_errors=True)
    for theme, entry in manifest.get("themes", {}).items():
        for mode, mode_entry in entry.get("modes", {}).items():
            for shot in mode_entry.get("shots", []):
                relative = shot.get("file")
                if not relative or not (compare / relative).is_file():
                    shot["file"] = None
                    continue
                name = Path(relative).name
                target = destination / theme / mode / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(compare / relative, target)
                shot["file"] = f"_before/{theme}/{mode}/{name}"
    return manifest


GALLERY_CSS = """
:root { color-scheme: light dark; --bg:#fff; --fg:#1b1b1d; --muted:#5c5c66;
        --line:#d8d8e0; --card:#f6f6f9; --warn:#8a3b12; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#131316; --fg:#e6e6ea; --muted:#a0a0ac; --line:#33333c;
          --card:#1c1c21; --warn:#f0a879; }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 24px; background: var(--bg); color: var(--fg);
       font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
h1 { font-size: 20px; margin: 0 0 4px; }
h2 { font-size: 16px; margin: 32px 0 8px; }
p.meta { color: var(--muted); margin: 0 0 12px; }
table.gallery { border-collapse: collapse; width: 100%; table-layout: fixed; }
table.gallery th, table.gallery td { border: 1px solid var(--line); padding: 8px;
       vertical-align: top; }
table.gallery th { background: var(--card); text-align: left; font-size: 13px; }
th.rowhead { width: 150px; }
figure { margin: 0 0 10px; }
figcaption { color: var(--muted); font-size: 12px; margin-bottom: 4px; }
img { max-width: 100%; height: auto; display: block; border: 1px solid var(--line); }
.na { color: var(--muted); font-style: italic; }
.warn { color: var(--warn); }
ul.errors { margin: 4px 0 0 16px; padding: 0; font-size: 12px; color: var(--warn); }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
details { margin-top: 6px; }
summary { cursor: pointer; color: var(--muted); font-size: 12px; }
"""

DARK_NA = "dark: n/a (theme has no dark mode)"


def _figure(caption: str, shot: Json | None) -> str:
    """One image, or the reason there is not one."""
    label = html.escape(caption)
    if shot is None:
        return f"<figure><figcaption>{label}</figcaption><p class='na'>not captured</p></figure>"
    if shot.get("error") or not shot.get("file"):
        reason = html.escape(str(shot.get("error", "not captured")))
        return f"<figure><figcaption>{label}</figcaption><p class='warn'>{reason}</p></figure>"
    file = html.escape(str(shot["file"]))
    note = ""
    interaction = shot.get("interaction")
    if isinstance(interaction, dict):
        before = interaction.get("before") or {}
        after = interaction.get("after") or {}
        note = (
            f"<details><summary>{html.escape(str(interaction.get('selector')))}</summary>"
            f"<code>rows {before.get('rows')} &rarr; {after.get('rows')}<br>"
            f"first: {html.escape(str(after.get('first')))}</code></details>"
        )
    return (
        f"<figure><figcaption>{label}</figcaption>"
        f"<a href='{file}'><img src='{file}' alt='{label}'></a>{note}</figure>"
    )


def _shots_by_label(entry: Json | None) -> dict[str, Json]:
    if not entry:
        return {}
    return {str(shot["label"]): shot for shot in entry.get("shots", [])}


def _row_head(mode: str, mode_entry: Json | None) -> str:
    """The left-hand cell: the mode, the background it sampled, and anything it logged."""
    parts = [f"<th class='rowhead'>{mode}"]
    entry = mode_entry or {}
    background = entry.get("background")
    if background:
        flag = "dark" if entry.get("background_is_dark") else "light"
        parts.append(
            f"<br><code>{html.escape(str(background))}</code>"
            f"<br><span class='meta'>reads as {flag}</span>"
        )
    errors = entry.get("console_errors") or []
    if errors:
        parts.append(
            "<ul class='errors'>"
            + "".join(
                f"<li>{html.escape(str(error['kind']))}: {html.escape(str(error['text']))}</li>"
                for error in errors
            )
            + "</ul>"
        )
    return "".join(parts) + "</th>"


def write_gallery(manifest: Json, out: Path, before: Json | None = None) -> Path:
    """`<out>/index.html`: one row per theme x mode, one column per label. Self-contained."""
    labels = [str(target["label"]) for target in manifest.get("targets", [])]
    themes = manifest.get("themes", {})
    before_themes = (before or {}).get("themes", {})
    source = manifest.get("source", {})
    parts: list[str] = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>sphinx-needs needtable &mdash; theme shots</title>",
        f"<style>{GALLERY_CSS}</style></head><body>",
        "<h1>needtable widgets across the docs themes</h1>",
    ]
    viewport = manifest.get("viewport", {})
    meta = [
        f"generated {html.escape(str(manifest.get('generated')))}",
        f"sphinx-needs {html.escape(str(source.get('sphinx_needs_version')))}",
        f"build {html.escape(str(source.get('git_sha'))[:12])}",
        f"viewport {viewport.get('width')}x{viewport.get('height')}",
    ]
    if before is not None:
        before_source = before.get("source", {})
        meta.append(
            f"compared against {html.escape(str(before_source.get('git_sha'))[:12])} "
            f"(sphinx-needs {html.escape(str(before_source.get('sphinx_needs_version')))})"
        )
    parts.append(f"<p class='meta'>{' &middot; '.join(meta)}</p>")
    if before is not None:
        parts.append(
            "<p class='meta'>Every cell is <strong>before</strong> (the comparison run) "
            "above <strong>after</strong> (this run).</p>"
        )
    for target in manifest.get("targets", []):
        if target.get("help"):
            parts.append(
                f"<p class='meta'><code>{html.escape(str(target['label']))}</code> &mdash; "
                f"{html.escape(str(target['help']))}</p>"
            )

    extra = [name for name in before_themes if name not in themes]
    for theme in theme_order([*themes, *extra]):
        entry = themes.get(theme, {})
        before_entry = before_themes.get(theme, {}) if before else {}
        dark = entry.get("dark", {})
        no_dark = bool(dark) and not dark.get("supported")
        parts.append(f"<h2>{html.escape(theme)}</h2>")
        if no_dark:
            parts.append(
                f"<p class='meta'>{DARK_NA} &mdash; {html.escape(str(dark.get('reason')))}</p>"
            )
        parts.append("<table class='gallery'><tr><th class='rowhead'>mode</th>")
        parts.extend(f"<th>{html.escape(label)}</th>" for label in labels)
        parts.append("</tr>")
        for mode in MODES:
            mode_entry = entry.get("modes", {}).get(mode)
            before_mode = before_entry.get("modes", {}).get(mode) if before else None
            if mode == "dark" and no_dark:
                parts.append(
                    f"<tr><th class='rowhead'>dark</th>"
                    f"<td class='na' colspan='{len(labels)}'>{DARK_NA}</td></tr>"
                )
                continue
            if mode_entry is None and before_mode is None:
                continue
            parts.append("<tr>" + _row_head(mode, mode_entry))
            after_shots = _shots_by_label(mode_entry)
            before_shots = _shots_by_label(before_mode)
            for label in labels:
                cell = []
                if before is not None:
                    cell.append(_figure("before", before_shots.get(label)))
                cell.append(
                    _figure("after" if before is not None else label, after_shots.get(label))
                )
                parts.append("<td>" + "".join(cell) + "</td>")
            parts.append("</tr>")
        parts.append("</table>")

    parts.append("</body></html>")
    path = out / "index.html"
    path.write_text("".join(parts), encoding="utf-8")
    return path


def write_manifest(manifest: Json, out: Path) -> Path:
    path = out / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def console_summary(manifest: Json) -> list[str]:
    """One line per (theme, mode) that logged anything. Printed; never an exit code."""
    lines = []
    for theme, entry in manifest.get("themes", {}).items():
        for mode, mode_entry in entry.get("modes", {}).items():
            errors = mode_entry.get("console_errors") or []
            if errors:
                lines.append(
                    f"{theme}/{mode}: {len(errors)} console error(s) -- "
                    + "; ".join(error["text"][:120] for error in errors)
                )
    return lines


# --- CLI -----------------------------------------------------------------------------------


def default_root() -> Path:
    """The repository root, from this file's own location (the tooling is run by path)."""
    return Path(__file__).resolve().parents[3]


def parse_viewport(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)x(\d+)", value.strip())
    if match is None:
        raise argparse.ArgumentTypeError(f"expected WIDTHxHEIGHT, got {value!r}")
    return int(match.group(1)), int(match.group(2))


def comma_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="theme_shots.py",
        description=(
            "Screenshot the needtable examples out of EXISTING theme docs builds, light and "
            "dark, into a self-contained gallery. Build them first: `poe docs-needs-themes`."
        ),
    )
    parser.add_argument(
        "--root", type=Path, default=None, help="the repository root (default: this checkout)"
    )
    parser.add_argument(
        "--build-root",
        type=Path,
        default=None,
        help=f"where the theme builds are (default: <root>/{DEFAULT_BUILD_ROOT})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"where to write (default: <root>/{DEFAULT_OUT})",
    )
    parser.add_argument(
        "--themes",
        type=comma_list,
        default=None,
        help="comma-separated theme directory names (default: every build present)",
    )
    parser.add_argument(
        "--targets",
        type=comma_list,
        default=None,
        help="comma-separated target labels (default: all; see --list-targets)",
    )
    parser.add_argument(
        "--modes",
        type=comma_list,
        default=list(MODES),
        help="comma-separated colour schemes (default: light,dark)",
    )
    parser.add_argument(
        "--viewport",
        type=parse_viewport,
        default=(1280, 900),
        help="WIDTHxHEIGHT (default: 1280x900)",
    )
    parser.add_argument(
        "--compare",
        type=Path,
        default=None,
        help="another --out directory, shown as BEFORE beside this run",
    )
    parser.add_argument(
        "--filter-text",
        default=DEFAULT_FILTER_TEXT,
        help=f"typed into the search input for the `filtered` shot (default: {DEFAULT_FILTER_TEXT})",
    )
    parser.add_argument(
        "--settle",
        type=int,
        default=1200,
        dest="settle_ms",
        help="milliseconds to wait after load for the widget JavaScript (default: 1200)",
    )
    parser.add_argument(
        "--list-targets",
        action="store_true",
        help="print the targets and exit (needs no browser)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_targets:
        for target in DEFAULT_TARGETS:
            print(f"{target.label:12s} {target.page}  {target.help}")
        return 0

    root = args.root or default_root()
    build_root = (args.build_root or root / DEFAULT_BUILD_ROOT).resolve()
    out = (args.out or root / DEFAULT_OUT).resolve()
    targets = select_targets(args.targets)
    unknown = [mode for mode in args.modes if mode not in MODES]
    if unknown:
        raise SystemExit(
            f"error: no such mode: {', '.join(unknown)}. Known: {', '.join(MODES)}"
        )

    themes, missing = discover_themes(build_root, args.themes)
    tasks = dict(BUILD_TASKS)
    for name in missing:
        task = tasks.get(name)
        hint = f" (build it with `uv run poe {task}`)" if task else ""
        print(f"note: no build at {build_root / name} -- skipping{hint}", file=sys.stderr)
    if not themes:
        raise SystemExit(
            f"error: no theme build under {build_root}.\n"
            "Build them first -- `uv run poe docs-needs-themes`, or one at a time:\n"
            + "\n".join(f"  uv run poe {task:24s} # {name}" for name, task in BUILD_TASKS)
        )

    out.mkdir(parents=True, exist_ok=True)
    manifest = capture(
        build_root=build_root,
        out=out,
        themes=themes,
        targets=targets,
        modes=args.modes,
        viewport=args.viewport,
        filter_text=args.filter_text,
        settle_ms=args.settle_ms,
    )
    before = import_before(args.compare.resolve(), out) if args.compare else None
    write_manifest(manifest, out)
    gallery = write_gallery(manifest, out, before)

    for theme in theme_order(themes):
        entry = manifest["themes"][theme]
        dark = entry.get("dark")
        if dark is None:
            state = "dark not captured"
        elif dark.get("supported"):
            state = f"dark ok ({dark['background_dark']})"
        else:
            state = DARK_NA
        light = entry.get("modes", {}).get("light", {})
        print(f"{theme:22s} {state:44s} light background {light.get('background')}")
    for line in console_summary(manifest):
        print(f"console: {line}", file=sys.stderr)
    print(gallery)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
