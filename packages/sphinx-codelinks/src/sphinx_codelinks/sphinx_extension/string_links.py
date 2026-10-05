"""The ``needs_string_links`` entries that turn codelinks' URL fields into links.

They are registered once, at ``config-inited``: after the ``[codelinks]`` table is
loaded and the fields are registered, and before Sphinx-Needs validates and compiles
``needs_string_links`` (its ``compile_string_links`` listener, priority 551). Writing
them from inside the ``src-trace`` directive instead, at read time, loses them in every
``-j N`` worker and changes the configuration on every build.

An entry cannot carry anything known only at read time -- a project's commit, or which
project a need came from -- so the remote URL field holds the fully formed URL itself,
and its entry is an identity link: the URL is the target, and the part after the
commit segment (``path#Lline``) is the name.
"""

from __future__ import annotations

from typing import Any

from sphinx.application import Sphinx
from sphinx.config import Config as _SphinxConfig

from sphinx_codelinks.config import CodeLinksConfig, need_id_refs_fields

URL_LINK_REGEX = (
    r"^(?P<codelinks_url>[A-Za-z][A-Za-z0-9+.-]*://"
    r"(?:[^#?]*?/(?:[0-9a-f]{64}|[0-9a-f]{40})/(?P<codelinks_location>.+)|.+))$"
)
"""Captures a whole URL, and the part after a full commit hash segment when it has one.

The name falls back to the whole URL when the URL has no commit segment -- a remote URL
pattern without ``{commit}``, or a project outside a git repository. A value without a
``scheme://`` prefix is not a URL and does not match, so it renders as text.
"""


def url_string_link(field: str) -> dict[str, Any]:
    """The identity string link for a field whose value is a fully formed URL."""
    return {
        "regex": URL_LINK_REGEX,
        "link_url": "{{codelinks_url}}",
        "link_name": "{{codelinks_location or codelinks_url}}",
        "options": [field],
    }


REF_LINK_REGEX = (
    r"^(?P<codelinks_value>"
    r"(?P<codelinks_url>[A-Za-z][A-Za-z0-9+.-]*://"
    r"(?:[^#?]*?/(?:[0-9a-f]{64}|[0-9a-f]{40})/(?P<codelinks_location>.+)|.+))"
    r"|(?P<codelinks_page>.+?)\.[^./]+#L(?P<codelinks_line>\d+)"
    r"|.+)$"
)
"""A reference field's entry: a remote URL (``scheme://``, as :data:`URL_LINK_REGEX`),
else a local value in the ``local-url`` field's shape, ``<file>.<ext>#L<line>`` relative
to the document, which links to the source page generated beside the copied file (in a
serial build, #2044); anything else renders as text."""


def ref_url_string_link(field: str) -> dict[str, Any]:
    """The string link for a field of ``@need-ids:`` references.

    A remote URL renders as :func:`url_string_link` does; a local value as the
    ``local-url`` field does (to the generated source page, named by the value itself).
    """
    return {
        "regex": REF_LINK_REGEX,
        "link_url": (
            "{% if codelinks_url %}{{codelinks_url}}"
            "{% elif codelinks_page %}{{codelinks_page}}.html#L-{{codelinks_line}}"
            "{% endif %}"
        ),
        "link_name": (
            "{% if codelinks_url %}{{codelinks_location or codelinks_url}}"
            "{% elif codelinks_page %}{{codelinks_value}}{% endif %}"
        ),
        "options": [field],
    }


def local_url_string_link(field: str) -> dict[str, Any]:
    """The string link for the local URL field.

    Its value is the copied source file's path relative to the document
    (``../src/file.cpp#L3``), and the link points at the source page generated beside
    that copy -- in a serial build; a parallel one does not generate it yet (#2044).
    """
    return {
        "regex": r"^(?P<value>.+?)\.[^\.]+#L(?P<lineno>\d+)",
        "link_url": "{{value}}.html#L-{{lineno}}",
        "link_name": "{{value}}#L{{lineno}}",
        "options": [field],
    }


# @Register the URL fields' string links at config-inited, IMPL_URL_LINKS_1, impl, [FE_DEF]
def register_string_links(_app: Sphinx, config: _SphinxConfig) -> None:
    """Add the string links for the URL fields to ``needs_string_links``.

    The value is rebound rather than mutated, as it may be the user's own conf.py object.
    A value that is not a dict is left alone: Sphinx-Needs warns about it and ignores it.
    """
    codelinks_config = CodeLinksConfig.from_sphinx(config)
    entries: dict[str, dict[str, Any]] = {}
    if codelinks_config.set_local_url:
        entries[codelinks_config.local_url_field] = local_url_string_link(
            codelinks_config.local_url_field
        )
    projects = codelinks_config.projects
    # a malformed ``projects`` is reported by ``check_sphinx_configuration``, later
    if (
        codelinks_config.set_remote_url
        and isinstance(projects, dict)
        and any(
            isinstance(project, dict) and project.get("remote_url_pattern")
            for project in projects.values()
        )
    ):
        entries[codelinks_config.remote_url_field] = url_string_link(
            codelinks_config.remote_url_field
        )
    for field_name in set(need_id_refs_fields(codelinks_config).values()):
        entries[field_name] = ref_url_string_link(field_name)
    existing = config.needs_string_links
    if not entries or not isinstance(existing, dict):
        return
    config.needs_string_links = {**existing, **entries}
