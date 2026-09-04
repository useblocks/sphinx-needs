"""Web URLs for test sources.

Sphinx-free, like every module the converter CLI depends on.

Only the small amount of URL handling the converter actually needs lives here:
normalising a git remote into a browsable base, and formatting a line-anchored
source URL. sphinx-codelinks carries a fuller implementation (giturlparse-based,
covering more forges); when the two extensions are consolidated the machinery
should be shared rather than duplicated -- which is why this stays deliberately
minimal instead of growing a second forge matrix.
"""

import re

#: GitHub and GitHub-compatible forges. GitLab needs ``{base}/-/blob/...``.
DEFAULT_URL_PATTERN = "{base}/blob/{commit}/{file}#L{line}"

#: ``git@host:org/repo.git`` and ``ssh://git@host/org/repo.git``.
_SCP_STYLE = re.compile(
    r"^(?:ssh://)?(?:[^@/]+@)?(?P<host>[^:/]+)[:/](?P<path>.+?)(?:\.git)?/?$"
)


def normalise_remote_url(remote_url: str) -> str:
    """Turn a git remote into a browsable ``https`` base URL.

    An already-browsable URL is returned unchanged apart from a trailing
    ``.git``/``/``; anything unrecognised is passed through, so an explicitly
    configured base is never mangled.
    """
    url = remote_url.strip()
    if not url:
        return ""

    if url.startswith(("http://", "https://")):
        stripped = url.rstrip("/")
        return stripped.removesuffix(".git")

    match = _SCP_STYLE.match(url)
    if match is None:
        return url.rstrip("/")

    host = match.group("host")
    path = match.group("path")
    return f"https://{host}/{path}"


def source_url(
    base_url: str,
    commit: str,
    file: str,
    line: str,
    pattern: str = DEFAULT_URL_PATTERN,
) -> str:
    """Line-anchored URL of a test source, or ``""`` without repo metadata.

    A hermetic build has no git remote, so the absence of metadata must yield an
    empty field rather than a placeholder URL that looks real and 404s.
    When the line is unknown the anchor is dropped instead of pointing at a
    fabricated line.
    """
    if not base_url or not commit or not file:
        return ""

    effective_pattern = pattern if line else pattern.split("#")[0]
    return effective_pattern.format(base=base_url, commit=commit, file=file, line=line)
