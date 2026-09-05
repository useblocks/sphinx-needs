#!/usr/bin/env bash
# Drive sphinx-build from Bazel.
#
# Invoked via ``bazel run //:build_docs``. The ``data`` dependency on
# ``:all_bundles`` makes Bazel build the two bundles before the script
# starts, so ``bazel-bin/bundles/api-{foo,bar}/`` exists where
# ``docs/ubproject.toml`` expects to find it.
set -euo pipefail

# ``bazel run`` sets BUILD_WORKSPACE_DIRECTORY to the user's source
# workspace (tests/example/), not the runfiles tree. We chdir there so
# ``-c docs docs`` and the ``../bazel-bin/...`` paths inside
# ``ubproject.toml`` resolve.
cd "${BUILD_WORKSPACE_DIRECTORY}"

# sphinx + sphinx-mounts come from the uv WORKSPACE ROOT's environment,
# four levels up from here (example -> tests -> sphinx-mounts ->
# packages -> the root). It has to be the root and not the member:
# dependency groups belong to the root in a uv workspace, so
# ``uv run --project packages/sphinx-mounts`` would install the member
# and nothing else. The host conf.py's extra extensions (myst-parser,
# sphinxcontrib-{plantuml,mermaid}) live in the root's ``test`` group,
# so ``--group test`` pulls them in. ``uv run --project`` selects the
# right interpreter regardless of where the user invoked Bazel from.
#
# ``--no-default-groups`` matters: ``--group`` ADDS to the default
# groups, so without it this build syncs ``dev`` as well and downloads
# ~70 MiB of tooling (uv, playwright, prek) a docs build has no use for
# — in CI, on top of the ``--no-default-groups --group test``
# environment the job installed one step earlier. Measured: with it,
# from a cell-shaped environment nothing is installed at all, and from
# a contributor's dev-synced ``.venv`` nothing is REMOVED either (uv's
# sync is inexact, so prek/poe/uv/playwright survive). ``--frozen``
# keeps it from touching the lock.
# Output lands under ``_build/html`` so the existing project-wide
# ``**/_build`` gitignore rule covers it.
out="docs/_build/html"

if command -v uv >/dev/null 2>&1; then
    exec uv run --frozen --no-default-groups --group test \
        --project="$(realpath ../../../..)" \
        sphinx-build -nW --keep-going -b html -c docs docs "${out}" "$@"
fi

# Fallback for environments without uv on PATH (a CI runner that installs
# sphinx-mounts globally, say): rely on ``python3 -m sphinx`` finding
# sphinx in the current interpreter.
exec python3 -m sphinx -nW --keep-going -b html -c docs docs "${out}" "$@"
