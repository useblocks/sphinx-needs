#!/usr/bin/env bash
# Build the host Sphinx docs inside a Bazel ``genrule`` action.
#
# Invoked by ``//:docs_html``. Unlike the ``bazel run //:build_docs``
# entry point — which executes in the user-facing workspace where
# ``bazel-bin`` is a valid symlink — a genrule sees its inputs at
# their execroot-relative paths, not at the convenience-symlink path
# ``../bazel-bin/...`` that ``docs/ubproject.toml`` declares. This
# script bridges that gap: it stages a working tree whose layout
# matches the user-facing workspace, runs ``sphinx-build`` there, and
# tars the rendered HTML into the genrule's declared output.
#
# Args:
#   $1        Output tarball path (``$@`` from the genrule cmd).
#   $2        Path to ``docs/conf.py`` (used as a stable anchor for
#             ``realpath``-discovering the umbrella project root).
#   $3 .. $N  Bundle file paths (the ``$(locations :all_bundles)``
#             expansion). Each carries the ``.../bundles/<name>/<file>``
#             suffix that determines its staged location.
set -euo pipefail

out_tar="$1"; shift
conf_py="$1"; shift
bundle_files=("$@")

# Bazel passes the output as ``bazel-out/.../docs_html.tar.gz`` —
# relative to the execroot. The script ``cd``s into the staging dir
# before invoking tar, so resolve to absolute now.
mkdir -p "$(dirname "${out_tar}")"
out_tar="$(realpath -m "${out_tar}")"

# Anchor: ``docs/conf.py`` is a source file, so realpath gives its
# real on-disk path. ``../../..`` from there is the umbrella project
# root (the dir holding ``pyproject.toml`` and ``.venv``). The
# genrule sets ``local = 1`` so this dereference works.
docs_dir_src="$(dirname "$(realpath "${conf_py}")")"
example_src="$(dirname "${docs_dir_src}")"
project_root="$(realpath "${example_src}/../..")"

stage="$(mktemp -d -t sphinx-mounts-stage.XXXXXX)"
trap 'rm -rf "${stage}"' EXIT

# Stage docs/ as a real copy. sphinx-mounts calls ``Path.resolve()``
# on confdir, which follows symlinks — symlinking ``${stage}/docs``
# back to the source tree would canonicalize the confdir to the real
# location and make ``../bazel-bin/...`` resolve against the user's
# workspace rather than the stage. ``cp -RL`` dereferences input
# symlinks (some test setups put files behind symlinks too).
cp -RL "${docs_dir_src}/." "${stage}/docs/"

# Stage the checked-in directive "showcase" bundles. They are plain
# source folders (not Bazel outputs) that ``ubproject.toml`` mounts via
# ``../showcase/<directive>``, so they must sit next to ``${stage}/docs``.
if [ -d "${example_src}/showcase" ]; then
    cp -RL "${example_src}/showcase" "${stage}/showcase"
fi

# Stage each artefact under ``bazel-bin/`` so the workspace-relative
# paths in the host config resolve from ``${stage}/docs/``:
#   - source bundle files at ``bazel-bin/bundles/<bundle>/<file>``
#     (the ``../bazel-bin/bundles/<name>`` paths in ``ubproject.toml``);
#   - the pre-built HTML report under ``bazel-bin/coverage_report/...``
#     (the ``../bazel-bin/coverage_report/extra`` path that conf.py's
#     ``html_extra_path`` consumes).
for f in "${bundle_files[@]}"; do
    case "${f}" in
        */coverage_report/*) rel="coverage_report/${f##*/coverage_report/}" ;;
        *) rel="bundles/${f##*/bundles/}" ;;
    esac
    target="${stage}/bazel-bin/${rel}"
    mkdir -p "$(dirname "${target}")"
    cp -L "${f}" "${target}"
done

out_dir="${stage}/_build/html"
mkdir -p "$(dirname "${out_dir}")"

# sphinx + sphinx-mounts come from the umbrella project's uv-managed
# environment; the host conf.py's extra extensions (myst-parser,
# sphinxcontrib-{plantuml,mermaid}) live in its ``testing`` dependency
# group, so ``--group testing`` pulls them in. Fall back to
# ``python -m sphinx`` for environments that already have the deps
# installed.
cd "${stage}"
if command -v uv >/dev/null 2>&1; then
    uv run --project="${project_root}" --group testing \
        sphinx-build -nW --keep-going -b html -c docs docs "${out_dir}"
else
    python3 -m sphinx -nW --keep-going -b html -c docs docs "${out_dir}"
fi

tar -czf "${out_tar}" -C "${stage}/_build" html
