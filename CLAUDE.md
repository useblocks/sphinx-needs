@AGENTS.md

## Claude Code cloud sessions

What a cloud environment for this repository needs, measured on the Ubuntu 24.04 image
(Python 3.11–3.13, uv, Node, OpenJDK 21 and `gh` are preinstalled):

- **Network**: Custom, keeping the default package-manager list, plus `docs.python.org` and
  `www.sphinx-doc.org` (intersphinx — without them `docs-needs` fails under `-nW`),
  `cdn.playwright.dev` and `playwright.download.prss.microsoft.com` (Playwright's browser
  download — the two mirrors its driver tries), and `api.github.com` (the GitHub-service
  example in the docs).
- **Setup script**: `apt-get install -y graphviz` — `dot` is absent from the image and the
  needflow tests fail rather than skip. Nothing else is needed: `prek` and `poe` come from
  `uv sync`.
- **Environment variables**: none. The root `.python-version` pins the default environment to
  3.13, which the image has, so a bare `uv sync` resolves the newest sphinx without help. Do
  not set `UV_PYTHON` globally — it overrides the file for every command in the session.

The Playwright browser download has not yet been exercised through the session proxy (the
~250 MB Electron binary of the harness it replaces did not survive it). If `uv run poe
install-browser` fails there, `~/.cache/ms-playwright` is the cache a setup script would
seed — that directory is the whole of what the install writes.

Attribution: this repository wants no `Co-Authored-By` trailers, "Generated with Claude
Code" lines or session links in commits, pull requests, issues or comments.
`.claude/settings.json` switches them off for Claude Code; do not add them by hand either.
