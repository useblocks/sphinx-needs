"""`theme_shots.py` without a browser: the resolution rules, the writers, the dark verdict.

This instrument's job is to be re-runnable across two different DOMs -- the DataTables markup
master builds, and whatever replaces it -- so its contract is not "it takes a screenshot", it
is *which element it decides to photograph, and what it does to it first*. All of that is
decided by pure functions taking a one-line callable for the browser's part, and this module
exercises them with fakes: a chromium launch against a two-minute sphinx build is not a thing
anybody runs often enough for it to be a check.

Four of the tests below cover behaviour that only shows up on a real run, and each of them
would otherwise be discovered as a broken gallery hours later:

* **the wrapper fallback** -- the class of the widget wrapper differs between the two DOMs and
  is absent from the built HTML in both, so the search starts at the table and walks up. A
  build whose JavaScript never ran has neither wrapper, and must still produce a shot;
* **the dark verdict** -- alabaster and sphinx_rtd_theme ignore `prefers-color-scheme`, so
  emulating it yields a duplicate image. Two signals decide it, and the test pins that ONE
  changing is enough to call the theme dark-capable;
* **the `--compare` layout** -- before images are copied inside the output directory, because
  the gallery's whole point is to be copied somewhere else and a relative path that climbs out
  of it would arrive broken;
* **the missing-theme skip** -- a theme that was never built is a note, not an error.

Nothing here imports playwright, and one test asserts that it stays that way: the import is
lazy, and its failure message has to name both halves of the fix.
"""

from __future__ import annotations

import base64
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from sn_tools import theme_shots

pytestmark = pytest.mark.filterwarnings("error")

#: a real 1x1 PNG -- the writers only stat and hash it, but a file that is not an image would
#: make a failing gallery look like a passing one when opened by hand
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQ"
    "AAAABJRU5ErkJggg=="
)

LABELS = ("first", "style-row", "sorted", "filtered", "full")


def write_shots(
    out: Path, theme: str, mode: str, *, payload: bytes = PNG
) -> list[dict]:
    """`<out>/<theme>/<mode>/<label>.png` for every label, and the manifest entries for them."""
    directory = out / theme / mode
    directory.mkdir(parents=True, exist_ok=True)
    shots = []
    for label in LABELS:
        path = directory / f"{label}.png"
        path.write_bytes(payload)
        shots.append(
            {
                "label": label,
                "theme": theme,
                "mode": mode,
                "page": theme_shots.NEEDTABLE_PAGE,
                "file": f"{theme}/{mode}/{label}.png",
                "bytes": len(payload),
                "sha": theme_shots.sha256_of(path),
                "wrapper": None if label == "full" else "div.dataTables_wrapper",
                "viewport": label == "full",
            }
        )
    return shots


def fake_manifest(
    out: Path,
    themes: dict[str, dict[str, Any]],
    *,
    git_sha: str = "0123456789abcdef",
    version: str = "5.2.0",
) -> dict[str, Any]:
    """A manifest of the shape `capture()` returns, over files actually on disk.

    `themes` maps a theme name to `{"backgrounds": {mode: colour}, "errors": [...] }`.
    """
    entries: dict[str, Any] = {}
    for theme, options in themes.items():
        modes: dict[str, Any] = {}
        for mode, background in options["backgrounds"].items():
            modes[mode] = {
                "background": background,
                "background_is_dark": theme_shots.is_dark(background),
                "console_errors": options.get("errors", []) if mode == "light" else [],
                "shots": write_shots(out, theme, mode),
            }
        entry: dict[str, Any] = {"modes": modes}
        if "light" in modes and "dark" in modes:
            theme_shots.finish_dark(out, theme, entry)
        entries[theme] = entry
    return {
        "generated": "2026-09-08T00:00:00+00:00",
        "build_root": str(out.parent / "html"),
        "out": str(out),
        "viewport": {"width": 1280, "height": 900},
        "modes": ["light", "dark"],
        "filter_text": "spec",
        "targets": [
            {
                "label": label,
                "page": theme_shots.NEEDTABLE_PAGE,
                "help": f"the {label} shot",
            }
            for label in LABELS
        ],
        "source": {"sphinx_needs_version": version, "git_sha": git_sha},
        "themes": entries,
    }


# --- selector resolution: the contract with two DOMs ----------------------------------------


