#!/usr/bin/env bash
# The one graphviz install every Linux job runs: `prepare-cell`'s "Install graphviz (linux)"
# step, and the jobs in `ci.yaml` and `release.yaml` that install graphviz without that
# action. Run with bash, from the repository root or anywhere:
#
#   bash .github/actions/prepare-cell/graphviz-linux.sh key      # the cache key, to $GITHUB_OUTPUT
#   bash .github/actions/prepare-cell/graphviz-linux.sh install  # install, then `dot -V`
#
# The .debs live in `$RUNNER_TEMP/graphviz-debs`, the directory the calling workflow
# restores from `actions/cache` before `install` and saves after it (`uses:` steps cannot
# live in the composite action; its header says why). Why this exists at all is in the
# comment on that action's Linux step.
set -euo pipefail

# Bump to retire every cached set at once, e.g. after a cached set keeps failing to install
# (an exact key hit is never overwritten, so only a new key replaces it)
CACHE_VERSION=1
dir="${RUNNER_TEMP:?}/graphviz-debs"
# the network path only: never wait two minutes on one dead connection, and retry a
# failed fetch (apt backs off between attempts) rather than failing the job on the first.
# Each network call is also bounded as a whole, at 10 minutes: a timed-out `update` only
# warns and a timed-out download fails the step (exit 124, apt's partial output, no
# `::error::`), so the worst case is about 21 minutes. Measured on a black-holed mirror,
# apt's own retries gave up first, failing the step in under five minutes
net=(-o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30)
bound=(timeout --kill-after=30 600)

key() {
  # Which .debs are right is decided by the runner image (its release and its preinstalled
  # libraries, which the downloaded set leaves out) and the architecture. GitHub-hosted
  # runners carry both image variables; a runner without them is not one this was written
  # for, so say so rather than invent a key
  if [ -z "${ImageOS:-}" ] || [ -z "${ImageVersion:-}" ]; then
    echo "::error::ImageOS/ImageVersion are not set, so this is not a GitHub-hosted runner image; the graphviz cache has no key for it"
    exit 1
  fi
  local prefix
  prefix="graphviz-linux-v${CACHE_VERSION}-${ImageOS}-$(dpkg --print-architecture)-"
  echo "graphviz .deb cache key: ${prefix}${ImageVersion}"
  {
    echo "key=${prefix}${ImageVersion}"
    echo "restore-prefix=${prefix}"
  } >> "${GITHUB_OUTPUT:?}"
}

install_from_dir() {
  # Local files as the candidates, with `--no-download`: apt solves the whole set before
  # dpkg touches anything, takes graphviz's dependencies from these files or from what is
  # installed, and REFUSES rather than fetches when that is not enough. `dpkg -i` over the
  # directory would instead unpack what it can and leave the rest unconfigured for a
  # fallback to trip over.
  #
  # `Dir::Cache::archives` is what makes the files count as local: a file whose version is
  # also in the package lists is merged into that version, which apt then looks for in its
  # archive directory, and without this `--no-download` drops it as a download ("Unable to
  # fetch some archives"). `--no-remove`: a set from another image (a restore-key match)
  # that would install only by REMOVING image packages aborts and falls back instead
  local rc=0
  sudo apt-get install --yes --no-download --no-remove -o "Dir::Cache::archives=$dir" \
    "$dir"/*.deb || rc=$?
  # apt takes its lock and creates partial/ in the archive directory, as root; the save
  # step archives this directory as the runner user, so it must hold .debs only
  sudo rm -rf "$dir/partial" "$dir/lock"
  return "$rc"
}

fetch_and_install() {
  sudo rm -rf "$dir"
  mkdir -p "$dir/partial"
  # not fatal: the image ships package lists, and the install below fails on its own if
  # they are too stale to fetch from
  sudo "${bound[@]}" apt-get "${net[@]}" update ||
    echo "::warning::apt-get update failed; fetching graphviz with the image's package lists"
  sudo "${bound[@]}" apt-get "${net[@]}" -o "Dir::Cache::archives=$dir" -o APT::Sandbox::User=root \
    install --yes --download-only graphviz
  # owned by the runner user and .debs only, so the save step can read and archive it
  sudo rm -rf "$dir/partial" "$dir/lock"
  sudo chown -R "$(id -u):$(id -g)" "$dir"
  # the same command as a cache hit, so a set that is saved has installed offline once
  install_from_dir
}

install() {
  if dpkg-query -W -f='${Status}' graphviz 2>/dev/null | grep -q "install ok installed"; then
    echo "graphviz is already installed on this image; nothing to fetch"
    # and nothing to save: a set restored from another image's key never installed here
    sudo rm -rf "$dir"
  elif compgen -G "$dir/*.deb" > /dev/null; then
    echo "graphviz: $(compgen -G "$dir/*.deb" | wc -l) .debs restored from the actions cache; installing them offline"
    if ! install_from_dir; then
      echo "::warning::the cached graphviz .debs did not install on this image; fetching them from the Ubuntu mirrors (if this repeats, bump CACHE_VERSION in graphviz-linux.sh)"
      fetch_and_install
    fi
  else
    echo "graphviz: no cached .debs for this image; fetching them from the Ubuntu mirrors"
    fetch_and_install
  fi
  dot -V || {
    echo "::error::graphviz did not install: no dot on PATH"
    exit 1
  }
}

case "${1:-}" in
  key) key ;;
  install) install ;;
  *)
    echo "usage: $0 key|install" >&2
    exit 2
    ;;
esac
