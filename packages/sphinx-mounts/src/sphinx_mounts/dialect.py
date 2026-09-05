"""Glob-dialect translation for ``[[source.variant_sources]]`` rule patterns.

**Import discipline: this module is deliberately dependency-free** — standard
library only, nothing from :mod:`sphinx_mounts`, Sphinx or docutils. See
:mod:`sphinx_mounts.variants` for why.

A rule's ``files`` patterns are written in **one** dialect and have to reach
**three** engines:

============================== ================================================
Where                          Engine
============================== ================================================
``[[source.variant_sources]]`` ``globset``, ``literal_separator = false``, plus
                               a raw-basename match — the authored dialect
``config.exclude_patterns``    :func:`sphinx.util.matching.patmatch`
                               (``_translate_pattern``)
``[[source.mounts]] exclude``  the Rust ``ignore`` crate's override builder
============================== ================================================

They disagree on three points, all measured:

* ``*`` crosses ``/`` in globset and in neither of the others;
* an interior ``**`` matches **zero** directories in globset and in gitignore,
  but not in Sphinx, whose ``**`` is a plain ``.*`` with the surrounding
  literal ``/`` still required (``sphinx/util/matching.py``
  ``_translate_pattern``: ``**`` -> ``.*``, ``*`` -> ``[^/]*``, ``?`` ->
  ``[^/]``);
* a separator-less pattern matches a **basename at any depth** in globset (via
  the raw-basename match) and in gitignore, but not in Sphinx.

:func:`to_exclude_patterns` and :func:`to_gitignore` are the two translations;
:func:`refuse` is the fence for the spellings that have no faithful form in
some target. Everything here is table-driven and every row of the two tables
has a test.
"""

from __future__ import annotations

from collections.abc import Callable
import re

#: The two path separators a pattern may be written with. ``\`` is a separator
#: on Windows and an ordinary filename character on POSIX, so a pattern that
#: climbs on one platform only is worse than one that climbs on both — the
#: refusals split on both, exactly as ubCode's ``refuse_glob_dialect`` does.
_SEPARATORS = ("/", "\\")


def _has_separator(pattern: str) -> bool:
    return any(sep in pattern for sep in _SEPARATORS)


#: The most zero-widening ``**`` components a pattern may carry.
#:
#: Each leading or interior ``**`` needs a present form and an absent form in
#: Sphinx's dialect (see :func:`to_exclude_patterns`), so *k* of them produce
#: 2^*k* patterns — measured at 1,024 patterns / 35 ms for *k* = 10 and 65,536
#: / 3.2 s for *k* = 16, paid once by discovery and twice by the attribution
#: diff. Six caps the expansion at 64 and still admits every pattern anyone
#: writes: a real rule glob carries one such wildcard, occasionally two.
MAX_ZERO_WIDENING = 6


def _refuse_empty(pattern: str, _scan: str) -> str | None:
    """An empty pattern means two different things to two engines."""
    if pattern.strip():
        return None
    return (
        "a `variant_sources` glob must not be empty. An empty pattern selects "
        "nothing in the authored dialect and EVERY file in a mount's walk, so "
        "one rule string would mean two different document sets inside one "
        "build; remove the entry, or write the pattern you meant"
    )


def _refuse_trailing_separator(_pattern: str, scan: str) -> str | None:
    """A trailing separator is the same hazard as the empty pattern."""
    if not scan.rstrip().endswith(_SEPARATORS):
        return None
    return (
        "a `variant_sources` glob must not end with a path separator. A "
        "trailing separator selects nothing in the authored dialect and a "
        "whole subtree in a mount's walk; write `dir/**` for the tree, or "
        "`dir` for the directory itself"
    )


def _refuse_alternation(_pattern: str, scan: str) -> str | None:
    if "{" not in scan and "}" not in scan:
        return None
    return (
        "`{a,b}` alternation is not supported in a `variant_sources` glob (it "
        "is alternation for one engine and three literal characters for "
        "another, so one pattern would select two different file sets); write "
        "one pattern per alternative"
    )


def _refuse_climb(_pattern: str, scan: str) -> str | None:
    if not any(segment.strip() == ".." for segment in re.split(r"[/\\]", scan)):
        return None
    return (
        "a `variant_sources` glob must not climb out of the project with "
        "`..`; gate files inside the project, and gate an external tree from "
        "the mount that contributes it"
    )


