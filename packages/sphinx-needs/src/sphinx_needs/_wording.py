"""Small helpers for the words of sphinx-needs' messages, shared by the modules that
write them: none imports anything of sphinx-needs, so any module may use them."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def joined(items: Sequence[str], word: str = "and") -> str:
    """``a``, ``a <word> b``, ``a, b <word> c``."""
    return f" {word} ".join(filter(None, (", ".join(items[:-1]), items[-1])))


def title_hint(name: str, need_types: Mapping[str, str]) -> str:
    """The hint for a name given where a need type is meant: `` (did you mean 'x'?)``
    when it is no need type but a need type's title, else ``""``.

    :param need_types: The declared need types: each directive name, with its title.
        Where two types share the title, the one given last is named.
    """
    if name in need_types:
        return ""
    titles = {title: directive for directive, title in need_types.items()}
    return f" (did you mean {titles[name]!r}?)" if name in titles else ""
