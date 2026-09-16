"""`.github/dependabot.yml` has NO `uv` ecosystem, and that is a decision, not an omission.

The comment in that file says why it left and what replaced it; the pull request that made
the change has the full account. What this module adds is the part nothing else can do: a
dependabot configuration is executed by GitHub and by no test, so re-adding the entry -- or
gutting the workflow that took its place -- would otherwise show up as a red job on the first
of some month, or not at all.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / ".github" / "dependabot.yml"
WORKFLOW = REPO / ".github" / "workflows" / "uv-update.yaml"


def ecosystems() -> list[str]:
    document = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return [entry["package-ecosystem"] for entry in document["updates"]]


def test_no_uv_ecosystem() -> None:
    """Read this module's docstring, and `dependabot.yml`'s comment, before adding one back."""
    assert "uv" not in ecosystems(), ecosystems()


def test_one_github_actions_ecosystem() -> None:
    """The half that stays: exactly one, so neither a deletion nor a duplicate passes."""
    assert ecosystems().count("github-actions") == 1, ecosystems()


def test_the_workflow_that_replaced_it() -> None:
    """The positive control, asserted as a COMMAND rather than as a substring.

    The two assertions above are about ABSENCE, which an empty `updates:` list or a deleted
    workflow would also satisfy -- so the replacement is asserted too. It has to be matched in
    the update step, in command position: `uv lock --upgrade` also appears in two prose strings
    (the assert step's `::error::` message and the body step's opening sentence), so weakening
    the real invocation to a plain `uv lock` -- which degrades the job to a no-op relock that
    opens nothing, every month, and stays green -- passes a substring search over every `run:`.
    """
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert document["name"] == "UV update"
    steps = [step for job in document["jobs"].values() for step in job["steps"]]
    update = next((step for step in steps if step.get("id") == "update"), None)
    assert update is not None, [step.get("id") for step in steps]
    invocation = re.search(r"^\s*(if ! )?uv lock --upgrade\b", update["run"], re.M)
    assert invocation, update["run"]
