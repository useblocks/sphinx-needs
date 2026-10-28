"""The template engine and its data (contract §4, §7.1-§7.5).

One function renders: :func:`render`. It is the package's one render seam -- every
template directive renders through it -- which is also where the conformance runner
reads each expansion from.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import minijinja

#: The render's fuel: one unit per instruction (§7.5; a bound, not a semantic).
FUEL = 10_000_000
#: The largest output a template may render, in UTF-8 bytes (§7.5).
OUTPUT_LIMIT = 1024 * 1024
#: The largest template or data file read (§7.5; a bound).
FILE_LIMIT = 16 * 1024 * 1024
#: Names a template cannot have (§7.2): sphinx-jinja2 handed these over, nothing here does.
UNAVAILABLE = ("env",)


class Failure(Exception):
    """A render that produced nothing; ``code`` is the contract code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Root:
    """The sandbox: the source root, and every path a render read or tried to."""

    path: Path
    reads: list[Path] = field(default_factory=list)

    def resolve(self, name: str) -> Path | None:
        """``name`` (a template name, or a path relative to the root; a leading ``/`` is
        the root) as a path inside the root, or ``None`` when it would leave it.

        The path rule (§2.4): a name is ``/``-separated, and a ``\\`` anywhere refuses it;
        ``..`` is resolved as the filesystem resolves it (the path is opened as written, so a
        missing intermediate directory is a missing file); then the real path must be
        inside the root."""
        if "\\" in name or ":" in name or "\0" in name:
            return None
        posix = PurePosixPath(name.lstrip("/"))
        candidate = self.path.joinpath(*posix.parts)
        self.reads.append(candidate)
        real = Path(os.path.realpath(candidate))
        root = Path(os.path.realpath(self.path))
        if real != root and root not in real.parents:
            return None
        return candidate

    def contains(self, path: Path) -> bool:
        """Whether ``path`` (absolute) is inside the root, symlinks resolved."""
        if "\0" in str(path):
            return False
        self.reads.append(path)
        real = Path(os.path.realpath(path))
        root = Path(os.path.realpath(self.path))
        return real == root or root in real.parents

    def read(self, path: Path) -> str:
        """The UTF-8 text of a regular file of at most :data:`FILE_LIMIT` bytes.

        :raises OSError: For a missing, special or too large file.
        """
        if not path.is_file():
            if path.exists():
                msg = f"{path.name} is not a regular file"
                raise OSError(msg)
            msg = f"{path.name} does not exist"
            raise FileNotFoundError(msg)
        if path.stat().st_size > FILE_LIMIT:
            msg = f"{path.name} is larger than {FILE_LIMIT} bytes"
            raise OSError(msg)
        return path.read_text(encoding="utf-8")

    def loader(self) -> Callable[[str], str | None]:
        """The engine's loader: a name inside the root, or nothing."""

        def load(name: str) -> str | None:
            path = self.resolve(name)
            if path is None:
                return None
            try:
                return self.read(path)
            except (OSError, UnicodeDecodeError):
                return None

        return load


# --- data -----------------------------------------------------------------------------


#: The deepest context data may nest (§4.2): a file's top table is level 1.
MAX_DEPTH = 64
#: The signed 64-bit range integers in context data must fall in (§4.2).
I64 = range(-(2**63), 2**63)


def _check_text(text: str, path: str) -> None:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as error:
        msg = f"{path} holds a lone surrogate, which is not text"
        raise ValueError(msg) from error


