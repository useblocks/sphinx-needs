@AGENTS.md

## Claude Code cloud sessions

What a cloud environment for this repository needs, measured on the Ubuntu 24.04 image
(Python 3.11–3.13, uv, Node, OpenJDK 21 and `gh` are preinstalled):

- **Network**: Custom, keeping the default package-manager list, plus `docs.python.org` and
  `www.sphinx-doc.org` (intersphinx — without them `docs-needs` fails under `-nW`),
  `download.cypress.io` and `cdn.cypress.io` (the Cypress binary), and `api.github.com`
  (the GitHub-service example in the docs).
- **Setup script**: `apt-get install -y graphviz` — `dot` is absent from the image and the
  needflow tests fail rather than skip. Nothing else is needed: `prek` and `poe` come from
  `uv sync`.
- **Environment variables**: none. The root `.python-version` pins the default environment to
  3.13, which the image has, so a bare `uv sync` resolves the newest sphinx without help. Do
  not set `UV_PYTHON` globally — it overrides the file for every command in the session.

The Cypress binary does not survive the session proxy: node's download is reset a few MB
before the end of the 250 MB transfer, and the installer reports `Corrupted download` at a
different percentage every attempt because it swallows the reset and has no resume or retry.
`curl` completes the same transfer, so seed the per-machine cache from the setup script; the
plain `npm install cypress` then finds the binary and skips the download:

```bash
V=$(npm view cypress version)
curl -fL -C - --retry 3 --retry-all-errors -o /tmp/cypress.zip \
  "https://download.cypress.io/desktop/$V?platform=linux&arch=x64"
CYPRESS_INSTALL_BINARY=/tmp/cypress.zip npx --yes cypress@$V install --force
rm -f /tmp/cypress.zip
```

During a Cypress run, `api.cypress.io`, `cloud.cypress.io` and `redirector.gvt1.com` get
403s from the proxy: that is telemetry and an Electron update check, and the tests pass
regardless.

Attribution: this repository wants no `Co-Authored-By` trailers, "Generated with Claude
Code" lines or session links in commits, pull requests, issues or comments.
`.claude/settings.json` switches them off for Claude Code; do not add them by hand either.