def _refuse_absolute(pattern: str, _scan: str) -> str | None:
    if not (pattern.startswith(_SEPARATORS) or re.match(r"^[A-Za-z]:[/\\]", pattern)):
        return None
    return (
        "a `variant_sources` glob is relative to the project, so it must not "
        "be an absolute path; drop the leading separator and write the pattern "
        "relative to the folder holding `ubproject.toml`"
    )


def _refuse_expansion(_pattern: str, scan: str) -> str | None:
    """Refuse a pattern whose Sphinx-side expansion would be unbounded.

    See :data:`MAX_ZERO_WIDENING` for the number and the measurement behind it.
    """
    segments = _segments(scan.replace("\\", "/"))
    widening = sum(
        1
        for index, segment in enumerate(segments)
        if segment == "**" and index != len(segments) - 1
    )
    if widening <= MAX_ZERO_WIDENING:
        return None
    return (
        f"a `variant_sources` glob may carry at most {MAX_ZERO_WIDENING} `**` "
        f"path components before the last one; this has {widening}. Each one "
        f"has to be emitted in a present and an absent form for Sphinx's "
        f"matcher, so the cost doubles per wildcard — collapse the adjacent "
        f"ones (`**/**` is `**`) or name the path"
    )


def _refuse_question(_pattern: str, scan: str) -> str | None:
    if "?" not in scan or not _has_separator(scan):
        return None
    return (
        "`?` may cross a path separator in one engine and not in another, so a "
        "`?` in a pattern that also contains a path separator has no faithful "
        "spelling for every reader; write the path segment out in full, or use "
        "`**`"
    )


#: The fence, in order. Each entry takes ``(pattern, scan)`` and returns a
#: reason or ``None``; ``scan`` is the pattern with its ``[...]`` character
#: classes blanked out, because a ``?`` or a ``{`` inside a class is a literal
#: character in all three engines and refusing it would abort a build over a
#: pattern with no hazard in it at all.
_REFUSALS: tuple[Callable[[str, str], str | None], ...] = (
    _refuse_empty,
    _refuse_trailing_separator,
    _refuse_alternation,
    _refuse_climb,
    _refuse_absolute,
    _refuse_expansion,
    _refuse_question,
)


def refuse(pattern: str) -> str | None:
    """Return why ``pattern`` is refused, or ``None`` when it is usable.

    Every refusal **refuses the whole configuration** rather than skipping its
    rule: dropping a rule leaves every file it named — including the files its
    *valid* patterns named — in the build, behind a diagnostic a project could
    silence. For a key whose only purpose is keeping content out of a build,
    failing open is the one outcome that must not be possible.

    The refusal is variant-**independent**: a pattern this key cannot interpret
    is unusable in every variant, so it is checked before any condition is
    evaluated. (The root-document refusal is the variant-dependent one.)
    """
    scan = _outside_classes(pattern)
    for check in _REFUSALS:
        reason = check(pattern, scan)
        if reason is not None:
            return reason
    return None


# ---------------------------------------------------------------------------
# Splitting a pattern into segments, without touching character classes
# ---------------------------------------------------------------------------


def _segments(pattern: str) -> list[str]:
    """Split ``pattern`` on ``/``, leaving ``[...]`` classes intact.

    A ``/`` inside a character class is not a separator. The class syntax is
    shared by all three engines, so treating it as opaque is what keeps the
    translations from mangling it.
    """
    out: list[str] = []
    current = ""
    in_class = False
    for char in pattern:
        if in_class:
            current += char
            if char == "]":
                in_class = False
            continue
        if char == "[":
            in_class = True
            current += char
            continue
        if char == "/":
            out.append(current)
            current = ""
            continue
        current += char
    out.append(current)
    return out


def _has_single_star(segment: str) -> bool:
    """Whether ``segment`` contains a ``*`` run that is not a bare ``**``.

    ``**`` as a whole segment is the zero-or-more-directories wildcard and is
    handled separately; anything else containing a ``*`` is a single star that
    crosses ``/`` in globset and does not in the other two dialects.
    """
    return segment != "**" and "*" in _outside_classes(segment)


