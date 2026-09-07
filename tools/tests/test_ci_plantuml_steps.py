"""Every CI site that runs `fetch_plantuml.py` runs it as the fence, not as a downloader.

The committed jar rests on ONE flag. `--verify` checks the jar against
`vendor/plantuml/pin.toml` and never touches the network; **without** it the same script is
the bump tool, which *downloads* — so a site that loses the flag turns the fence into a
self-healing download that exits **0** on exactly the mistake it exists to catch (a bumped
pin with no jar), silently repairing the runner's tree and reporting green. That is reviewer
B's B2 mutation, and nothing in this repository could see it: `check_workspace.py` reads
manifests, not workflows; `actionlint` cannot know what a flag means; and the workflows are
not executed by any test. This module is that missing check.

Three other clauses of the capture shape are load-bearing in the same invisible way, all
measured in the review and written up in `vendor/plantuml/README.md`, "The step CI runs":

* **`shell: bash`** selects ``bash --noprofile --norc -eo pipefail``. The bash GitHub gives a
  step with no `shell:` key is ``bash -e`` with **no pipefail**, under which a failing command
  inside ``$( … )`` piped into `tr` exits **0** and the step goes green with `PLANTUML_JAR`
  exported EMPTY — which every consumer then treats as "unset" (the deliberate
  empty-is-unset rule) and falls back silently. A fence whose failure mode is green is not a
  fence.
* **`| tr -d '\\r'`**. On Windows python's `print()` writes CRLF and ``$( )`` strips trailing
  newlines only, so without it the variable carries a carriage return into `$GITHUB_ENV`.
  The two captures print IDENTICALLY in a log — a CR only returns the cursor — so this defect
  cannot be found by reading one; only `test -f` finds it.
* **the assignment form**: capture into a variable, then `echo` it to `$GITHUB_ENV` on the
  next line. ``echo "PLANTUML_JAR=$(…)"`` would exit 0 with an empty value and leave the
  failure to whatever reads the variable next.

The walk is over the FILES rather than a list of sites, so a new rendering job that copies
the step in gets checked, and a renamed script or a deleted step makes the count below wrong
rather than making the walk quietly empty.

The workflows are PARSED, not grepped: `shell:` is a sibling key of `run:`, so only a parse
can tell which step declares it, and a regex over the file would have to re-implement block
scalars to know where one `run:` ends. `pyyaml` comes from the root's shared `test` group --
the environment CI's Lint job runs `pytest tools/tests` in, and the one a bare root `pytest`
uses -- not from `tools/pyproject.toml`, whose dependencies are what the SCRIPTS import
(`fetch_plantuml.py` is deliberately stdlib-only, and this module does not import it at all).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPT = "tools/src/sn_tools/fetch_plantuml.py"

# The seven sites, counted by hand on this head and asserted below. Six CAPTURE the jar's
# path into `PLANTUML_JAR`; the seventh is CI's Lint job, which runs the same `--verify` with
# no pipe and no capture — so it needs neither `shell: bash` nor the `tr`, and a plain `run:`
# under `bash -e` already carries the script's exit status.
#
#   .github/actions/prepare-cell/action.yml  runs                 capture  (tests-core x14,
#                                                                  tests-extensions x4)
#   .github/workflows/benchmark.yaml         benchmarks           capture
#   .github/workflows/ci.yaml                bazel                capture
#   .github/workflows/ci.yaml                tests-no-mpl         capture
#   .github/workflows/docs.yaml              linkcheck            capture
#   .github/workflows/release.yaml           build                capture
#   .github/workflows/ci.yaml                lint                 the bare check
#
# Adding a job that renders means adding a site and raising these numbers — deliberately, so
# that the addition is a decision someone made rather than a step nobody checked.
EXPECTED_SITES = 7
EXPECTED_CAPTURES = 6


@dataclass(frozen=True)
class Site:
    """One step, anywhere under `.github/`, whose `run:` invokes the script."""

    where: str  # "<file> :: <job or 'runs'> :: <step name>", for the failure message
    run: str
    shell: str | None

    @property
    def lines(self) -> list[str]:
        return [line for line in self.run.splitlines() if line.strip()]

    @property
    def invocation(self) -> str:
        """The one line that runs the script."""
        return next(line for line in self.lines if SCRIPT in line)

    @property
    def captures(self) -> bool:
        """True for the seven that read the path back into a shell variable."""
        return "$(" in self.invocation


def _steps(document: Any) -> list[tuple[str, list[Any]]]:
    """Every `steps:` list in one workflow or composite action, with what holds it."""
    found: list[tuple[str, list[Any]]] = []
    jobs = document.get("jobs") if isinstance(document, dict) else None
    if isinstance(jobs, dict):
        for job_id, job in jobs.items():
            # a job that `uses:` a reusable workflow has no steps of its own
            if isinstance(job, dict) and isinstance(job.get("steps"), list):
                found.append((str(job_id), job["steps"]))
    runs = document.get("runs") if isinstance(document, dict) else None
    if isinstance(runs, dict) and isinstance(runs.get("steps"), list):
        found.append(("runs", runs["steps"]))
    return found


def _collect() -> list[Site]:
    """Walk every workflow and composite action; return the steps that run the script.

    Both suffixes for both kinds. GitHub accepts `.yml` and `.yaml` for each, and this
    repository already uses both (`copilot-setup-steps.yml` beside `ci.yaml`), so a walk
    that guessed one suffix would go green by not looking.
    """
    files = sorted(
        {
            *(REPO / ".github" / "workflows").glob("*.yaml"),
            *(REPO / ".github" / "workflows").glob("*.yml"),
            *REPO.glob(".github/actions/*/action.yaml"),
            *REPO.glob(".github/actions/*/action.yml"),
        }
    )
    assert files, f"no workflows or actions found under {REPO / '.github'}"
    sites: list[Site] = []
    for path in files:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for holder, steps in _steps(document):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                run = step.get("run")
                if not isinstance(run, str) or SCRIPT not in run:
                    continue
                where = f"{path.relative_to(REPO)} :: {holder} :: {step.get('name', '(unnamed)')}"
                sites.append(Site(where=where, run=run, shell=step.get("shell")))
    return sites


SITES = _collect()


def _ids(sites: list[Site]) -> list[str]:
    return [site.where for site in sites]


def test_every_site_was_found() -> None:
    """The positive control: an empty walk, or a renamed script, is RED rather than green.

    Every assertion below is parametrised over what the walk found, so a walk that found
    nothing would report a tidy row of passes. This is the test that makes that impossible,
    and it is why the counts are written down instead of being derived.
    """
    assert len(SITES) == EXPECTED_SITES, "\n".join(["found:", *_ids(SITES)])
    captures = [site for site in SITES if site.captures]
    assert len(captures) == EXPECTED_CAPTURES, "\n".join(["captures:", *_ids(captures)])


@pytest.mark.parametrize("site", SITES, ids=_ids(SITES))
def test_the_invocation_carries_verify(site: Site) -> None:
    """`--verify` at every site. Without it the script DOWNLOADS, and green is the wrong answer."""
    assert "--verify" in site.invocation, f"{site.where}\n  {site.invocation.strip()}"


@pytest.mark.parametrize(
    "site", [s for s in SITES if s.captures], ids=_ids([s for s in SITES if s.captures])
)
def test_the_capture_is_piped_through_tr(site: Site) -> None:
    r"""`| tr -d '\r'`, or Windows exports a path with a carriage return in it."""
    assert r"tr -d '\r'" in site.invocation, (
        f"{site.where}\n  {site.invocation.strip()}"
    )


@pytest.mark.parametrize(
    "site", [s for s in SITES if s.captures], ids=_ids([s for s in SITES if s.captures])
)
def test_the_capture_declares_shell_bash(site: Site) -> None:
    """`shell: bash` — the runner's default has no `pipefail`, so the step would go green."""
    assert site.shell == "bash", f"{site.where}: shell is {site.shell!r}, not 'bash'"