def test_resolve_selector_takes_the_first_that_exists():
    seen: list[str] = []

    def exists(candidate: str) -> bool:
        seen.append(candidate)
        return candidate == "thead th:nth-child(2)"

    assert (
        theme_shots.resolve_selector(theme_shots.SORT_CONTROLS, exists)
        == "thead th:nth-child(2)"
    )
    # every more specific candidate was tried first, and nothing after the winner was
    assert seen == list(theme_shots.SORT_CONTROLS)


def test_resolve_selector_prefers_a_real_button_to_the_header_cell():
    """The branch's DOM and master's both satisfy "the second column's sort control"."""
    both = {"thead th:nth-child(2) button", "thead th:nth-child(2)"}
    assert (
        theme_shots.resolve_selector(theme_shots.SORT_CONTROLS, both.__contains__)
        == "thead th:nth-child(2) button"
    )


def test_resolve_selector_returns_none_when_nothing_matches():
    assert theme_shots.resolve_selector(("a", "b"), lambda _: False) is None


@pytest.mark.parametrize(
    ("ancestors", "expected"),
    [
        # master: DataTables builds this wrapper at load time
        ({"div.dataTables_wrapper"}, "div.dataTables_wrapper"),
        # the enhancer that replaces it
        ({"div.needstable"}, "div.needstable"),
        # a page carrying both -- the preference order decides
        (
            {"div.dataTables_wrapper", "div.needstable"},
            "div.dataTables_wrapper",
        ),
        # JavaScript never ran: there is no wrapper, and the bare table is the right shot
        (set(), None),
    ],
)
def test_closest_wrapper(ancestors: set[str], expected: str | None):
    assert (
        theme_shots.closest_wrapper(theme_shots.WIDGET_WRAPPERS, ancestors.__contains__)
        == expected
    )


def test_scope_strategies_without_an_anchor_is_just_the_element():
    assert theme_shots.scope_strategies(None, "table.NEEDS_DATATABLES") == [
        ("selector", "table.NEEDS_DATATABLES")
    ]


def test_scope_strategies_copes_with_both_shapes_of_section():
    """sphinx puts the id on the section; sphinx-immaterial puts it on the heading."""
    assert theme_shots.scope_strategies("#style-row", "table.NEEDS_DATATABLES") == [
        # four of the five themes: the widget is a descendant of `<section id="style-row">`
        ("selector", "#style-row table.NEEDS_DATATABLES"),
        # sphinx-immaterial unwraps sections, so nothing is a descendant of the `<h3>` and
        # the widget has to be found by document order instead
        ("after", "#style-row"),
    ]


def test_default_targets_cover_the_documented_set():
    labels = [target.label for target in theme_shots.DEFAULT_TARGETS]
    assert labels == ["first", "style-row", "sorted", "filtered", "full"]
    by_label = {target.label: target for target in theme_shots.DEFAULT_TARGETS}
    # the two interaction states are the SAME widget as `first`, so they are comparable
    assert by_label["sorted"].anchor is None
    assert by_label["filtered"].anchor is None
    assert by_label["style-row"].anchor == "#style-row"
    # every widget target starts from the table that IS in the built HTML
    assert all(
        target.element == theme_shots.WIDGET_TABLE
        for target in theme_shots.DEFAULT_TARGETS
        if not target.viewport
    )
    assert by_label["full"].viewport is True


def test_select_targets_keeps_the_callers_order():
    chosen = theme_shots.select_targets(["filtered", "first"])
    assert [target.label for target in chosen] == ["filtered", "first"]


def test_select_targets_names_what_there_is():
    with pytest.raises(SystemExit) as error:
        theme_shots.select_targets(["frist"])
    assert "frist" in str(error.value)
    assert "style-row" in str(error.value)


# --- theme discovery ------------------------------------------------------------------------


def make_build(root: Path, theme: str, *, version: str | None = "5.2.0") -> None:
    directory = root / theme
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.html").write_text("<html></html>", encoding="utf-8")
    if version is not None:
        static = directory / "_static"
        static.mkdir(exist_ok=True)
        (static / "documentation_options.js").write_text(
            f"const DOCUMENTATION_OPTIONS = {{VERSION: '{version}', LANGUAGE: 'en'}};",
            encoding="utf-8",
        )