def _outside_classes(segment: str) -> str:
    """``segment`` with every ``[...]`` character class blanked out.

    A ``*`` inside a class is a literal asterisk in all three dialects, so it
    must not be widened or counted.
    """
    out = ""
    in_class = False
    for char in segment:
        if in_class:
            out += "_"
            if char == "]":
                in_class = False
            continue
        if char == "[":
            in_class = True
            out += "_"
            continue
        out += char
    return out


def _widen_stars(segment: str) -> str:
    """Turn every single-``*`` run outside a character class into ``**``.

    globset's ``*`` crosses ``/`` with ``literal_separator = false``, and
    Sphinx's ``**`` is exactly ``.*`` — so widening is the faithful
    translation, not a loosening.
    """
    out = ""
    i = 0
    in_class = False
    while i < len(segment):
        char = segment[i]
        if in_class:
            out += char
            if char == "]":
                in_class = False
            i += 1
            continue
        if char == "[":
            in_class = True
            out += char
            i += 1
            continue
        if char == "*":
            while i < len(segment) and segment[i] == "*":
                i += 1
            out += "**"
            continue
        out += char
        i += 1
    return out


# ---------------------------------------------------------------------------
# globset -> gitignore (the mount arm)
# ---------------------------------------------------------------------------


def to_gitignore(pattern: str) -> str:
    """Translate a rule glob into a mount ``exclude`` (gitignore) pattern.

    Anchored at the mount's ``dir``, which is what makes a path-naming rule
    glob reach into a mount at all — the same per-root re-anchoring ubCode
    performs, reproduced by handing the mount's own walker the translated
    pattern.

    The measured table (fixture tree walked with the exact ``WalkBuilder``
    configuration :func:`sphinx_mounts.mounter._build_walker` uses):

    ========================= ================================ ==============
    Rule glob                 Mount ``exclude``                Why
    ========================= ================================ ==============
    ``name.rst``              ``name.rst``                     identity — both match the basename at every depth
    ``*.rst``                 ``*.rst``                        identity — both match at every depth
    ``a?c.rst``               ``a?c.rst``                      identity for the separator-less case
    ``a[bX]c.rst``            ``a[bX]c.rst``                   identity — same class syntax
    ``dir/name.rst``          ``dir/name.rst``                 identity — root-anchored once a separator is present
    ``dir/**``                ``dir/**``                       identity
    ``dir/**/*.rst``          ``dir/**/*.rst``                 identity — both treat an interior ``**`` as zero-or-more
    ``dir/*.rst``             ``dir/**/*.rst``                 globset's ``*`` crosses ``/`` and gitignore's does not
    ``dir/*``                 ``dir/**``                       same reason, said directly
    ========================= ================================ ==============

    A separator-less pattern is left exactly as authored, because that is what
    makes both engines match it by **basename at any depth** — the documented
    footgun, and the one row where doing nothing is the translation.
    """
    if not _has_separator(pattern):
        return pattern
    segments = _segments(pattern.replace("\\", "/"))
    out: list[str] = []
    for index, segment in enumerate(segments):
        if not _has_single_star(segment):
            out.append(segment)
            continue
        if segment == "*" and index == len(segments) - 1:
            # `dir/*` -> `dir/**`: gitignore's `dir/*` happens to prune a
            # matching sub-directory and so gives the same answer here, but
            # `dir/**` says it directly.
            out.append("**")
            continue
        if out and out[-1] == "**":
            # Already preceded by a zero-or-more wildcard; widening again would
            # only add a redundant `**/`.
            out.append(segment)
            continue
        out.extend(("**", segment))
    return "/".join(out)


# ---------------------------------------------------------------------------
# globset -> Sphinx exclude_patterns (the host arm)
# ---------------------------------------------------------------------------