def check_data(value: object, path: str, depth: int = 1) -> None:
    """Refuse what the context data model (§4.2) does not allow, naming where.

    ``depth`` is the level of ``value`` when it is a table or an array (a file's top
    table is level 1).

    :raises ValueError: Naming the dotted path and the rule broken.
    """
    if isinstance(value, Mapping | list | tuple) and depth > MAX_DEPTH:
        msg = f"{path} is nested deeper than {MAX_DEPTH} levels"
        raise ValueError(msg)
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                msg = f"{path} has a key that is not a string"
                raise ValueError(msg)
            _check_text(key, path)
            check_data(item, f"{path}.{key}", depth + 1)
        return
    if isinstance(value, list | tuple):
        if not value:
            return
        if all(isinstance(item, Mapping) for item in value):
            for index, item in enumerate(value):
                check_data(item, f"{path}[{index}]", depth + 1)
            return
        kinds = {type(item) for item in value}
        if len(kinds) != 1 or not kinds <= {str, bool, int, float}:
            msg = f"{path} is an array that mixes kinds of value, or holds arrays"
            raise ValueError(msg)
        for index, item in enumerate(value):
            check_data(item, f"{path}[{index}]", depth + 1)
        return
    if value is None:
        msg = f"{path} is null, which context data cannot hold"
        raise ValueError(msg)
    if isinstance(value, datetime.date | datetime.time):
        msg = f"{path} is a date or time, which context data cannot hold"
        raise ValueError(msg)
    if isinstance(value, float) and not math.isfinite(value):
        msg = f"{path} is a float that is not finite"
        raise ValueError(msg)
    if type(value) is int and value not in I64:
        msg = f"{path} is an integer outside the signed 64-bit range"
        raise ValueError(msg)
    if isinstance(value, str):
        _check_text(value, path)
        return
    if not isinstance(value, bool | int | float):
        msg = f"{path} is a {type(value).__name__}, which context data cannot hold"
        raise ValueError(msg)


def parse_data(text: str, suffix: str, name: str) -> dict[str, Any]:
    """A context file's data: JSON or TOML, a table at the top, the data model's shape.

    :raises ValueError: Saying why the file cannot be used.
    """
    suffix = suffix.lower()
    if suffix in (".yaml", ".yml"):
        msg = f"{name} is YAML; contexts are JSON or TOML files"
        raise ValueError(msg)
    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            msg = f"{name} is not valid JSON ({error})"
            raise ValueError(msg) from error
    elif suffix == ".toml":
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as error:
            msg = f"{name} is not valid TOML ({error})"
            raise ValueError(msg) from error
    else:
        msg = f"{name} is not a .json or .toml file"
        raise ValueError(msg)
    if not isinstance(data, dict):
        msg = f"{name} does not hold a table at its top level"
        raise ValueError(msg)
    check_data(data, name)
    return data


def read_data(text: str, suffix: str, name: str) -> dict[str, Any]:
    """:func:`parse_data`, with data too deep for the parsers themselves refused too.

    :raises ValueError: Saying why the file cannot be used.
    """
    try:
        return parse_data(text, suffix, name)
    except RecursionError as error:
        msg = f"{name} is nested deeper than {MAX_DEPTH} levels"
        raise ValueError(msg) from error


#: Names the engine reads as literals: a context key spelled so cannot be named, and is
#: left out (§4.8).
LITERAL_NAMES = frozenset({"true", "false", "none", "True", "False", "None", "in"})


def nameable(key: str) -> bool:
    """Whether a template can name ``key`` as a variable: an identifier (Unicode ones
    too: minijinja's ``unicode`` feature, §7.1) that is not a literal's name."""
    return key.isidentifier() and key not in LITERAL_NAMES


def preamble(context: Mapping[str, Any]) -> str:
    """The context as ``{% set %}`` statements of engine-native literals, on ONE line, so
    no template line moves (§4.4, §4.5).

    minijinja-py hands a Python ``dict`` or ``list`` to a template as a Python object:
    printed, it is Python's ``repr`` (``{'a': [1, 2]}``, not ``{"a": [1, 2]}``), its
    ``items()`` is a ``dict_items``, and ``pop``/``append`` change the caller's data. A
    literal is a native value -- printed, iterated in its written order, and immutable
    exactly as the engine's own data is in ubCode. The data model (:func:`check_data`)
    is what makes every value expressible as a literal (JSON is a subset of minijinja's
    literal syntax once null is excluded). A key that is not an identifier cannot be
    named by a template, so it is left out."""
    statements = [
        f"{{% set {key} = {literal(value)} %}}"
        for key, value in context.items()
        if nameable(key)
    ]
    return "".join(statements)


