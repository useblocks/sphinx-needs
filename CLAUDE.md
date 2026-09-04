@AGENTS.md

## Claude Code cloud sessions

What a cloud environment for this repository needs, measured on the Ubuntu 24.04 image
(Python 3.11–3.13, uv, Node, OpenJDK 21 and `gh` are preinstalled):

- **Network**: Custom, keeping the default package-manager list, plus `docs.python.org` and
  `www.sphinx-doc.org` (intersphinx — without them `docs-needs` fails under `-nW`),
  `cdn.playwright.dev` (Playwright's browser download — the only host it tries for
  chromium on linux-x64; its `playwright.download.prss.microsoft.com` mirror is never
  consulted for that artefact, see `AGENTS.md`), and `api.github.com` (the GitHub-service
  example in the docs). The allowlist lives on the environment, not in this repository:
  nothing under `.claude/` can add a host to it.
- **Setup script**: `apt-get install -y graphviz` — `dot` is absent from the image and the
  needflow tests fail rather than skip. Nothing else is needed: `prek` and `poe` come from
  `uv sync`.
- **Environment variables**: none to set on the environment. `.claude/settings.json` sets
  `UV_HTTP_TIMEOUT=180` for every Claude Code session, cloud ones included (committed
  project settings are read there): uv's 30 s default is not enough for this lock through
  the session proxy — a cold `uv sync --frozen` died on `babel` with "network timeout" and
  only got through on a second run off the warm cache. Do **not** set `UV_PYTHON`: the root
  `.python-version` pins the default environment to 3.13, which the image has, so a bare
  `uv sync` resolves the newest sphinx without help, and the variable would override the
  file for every command in the session.

### The browser tests in a cloud session

Measured on the image: `uv sync --frozen && uv run poe install-browser && uv run poe
test-needs-js` gives 3 passed in 9 s. Two things about this image differ from the
`AGENTS.md` account.

**The cache is not `~/.cache/ms-playwright`.** The image sets
`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers` and ships a Chromium there already, so that is
the directory `playwright install` writes to and the one to inspect.

**The browser it ships is the wrong revision.** At the time of writing the image has
chromium 1194 (Chrome 141); the pinned playwright 1.62 resolves exactly
`/opt/pw-browsers/chromium-1234/…` (Chrome 151) and reports `Executable doesn't exist
at …`, which looks like nothing is installed at all. Do not try to point the pin at the
image's browser; fetch the one it names.

So the browser has to be fetched, and with `cdn.playwright.dev` in the environment's
network policy that is all there is to it: run `uv run poe install-browser` in the session
when you actually need the browser tests — measured 299 MiB over its two artefacts
(chromium and chrome-headless-shell), 651 MB on disk, 14 s. Keep it out of the setup
script: that is a poor tax on every session for one three-case test module, and the
container is ephemeral so no session pays it for the next one. Without the host the
download is refused before it starts — the proxy answers 403 `no rule or allowlist entry
allows host "cdn.playwright.dev"`, four retries, ~5 s. `--browser-channel chrome`, the
download-free route, is **not** available here: the image has no Google Chrome, only
playwright's Chromium.

Attribution: this repository wants no `Co-Authored-By` trailers, "Generated with Claude
Code" lines or session links in commits, pull requests, issues or comments.
`.claude/settings.json` switches them off for Claude Code; do not add them by hand either.