def test_discover_themes_finds_every_build_and_ignores_everything_else(tmp_path: Path):
    make_build(tmp_path, "furo")
    make_build(tmp_path, "alabaster")
    # siblings of the theme directories that are not builds
    (tmp_path / ".doctrees").mkdir()
    (tmp_path / "shots").mkdir()
    (tmp_path / "stray.txt").write_text("", encoding="utf-8")
    assert theme_shots.discover_themes(tmp_path, None) == (["alabaster", "furo"], [])


def test_discover_themes_reports_a_missing_theme_and_skips_it(tmp_path: Path):
    """A theme nobody built is a note, never an error -- see the module docstring."""
    make_build(tmp_path, "furo")
    present, missing = theme_shots.discover_themes(
        tmp_path, ["furo", "sphinx_rtd_theme"]
    )
    assert present == ["furo"]
    assert missing == ["sphinx_rtd_theme"]


def test_discover_themes_on_a_root_that_does_not_exist(tmp_path: Path):
    assert theme_shots.discover_themes(tmp_path / "nope", None) == ([], [])


def test_theme_order_is_task_order_then_the_rest():
    assert theme_shots.theme_order(
        ["zebra", "sphinx_rtd_theme", "alabaster", "furo"]
    ) == ["furo", "alabaster", "sphinx_rtd_theme", "zebra"]


def test_built_version_comes_from_the_build_not_the_checkout(tmp_path: Path):
    make_build(tmp_path, "furo", version="9.0.0")
    assert theme_shots.built_version(tmp_path, "furo") == "9.0.0"
    make_build(tmp_path, "alabaster", version=None)
    assert theme_shots.built_version(tmp_path, "alabaster") is None


# --- the dark verdict -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("colour", "expected"),
    [
        ("rgb(255, 255, 255)", False),
        ("rgb(19, 19, 22)", True),
        ("rgba(18, 18, 18, 1)", True),
        ("transparent", None),
        (None, None),
    ],
)
def test_is_dark(colour: str | None, expected: bool | None):
    assert theme_shots.is_dark(colour) is expected


def shot(label: str, sha: str, *, viewport: bool = False) -> dict[str, Any]:
    return {
        "label": label,
        "sha": sha,
        "file": f"x/{label}.png",
        "viewport": viewport,
    }


def test_dark_verdict_calls_a_theme_dark_less_only_when_both_signals_agree():
    light = {
        "background": "rgb(255, 255, 255)",
        "shots": [shot("first", "aa"), shot("full", "bb", viewport=True)],
    }
    dark = {
        "background": "rgb(255, 255, 255)",
        "shots": [shot("first", "aa"), shot("full", "bb", viewport=True)],
    }
    supported, reason, identical = theme_shots.dark_verdict(light, dark)
    assert supported is False
    assert "byte-identical" in reason
    # the whole-page shot is never one of the signals, so it is not one of the labels either
    assert identical == ["first"]


def test_dark_verdict_ignores_a_whole_page_shot_that_moved_on_its_own():
    """Measured on master: alabaster and rtd, whose code blocks are not the theme's doing."""
    light = {
        "background": "rgb(255, 255, 255)",
        "shots": [shot("first", "aa"), shot("full", "bb", viewport=True)],
    }
    dark = {
        "background": "rgb(255, 255, 255)",
        "shots": [shot("first", "aa"), shot("full", "ZZ", viewport=True)],
    }
    supported, reason, _ = theme_shots.dark_verdict(light, dark)
    assert supported is False
    # ... and the reader is told about it anyway
    assert "whole-page shot does differ" in reason


def test_dark_verdict_one_changed_widget_shot_is_enough():
    light = {"background": "rgb(255, 255, 255)", "shots": [shot("first", "aa")]}
    dark = {"background": "rgb(255, 255, 255)", "shots": [shot("first", "zz")]}
    supported, reason, identical = theme_shots.dark_verdict(light, dark)
    assert supported is True
    assert "1 of 1 widget shots changed" in reason
    assert identical == []


def test_dark_verdict_a_changed_background_is_enough():
    """A theme could in principle darken its page and not its widgets; that is still dark."""
    light = {"background": "rgb(255, 255, 255)", "shots": [shot("first", "aa")]}
    dark = {"background": "rgb(19, 19, 22)", "shots": [shot("first", "aa")]}
    supported, reason, _ = theme_shots.dark_verdict(light, dark)
    assert supported is True
    assert "rgb(19, 19, 22)" in reason