@pytest.mark.parametrize(
    "site", [s for s in SITES if s.captures], ids=_ids([s for s in SITES if s.captures])
)
def test_the_next_line_exports_plantuml_jar(site: Site) -> None:
    """Capture, THEN export — on the very next line, so nothing can come between them."""
    lines = site.lines
    after = lines[lines.index(site.invocation) + 1 :]
    assert after, f"{site.where}: the capture is the last line; nothing exports it"
    export = after[0].strip()
    assert export.startswith('echo "PLANTUML_JAR='), (
        f"{site.where}: next line is {export!r}"
    )
    assert '>> "$GITHUB_ENV"' in export, f"{site.where}: next line is {export!r}"


def test_the_lint_check_needs_neither() -> None:
    """The eighth site, stated rather than assumed: a bare `run:`, so the two clauses do not apply.

    It is exempt from `shell: bash` and the `tr` for a reason that has to hold, not by being
    left out of a list: it captures nothing, so there is no pipeline whose status could be
    lost and no variable a carriage return could contaminate. Assert that, and the exemption
    stays honest — a future edit that turned it into a capture would be caught by this test
    rather than quietly inheriting the exemption.
    """
    plain = [site for site in SITES if not site.captures]
    assert len(plain) == EXPECTED_SITES - EXPECTED_CAPTURES, _ids(plain)
    site = plain[0]
    assert site.where.startswith(".github/workflows/ci.yaml :: lint ::"), site.where
    assert "|" not in site.invocation, site.invocation
    assert "GITHUB_ENV" not in site.run, site.run
