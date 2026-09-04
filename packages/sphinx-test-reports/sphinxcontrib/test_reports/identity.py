"""Deterministic identities for test-case needs.

Sphinx-free by design: the same identities must be derivable from a build
action, a converter CLI and the Sphinx directives, so nothing here may import
Sphinx or sphinx-needs.

The scheme is byte-compatible with the one S-CORE's ``score_source_code_linker``
produces, so a project can adopt sphinx-test-reports without any of its
test-case need IDs moving.
"""

import base64
import hashlib
import re

#: Stand-in for a missing source file, so a case without a ``file`` attribute
#: still gets a stable identity instead of an unstable or empty one.
PLACEHOLDER_FILE = "<placeholder_file>"

#: Value the JUnit parser reports for an attribute that is absent.
UNKNOWN = "unknown"

#: Characters a need ID may consist of. googletest parameterised suites put
#: ``/`` into both the class and the case name, which is neither a legal need ID
#: (sphinx-needs validates IDs against ``needs_id_regex``) nor a usable HTML
#: anchor.
_UNSAFE_ID_CHARS = re.compile(r"[^A-Za-z0-9_]")


def short_hash(value: str, length: int = 5) -> str:
    """Stable short digest of ``value``: lowercase base32 letters of sha256."""
    digest = hashlib.sha256(value.encode()).digest()
    base32 = base64.b32encode(digest).decode("utf-8").rstrip("=")
    letters_only = "".join(character for character in base32 if character.isalpha())
    return letters_only[:length].lower()


def case_display_name(classname: str, name: str) -> str:
    """Human-readable case name: ``Classname__Casename``.

    Only the last dot-separated segment of the class name is used, matching how
    both googletest and pytest report a fully qualified class path.
    """
    if not classname or classname == UNKNOWN:
        return name
    return f"{classname.split('.')[-1]}__{name}"


def deterministic_case_id(
    *,
    classname: str,
    name: str,
    file: str,
    prefix: str = "testcase",
    hash_length: int = 5,
) -> str:
    """ID derived from *where the test is*, never from what it reported.

    Deriving it from the source location and the case name -- and not from the
    need's content, as the default auto-ID does -- keeps the ID stable when a
    test starts failing differently, which is what build caches and
    pre-authored links to a test case depend on.

    The digest is taken over the *raw* display name so it matches S-CORE's
    value exactly; only the readable part of the ID is sanitised.
    """
    display_name = case_display_name(classname, name)
    source_file = PLACEHOLDER_FILE if not file or file == UNKNOWN else file
    digest = short_hash(source_file + display_name, length=hash_length)
    safe_name = _UNSAFE_ID_CHARS.sub("_", display_name)
    return f"{prefix}__{safe_name}_{digest}"