def test_finish_dark_removes_the_duplicate_images(tmp_path: Path):
    light_shots = write_shots(tmp_path, "alabaster", "light")
    dark_shots = write_shots(tmp_path, "alabaster", "dark")
    entry: dict[str, Any] = {
        "modes": {
            "light": {"background": "rgb(255, 255, 255)", "shots": light_shots},
            "dark": {"background": "rgb(255, 255, 255)", "shots": dark_shots},
        }
    }
    assert (tmp_path / "alabaster" / "dark").is_dir()
    theme_shots.finish_dark(tmp_path, "alabaster", entry)
    assert entry["dark"]["supported"] is False
    assert entry["dark"]["files_removed"] is True
    assert not (tmp_path / "alabaster" / "dark").exists()
    assert (tmp_path / "alabaster" / "light").is_dir()


def test_finish_dark_keeps_a_real_dark_mode(tmp_path: Path):
    light_shots = write_shots(tmp_path, "furo", "light")
    dark_shots = write_shots(tmp_path, "furo", "dark", payload=PNG + b"\x00")
    entry: dict[str, Any] = {
        "modes": {
            "light": {"background": "rgb(255, 255, 255)", "shots": light_shots},
            "dark": {"background": "rgb(19, 19, 22)", "shots": dark_shots},
        }
    }
    theme_shots.finish_dark(tmp_path, "furo", entry)
    assert entry["dark"]["supported"] is True
    assert (tmp_path / "furo" / "dark").is_dir()


# --- the writers ----------------------------------------------------------------------------


def test_manifest_and_gallery(tmp_path: Path):
    out = tmp_path / "after"
    out.mkdir()
    manifest = fake_manifest(
        out,
        {
            "furo": {
                "backgrounds": {
                    "light": "rgb(255, 255, 255)",
                    "dark": "rgb(19, 19, 22)",
                },
                "errors": [{"kind": "pageerror", "text": "$ is not defined"}],
            },
            "alabaster": {
                "backgrounds": {
                    "light": "rgb(255, 255, 255)",
                    "dark": "rgb(255, 255, 255)",
                }
            },
        },
    )
    # the two themes were given identical shot bytes, so only the backgrounds separate them
    assert manifest["themes"]["furo"]["dark"]["supported"] is True
    assert manifest["themes"]["alabaster"]["dark"]["supported"] is False

    theme_shots.write_manifest(manifest, out)
    written = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert written["source"]["sphinx_needs_version"] == "5.2.0"
    assert written["themes"]["furo"]["modes"]["light"]["shots"][0]["bytes"] == len(PNG)

    theme_shots.write_gallery(manifest, out)
    page = (out / "index.html").read_text(encoding="utf-8")
    # one column per label, one row per theme x mode
    for label in LABELS:
        assert f"<th>{label}</th>" in page
        assert f"furo/light/{label}.png" in page
        assert f"furo/dark/{label}.png" in page
    # the theme with no dark mode says so instead of showing the same picture twice
    assert theme_shots.DARK_NA in page
    assert "alabaster/dark/first.png" not in page
    assert "alabaster/light/first.png" in page
    # console errors reach the reader
    assert "$ is not defined" in page
    # self-contained: no external resource of any kind
    assert "http://" not in page and "https://" not in page
    assert "<style>" in page and "<link" not in page
    # the sampled background is on the page, and so is the verdict about it
    assert "rgb(19, 19, 22)" in page
    assert "reads as dark" in page


def test_gallery_escapes_what_a_page_logged(tmp_path: Path):
    out = tmp_path / "after"
    out.mkdir()
    manifest = fake_manifest(
        out,
        {
            "furo": {
                "backgrounds": {"light": "rgb(255, 255, 255)"},
                "errors": [{"kind": "console.error", "text": "<script>oops</script>"}],
            }
        },
    )
    theme_shots.write_gallery(manifest, out)
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "&lt;script&gt;oops&lt;/script&gt;" in page
    assert "<script>" not in page


