"""Turn pytest-benchmark's JSON into github-action-benchmark's ``customSmallerIsBetter`` list.

Usage: python .github/scripts/extract_benchmark_data.py OUTPUT INPUT [INPUT ...]

A duration is the FASTEST round, not the mean: on a shared runner noise only ever adds
time, so the minimum is the estimate least disturbed by it. A benchmark that records
``peak_memory_bytes`` in its ``extra_info`` is reported as that peak, in MB, and its
duration (memray's, not the build's) is dropped. Every entry's ``extra`` names the CPU
the runner had, which is what ``check_benchmark_regression.py`` matches durations on.
"""

import json
import sys
from pathlib import Path

NAMES = {
    "test_basic_time": "Small, basic Sphinx-Needs project",
    "test_official_time": "Official Sphinx-Needs documentation (no diagram rendering)",
    "test_official_memory": "Official Sphinx-Needs documentation: peak memory",
}


def cpu_model() -> str:
    """The runner's CPU, as ``/proc/cpuinfo`` names it, or ``unknown``."""
    try:
        cpuinfo = Path("/proc/cpuinfo").read_text()
    except OSError:
        return "unknown"
    for line in cpuinfo.splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "model name":
            return value.strip()
    return "unknown"


def extract(output_file: str, input_files: list[str]) -> None:
    cpu = cpu_model()
    print(f"CPU: {cpu}")
    data = []
    for input_file in input_files:
        with open(input_file) as in_file:
            input_data = json.load(in_file)
        commit = input_data["commit_info"]
        extra = (
            f"Commit: {commit['id']}\nBranch: {commit['branch']}\n"
            f"Time: {commit['time']}\nCPU: {cpu}"
        )
        for bench in input_data["benchmarks"]:
            name = bench["name"].split("[")[0]
            peak = bench.get("extra_info", {}).get("peak_memory_bytes")
            if peak is not None:
                value, unit = peak / 1_000_000, "MB"
            else:
                value, unit = bench["stats"]["min"], "s"
            data.append(
                {
                    "name": NAMES.get(name, name),
                    "unit": unit,
                    "value": value,
                    "extra": extra,
                }
            )

    with open(output_file, "w") as out_file:
        json.dump(data, out_file, sort_keys=True, indent=4)


if __name__ == "__main__":
    extract(sys.argv[1], sys.argv[2:])
