@AGENTS.md

## Claude Code cloud sessions

What a cloud environment for this repository needs, measured on the Ubuntu 24.04 image
(Python 3.11–3.13, uv, Node, OpenJDK 21 and `gh` are preinstalled):

- **Network**: Custom, keeping the default package-manager list, plus `docs.python.org` and
  `www.sphinx-doc.org` (intersphinx — without them `docs-needs` fails under `-nW`),
  `cdn.playwright.dev` (Playwright's browser download — the only host it tries for
  chromium on linux-x64; its `playwright.download.prss.microsoft.com` mirror is never
  consulted for that artefact, see `AGENTS.md`), and `api.github.com` (the GitHub-service
  example in the docs).
- **Setup script**: `apt-get install -y graphviz` — `dot` is absent from the image and the
  needflow tests fail rather than skip. Nothing else is needed: `prek` and `poe` come from
  `uv sync`.
- **Environment variables**: `UV_HTTP_TIMEOUT=600`. Not a correctness requirement, but
  uv's 30 s default is not enough for this lock through the session proxy — a cold
  `uv sync --frozen` here died on `babel` with "network timeout" and only got through on a
  second run off the warm cache, and prek's hook install died the same way on `setuptools`.
  Even 180 s was not enough for the `ty` hook building `.venvs/typing` while a second uv
  process was running, so give it room and run heavy tasks one at a time. Do **not** set
  `UV_PYTHON` globally: the root `.python-version` pins
  the default environment to 3.13, which the image has, so a bare `uv sync` resolves the
  newest sphinx without help, and the variable would override the file for every command in
  the session.

### The browser tests in a cloud session

Measured on the image: `uv sync --frozen && uv run poe test-needs-js` gives 3 passed in
7 s — but only after the browser question is settled, and two things about this image make
it different from the `AGENTS.md` account.

**The cache is not `~/.cache/ms-playwright`.** The image sets
`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers` and ships a Chromium there already, so that is
the directory `playwright install` writes to and the one to seed or inspect.

**The browser it ships is the wrong revision.** The image has chromium 1194 (Chrome 141);
the pinned playwright 1.62 resolves exactly `/opt/pw-browsers/chromium-1234/…` (Chrome 151)
and reports `Executable doesn't exist at …`, which looks like nothing is installed at all.

So one of these has to happen, and the first is much the better environment fix:

1. **Allow `cdn.playwright.dev`** in the environment's network policy, then run
   `uv run poe install-browser` in the session when you actually need the browser tests.
   Without that host the download is refused before it starts — the proxy answers 403
   `no rule or allowlist entry allows host "cdn.playwright.dev"`, four retries, ~5 s. Leave
   it out of the setup script: 274 MiB is a poor tax on every session for one three-case
   test module, and
   the container is ephemeral so no session pays it for the next one.
2. **Point the pinned revision at the browser already on the image** — no network, ~0 s,
   and what this session used to get the run above. It is a dev-loop shortcut, not a
   substitute for CI's real install:

   ```bash
   want=$(uv run python -c "import json,playwright,pathlib;print(next(b['revision'] for b in json.loads((pathlib.Path(playwright.__file__).parent/'driver/package/browsers.json').read_text())['browsers'] if b['name']=='chromium'))")
   have=$(basename "$(ls -d /opt/pw-browsers/chromium-* | grep -v -- "-$want\$" | head -1)" | cut -d- -f2)
   ln -sfn headless_shell "/opt/pw-browsers/chromium_headless_shell-$have/chrome-linux/chrome-headless-shell"
   mkdir -p "/opt/pw-browsers/chromium-$want" "/opt/pw-browsers/chromium_headless_shell-$want"
   ln -sfn "/opt/pw-browsers/chromium-$have/chrome-linux" "/opt/pw-browsers/chromium-$want/chrome-linux64"
   ln -sfn "/opt/pw-browsers/chromium_headless_shell-$have/chrome-linux" "/opt/pw-browsers/chromium_headless_shell-$want/chrome-headless-shell-linux64"
   touch "/opt/pw-browsers/chromium-$want/INSTALLATION_COMPLETE" "/opt/pw-browsers/chromium_headless_shell-$want/INSTALLATION_COMPLETE"
   ```

   Both directories are needed: pytest-playwright runs headless, which is the
   `chromium_headless_shell` binary, and the driver wants it under the CfT name
   (`chrome-headless-shell`), not the `headless_shell` the image's build calls it.

`--browser-channel chrome`, the other download-free route, is **not** available here: the
image has no Google Chrome, only playwright's Chromium.

### Python HTTPS through the session proxy fails on 3.13

Measured, and not a repository bug: on Python **3.13** every `https://` request from Python
through the proxy dies with

```
CERTIFICATE_VERIFY_FAILED: CA cert does not include key usage extension
```

3.13 turns on `ssl.VERIFY_X509_STRICT` in `create_default_context()` by default, and the
proxy's own CA — `CN = CCR Upstream Proxy CA (staging), O = Anthropic`, one of four certs in
`/root/.ccr/ca-bundle.crt` with no `X509v3 Key Usage` extension — is exactly what that flag
rejects. Clearing the flag on the same interpreter and the same bundle gives 200, so
`REQUESTS_CA_BUNDLE` and `SSL_CERT_FILE` do **not** help: the bundle is not the problem, the
CA's shape is. `curl` to the same host returns 200 because it does not apply that
strictness, which makes a curl probe useless as evidence that Python will get through.

For this repository it lands on `docs-needs`: the GitHub-service example raises `SSLError`
at read time and takes the build down with exit 2, rather than degrading to the warning
`conf.py` suppresses. `UV_PYTHON=3.12 uv run poe docs-needs` builds clean (`build succeeded`
under `-nW --keep-going`) and is the workaround — one command, not the global `UV_PYTHON`
the section above warns against. It is not free, though: `UV_PYTHON` overrides the pin for
`uv run` too, so that command rebuilds the default `.venv` on 3.12 and the next bare `uv
run` rebuilds it again on 3.13 (measured — `poe lint` right after it reinstalled 71
packages). Run it when you need the docs, not idly. The tests, browser tests included, are unaffected: nothing
in them reaches the network. The real fix belongs to the proxy, whose CA should carry
`keyUsage`/`keyCertSign`; the `(staging)` in its CN suggests this may not outlive that build.

Attribution: this repository wants no `Co-Authored-By` trailers, "Generated with Claude
Code" lines or session links in commits, pull requests, issues or comments.
`.claude/settings.json` switches them off for Claude Code; do not add them by hand either.