def test_compare_layout_brings_the_before_images_inside(tmp_path: Path):
    before_dir = tmp_path / "before"
    before_dir.mkdir()
    before = fake_manifest(
        before_dir,
        {"furo": {"backgrounds": {"light": "rgb(255, 255, 255)"}}},
        git_sha="beef0000beef0000",
        version="5.1.0",
    )
    theme_shots.write_manifest(before, before_dir)

    after_dir = tmp_path / "after"
    after_dir.mkdir()
    after = fake_manifest(
        after_dir,
        {"furo": {"backgrounds": {"light": "rgb(255, 255, 255)"}}},
        git_sha="cafe0000cafe0000",
    )
    rebased = theme_shots.import_before(before_dir, after_dir)
    theme_shots.write_gallery(after, after_dir, rebased)
    page = (after_dir / "index.html").read_text(encoding="utf-8")

    # the before images live under the AFTER directory, so the gallery survives being copied
    for label in LABELS:
        copied = after_dir / "_before" / "furo" / "light" / f"{label}.png"
        assert copied.is_file()
        assert f"_before/furo/light/{label}.png" in page
        assert f"furo/light/{label}.png" in page
    assert "<figcaption>before</figcaption>" in page
    assert "<figcaption>after</figcaption>" in page
    # nothing climbs out of the output directory
    assert "../" not in page
    # both revisions are identified, so a reviewer knows what is being compared
    assert "cafe0000cafe" in page
    assert "beef0000beef" in page
    assert "5.1.0" in page


def test_compare_needs_a_manifest(tmp_path: Path):
    (tmp_path / "before").mkdir()
    (tmp_path / "after").mkdir()
    with pytest.raises(SystemExit, match=r"manifest\.json"):
        theme_shots.import_before(tmp_path / "before", tmp_path / "after")


def test_console_summary_lists_every_page_that_logged(tmp_path: Path):
    out = tmp_path / "after"
    out.mkdir()
    manifest = fake_manifest(
        out,
        {
            "furo": {
                "backgrounds": {"light": "rgb(255, 255, 255)"},
                "errors": [{"kind": "pageerror", "text": "boom"}],
            },
            "alabaster": {"backgrounds": {"light": "rgb(255, 255, 255)"}},
        },
    )
    summary = theme_shots.console_summary(manifest)
    assert len(summary) == 1
    assert summary[0].startswith("furo/light: 1 console error(s)")
    assert "boom" in summary[0]


# --- the CLI, and staying browser-free ------------------------------------------------------


def test_list_targets_needs_no_browser(capsys: pytest.CaptureFixture[str]):
    assert theme_shots.main(["--list-targets"]) == 0
    printed = capsys.readouterr().out
    for label in LABELS:
        assert label in printed
    # nothing on this path touched the driver
    assert "sync_playwright" not in printed


def test_no_builds_names_the_tasks_that_make_them(tmp_path: Path):
    with pytest.raises(SystemExit) as error:
        theme_shots.main(["--build-root", str(tmp_path), "--out", str(tmp_path / "o")])
    message = str(error.value)
    assert "docs-needs-themes" in message
    for _, task in theme_shots.BUILD_TASKS:
        assert task in message


def test_an_unknown_mode_is_a_usage_error(tmp_path: Path):
    make_build(tmp_path, "furo")
    with pytest.raises(SystemExit, match="sepia"):
        theme_shots.main(["--build-root", str(tmp_path), "--modes", "sepia"])


def test_viewport_parsing():
    assert theme_shots.parse_viewport("1280x900") == (1280, 900)
    with pytest.raises(Exception, match="WIDTHxHEIGHT"):
        theme_shots.parse_viewport("wide")


def test_playwright_is_imported_lazily_and_says_how_to_get_it(
    monkeypatch: pytest.MonkeyPatch,
):
    """The whole point of the lazy import: this module works in an environment without it."""
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    with pytest.raises(SystemExit) as error:
        theme_shots._import_playwright()
    message = str(error.value)
    assert "--group js" in message
    assert "install-browser" in message


def test_serve_hands_out_the_build_over_http(tmp_path: Path):
    """Not `file://`: an opaque origin breaks module scripts and every fetch a theme makes.

    Loopback only -- nothing here leaves the machine.
    """
    (tmp_path / "furo").mkdir()
    (tmp_path / "furo" / "index.html").write_bytes(b"<h1>needtable</h1>")
    with theme_shots.serve(tmp_path) as base_url:
        assert base_url.startswith("http://127.0.0.1:")
        with urllib.request.urlopen(f"{base_url}/furo/index.html") as response:
            assert response.read() == b"<h1>needtable</h1>"