def literal(value: Any) -> str:
    """``value`` as a minijinja literal: JSON's syntax, with ``none`` for null."""
    if value is None:
        return "none"
    if isinstance(value, Mapping):
        items = (
            f"{json.dumps(str(k), ensure_ascii=False)}: {literal(v)}"
            for k, v in value.items()
        )
        return "{" + ", ".join(items) + "}"
    if isinstance(value, list | tuple):
        return "[" + ", ".join(literal(item) for item in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def input_key(identity: str, source: str, context: Mapping[str, Any]) -> str:
    """A digest of a render's inputs, for the per-page breaker (§7.6)."""
    payload = json.dumps([identity, source, context], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --- rendering ------------------------------------------------------------------------

_WORDWRAP_HELPER = minijinja.Environment()


def _wordwrap(
    value: Any,
    width: int = 79,
    break_long_words: bool = True,
    break_on_hyphens: bool = True,
    wrapstring: str | None = None,
) -> str:
    """minijinja's own ``wordwrap``, with the width positional too (§7.1). A separate
    environment renders it: an environment cannot be re-entered from its own filter."""
    keywords: dict[str, Any] = {
        "width": width,
        "break_long_words": break_long_words,
        "break_on_hyphens": break_on_hyphens,
    }
    if wrapstring is not None:
        keywords["wrapstring"] = wrapstring
    arguments = ", ".join(f"{key}={key}" for key in keywords)
    return _WORDWRAP_HELPER.render_str(
        f"{{{{ value|wordwrap({arguments}) }}}}", value=value, **keywords
    )


def environment(root: Root) -> minijinja.Environment:
    """The contract's dialect (§7.1): strict undefined, no autoescaping, standard
    delimiters, ``debug`` removed, ``pycompat``, the positional ``wordwrap``, a fuel
    bound, and a loader that never leaves the source root."""
    env = minijinja.Environment(
        loader=root.loader(),
        undefined_behavior="strict",
        auto_escape_callback=lambda _name: False,
        fuel=FUEL,
        debug=False,
    )
    env.remove_global("debug")
    env.add_filter("wordwrap", _wordwrap)
    return env


@dataclass
class Rendered:
    """A successful render."""

    text: str


def render(source: str, name: str, context: Mapping[str, Any], root: Root) -> Rendered:
    """Render ``source`` (compiled as ``name``) against ``context`` (plain data under the
    data model; it reaches the template as native values, :func:`preamble`).

    The output limit is checked after the render. There is deliberately no live check: a
    minijinja-py ``finalizer`` changes how every value it sees prints (measured on 2.24:
    ``1.0`` prints ``1`` and a list prints as Python's ``repr``), which would break the
    dialect (§7.1); fuel bounds the render instead (§7.5).

    :raises Failure: With the contract code of what went wrong.
    """
    env = environment(root)
    try:
        free = env.undeclared_variables_in_str(source)
    except minijinja.TemplateError as error:
        raise Failure("template_render_error", _describe(error, name)) from error
    for unavailable in UNAVAILABLE:
        if unavailable in free and unavailable not in context:
            msg = f"the template uses {unavailable!r}, which no template is given"
            raise Failure("template_context_unavailable", msg)
    try:
        env.add_template(name, preamble(context) + source)
        # the preamble is the only way in: a context passed as keywords would reach the
        # template as Python objects too (an un-nameable key, or one the preamble skips)
        text = env.render_template(name)
    except minijinja.TemplateError as error:
        if error.kind == "OutOfFuel" or "recursion" in error.message.lower():
            raise Failure("template_compute_limit", _describe(error, name)) from error
        raise Failure("template_render_error", _describe(error, name)) from error
    except Exception as error:
        msg = f"the template cannot be rendered: {error}"
        raise Failure("template_render_error", msg) from error
    if len(text.encode("utf-8")) > OUTPUT_LIMIT:
        raise Failure("template_output_limit", _limit_message())
    return Rendered(text)


def _limit_message() -> str:
    return f"the rendered text is larger than {OUTPUT_LIMIT} bytes; nothing is rendered"


def _describe(error: minijinja.TemplateError, name: str) -> str:
    # a syntax error found before the render names minijinja's "<string>", not the template
    shown = name if error.name in (None, "<string>") else error.name
    where = f" ({shown}, line {error.line})" if error.line else ""
    return f"the template cannot be rendered: {error.message}{where}"
