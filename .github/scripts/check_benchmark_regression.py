"""Fail when a benchmark is worse than its recent baseline on comparable hardware.

Usage: python .github/scripts/check_benchmark_regression.py HISTORY CURRENT COMMIT

HISTORY is the ``data.js`` github-action-benchmark keeps on the ``benchmarks`` branch,
CURRENT the list ``extract_benchmark_data.py`` wrote, and COMMIT this run's commit, whose
own entries (from an earlier attempt of the same run) are never part of its baseline.

Why not the action's own alert: it compares a result with the ONE result before it, and
``ubuntu-latest`` hands out machines of different speeds -- since 2026-09 about a third
of runs landed about 1.5 times faster than the rest, so a slow run after a fast one
crossed the 150 % threshold with no change to the code (one push in ten in 2026-10).
Here the baseline is the median of the last ``WINDOW`` results, and for a duration only
those measured on the same CPU model. Peak memory barely depends on the machine and is
compared with every recent result.

The check fails only on what it can judge: a benchmark with fewer than ``MIN_BASELINE``
comparable results passes with a notice, which is every benchmark the first time it
runs on a CPU model.
"""

import json
import os
import statistics
import sys
from pathlib import Path
from typing import TypedDict, cast

WINDOW = 10
MIN_BASELINE = 3
#: how much worse than the baseline is a regression, per unit
THRESHOLDS = {"s": 1.3, "MB": 1.1}


class Bench(TypedDict):
    """One result, as ``extract_benchmark_data.py`` writes it and the action stores it."""

    name: str
    unit: str
    value: float
    extra: str


class Commit(TypedDict):
    id: str


class Entry(TypedDict):
    """One run's results in the action's ``data.js``."""

    commit: Commit
    benches: list[Bench]


def cpu_of(bench: Bench) -> str | None:
    """The ``CPU:`` line of a result's ``extra``; results from before it was recorded have none."""
    for line in bench.get("extra", "").splitlines():
        if line.startswith("CPU: "):
            return line.removeprefix("CPU: ")
    return None


def load_history(path: Path) -> list[Entry]:
    text = path.read_text()
    text = text[text.index("{") :]
    return cast("list[Entry]", json.loads(text)["entries"]["Benchmark"])


def check(history_path: Path, current_path: Path, commit: str) -> int:
    history = [
        entry for entry in load_history(history_path) if entry["commit"]["id"] != commit
    ]
    current = cast("list[Bench]", json.loads(current_path.read_text()))

    rows = []
    regressions = []
    for bench in current:
        name, unit, value = bench["name"], bench["unit"], bench["value"]
        cpu = cpu_of(bench)
        past = [
            b["value"]
            for entry in history
            for b in entry["benches"]
            if b["name"] == name
            and b["unit"] == unit
            and (unit != "s" or cpu_of(b) == cpu)
        ][-WINDOW:]
        if len(past) < MIN_BASELINE:
            rows.append(
                f"| {name} | {value:.3f} {unit} | {len(past)} comparable results "
                f"| | not judged |"
            )
            print(
                f"::notice::{name}: {len(past)} comparable results so far, "
                f"{MIN_BASELINE} are needed to judge one"
            )
            continue
        baseline = statistics.median(past)
        ratio = value / baseline
        threshold = THRESHOLDS[unit]
        verdict = "REGRESSION" if ratio > threshold else "ok"
        rows.append(
            f"| {name} | {value:.3f} {unit} | {baseline:.3f} {unit} (median of "
            f"{len(past)}) | {ratio:.2f} | {verdict} |"
        )
        if ratio > threshold:
            regressions.append(
                f"{name}: {value:.3f} {unit} is {ratio:.2f} times the median of the last "
                f"{len(past)} comparable results ({baseline:.3f} {unit}), over the "
                f"{threshold:.2f} allowed"
            )

    cpu = cpu_of(current[0]) if current else None
    summary = "\n".join(
        [
            "## Benchmarks",
            "",
            f"CPU: `{cpu}`",
            "",
            "| benchmark | this commit | baseline | ratio | verdict |",
            "|---|---|---|---|---|",
            *rows,
            "",
        ]
    )
    print(summary)
    if step_summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(step_summary, "a") as out:
            out.write(summary)
    for regression in regressions:
        print(f"::error::{regression}")
    return 1 if regressions else 0


if __name__ == "__main__":
    sys.exit(check(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]))