def to_exclude_patterns(pattern: str) -> list[str]:
    """Translate a rule glob into ``config.exclude_patterns`` entries.

    Returns a **list**, because two of globset's behaviours need two Sphinx
    patterns to reproduce:

    * a separator-less pattern matches a basename at any depth, and Sphinx has
      no single spelling for "here or anywhere below" — ``**/x`` translates to
      ``.*/x$`` and so cannot match ``x`` at the root. Both forms are emitted.
      (``sphinx.util.matching.Matcher`` *does* expand ``**/x`` to ``x`` for
      asset copying, but ``Project.discover`` goes through ``get_matching_files``
      -> ``compile_matchers``, which does not.)
    * an interior or leading ``**`` matches zero directories in globset, and
      Sphinx's ``**`` is a plain ``.*`` with the surrounding literal ``/`` still
      required. Each such wildcard therefore contributes a present form and an
      absent form.

    A single ``*`` crosses ``/`` in globset, so it becomes ``**`` — Sphinx's
    ``**`` is exactly ``.*``, which is what globset's ``*`` means with
    ``literal_separator = false``.

    Anchoring is the caller's business and is identity by construction: the
    host arm only runs when the declared source root resolves to Sphinx's
    ``srcdir`` (see the layout guard), so a rule glob and an
    ``exclude_patterns`` entry share a base.
    """
    if not _has_separator(pattern):
        # Basename at any depth: `x` for the root, `**/x` for everything below.
        return [pattern, f"**/{pattern}"]
    segments = _segments(pattern.replace("\\", "/"))
    variants: list[list[str]] = [[]]
    for index, segment in enumerate(segments):
        if segment == "**":
            if index == len(segments) - 1:
                # A trailing `/**` requires at least one component after it in
                # globset, so there is no absent form to emit.
                variants = [[*variant, "**"] for variant in variants]
                continue
            # Leading or interior: zero or more directories, so both.
            variants = [
                *[[*variant, "**"] for variant in variants],
                *[list(variant) for variant in variants],
            ]
            continue
        widened = _widen_stars(segment)
        variants = [[*variant, widened] for variant in variants]
    seen: dict[str, None] = {}
    for variant in variants:
        seen.setdefault("/".join(variant), None)
    return list(seen)


# ---------------------------------------------------------------------------
# Matching, under the AUTHORED (globset) dialect
# ---------------------------------------------------------------------------


def _globset_regex(pattern: str) -> str:
    """Compile ``pattern`` to a regex under globset's ``literal_separator = false``.

    * ``/**/`` matches one or more separators-worth of components — i.e. zero
      or more directories;
    * a leading ``**/`` is an optional prefix;
    * a trailing ``/**`` requires at least one component;
    * ``*`` and ``?`` cross ``/``, because separators are not literal;
    * ``[...]`` is passed through.
    """
    out = ""
    i = 0
    n = len(pattern)
    while i < n:
        if pattern.startswith("**/", i) and (i == 0 or pattern[i - 1] == "/"):
            # Zero or more directories, leading and interior alike. The
            # preceding literal `/` has already been emitted, so the optional
            # group carries its own trailing separator.
            out += "(?:.*/)?"
            i += 3
            continue
        if pattern.startswith("/**", i) and i + 3 == n:
            out += "/.+"
            i += 3
            continue
        char = pattern[i]
        if char == "*":
            while i < n and pattern[i] == "*":
                i += 1
            out += ".*"
            continue
        if char == "?":
            out += "."
            i += 1
            continue
        if char == "[":
            end = pattern.find("]", i + 1)
            if end == -1:
                out += re.escape(char)
                i += 1
                continue
            body = pattern[i + 1 : end]
            if body.startswith("!"):
                body = "^" + body[1:]
            out += f"[{body}]"
            i = end + 1
            continue
        out += re.escape(char)
        i += 1
    return f"(?s:{out})\\Z"


def matches(pattern: str, relpath: str, *, basename: str | None = None) -> bool:
    """Whether the AUTHORED rule glob selects ``relpath``.

    This is globset's own reading of the pattern, plus ubCode's raw-basename
    match — the walker's test mirrored exactly ("the full path OR the file
    name"). It is used for the file-list mount arm, which has no walker to hand
    a pattern to and so has to ask the question itself.

    :param pattern: The rule glob exactly as authored.
    :param relpath: A POSIX-separated path relative to the anchoring root.
    :param basename: The file name, when it differs from ``relpath``'s last
        segment (it never does in practice; the parameter exists so a caller
        can be explicit).
    """
    normalised = relpath.replace("\\", "/")
    name = basename if basename is not None else normalised.rsplit("/", 1)[-1]
    expression = re.compile(_globset_regex(pattern))
    return bool(expression.match(normalised)) or bool(expression.match(name))
