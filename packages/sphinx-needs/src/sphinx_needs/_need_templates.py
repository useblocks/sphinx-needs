"""Rendering a need's templates: ``:template:``, ``:pre_template:``, ``:post_template:``
and ``:jinja_content:``.

The four are rendered once, when the need is created (:func:`render_need_templates`,
called by ``_generate_need``), against the created need's
:meth:`~sphinx_needs.need_item.NeedItem.filter_context` and ``needs_render_context``.
A template that cannot be rendered -- its file is missing, it does not parse, it fails
while rendering -- never costs the need: its output is empty and one warning is
reported at the need (``needs.template_missing``, ``needs.template_syntax``,
``needs.template_render``). An undefined name renders empty, as it always has, and is
reported (``needs.template_undefined``): each template is rendered strictly first, and
leniently again only when that fails (:func:`_render`). ``:jinja_content:`` is deprecated
(``needs.deprecated``, until it is removed in 10.0). A template naming a field that
holds a value resolved only after every document is read -- a dynamic function, a
variant, a derived value -- sees it unset, and is reported
(``needs.template_unresolved``, naming the field).

Every template file a render reads, or tries to read, is a dependency of the document
the need is created on (``on_read``), so creating, editing or deleting it re-reads the
document; and a change of ``needs_template_folder`` or of the picklable part of
``needs_render_context`` re-reads every document with a templated need
(:func:`reread_on_template_inputs_change`).

The executable half of these rules is the shared conformance corpus,
``tests/fixtures/need_templates_conformance.toml``.
"""

from __future__ import annotations

import functools
import inspect
import pickle
from collections.abc import Callable, Collection, Set
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs._jinja import render_template_string, undeclared_names
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedsContent

__all__ = ["render_need_templates", "reread_on_template_inputs_change"]

logger = get_logger(__name__)

#: The option a template is rendered for.
TemplateOption = Literal["template", "pre_template", "post_template", "jinja_content"]

#: Where a warning about a need is reported: its document and line, or nowhere.
Location = tuple[str | None, int | None] | None


def render_need_templates(
    needs_config: NeedsSphinxConfig,
    needs_info: NeedItem,
    content_info: NeedsContent,
    *,
    jinja_content: bool,
    template_root: Path | None,
    location: Location,
    on_read: Callable[[Path], None] | None = None,
    unresolved: Collection[str] = (),
) -> NeedsContent:
    """The need's content with its templates rendered.

    :param content_info: The need's content as authored (``content`` is its body).
    :param jinja_content: Whether the body is itself rendered as a template.
    :param template_root: The directory a relative ``needs_template_folder`` is
        resolved against.
    :param location: Where a template's warnings are reported (the need's directive).
    :param on_read: Called with each template file the render reads or tries to read,
        a missing one included: the document's dependencies.
    :param unresolved: The fields of the need whose value is not resolved yet (a
        dynamic function, a variant, a derived value): a template naming one is
        reported.
    :return: ``content_info`` with ``content`` (``:jinja_content:``, then
        ``:template:``), ``pre_content`` and ``post_content`` replaced by the rendered
        text of each template the need names; an empty string for one that cannot be
        rendered. A hidden need's pre and post templates are not rendered (its
        ``pre_content`` and ``post_content`` stay unset).
    """
    need_id = needs_info["id"]
    if jinja_content:
        # deprecated: it loses the authored body, its output can hold Jinja syntax that
        # a reader must not render again, and a template does what it does
        log_warning(
            logger,
            f"The jinja_content option of need {need_id!r} is deprecated, and is "
            "removed in sphinx-needs 10.0: move the Jinja into a template file, with "
            "{{ content }} where the need's body goes, and name it with the template "
            "option.",
            "deprecated",
            location,
        )
        context: dict[str, Any] = needs_info.filter_context()
        context.update(**needs_config.filter_data)
        context.update(**needs_config.render_context)
        content_info = replace(
            content_info,
            content=_render(
                needs_info["content"],
                context,
                option="jinja_content",
                name=None,
                need_id=need_id,
                location=location,
                unresolved=frozenset(unresolved).difference(
                    needs_config.filter_data, needs_config.render_context
                ),
            ),
        )
    rendered: dict[str, str] = {}
    for option, key in (
        ("template", "content"),
        ("pre_template", "pre_content"),
        ("post_template", "post_content"),
    ):
        if option != "template" and needs_info["hide"]:
            # a hidden need shows no pre or post output: it is not rendered at all, so
            # it reads no file and reports nothing (its content is, for needs.json)
            continue
        if name := needs_info[option]:
            rendered[key] = _render_file(
                needs_config,
                needs_info,
                name,
                template_root,
                option=option,
                location=location,
                on_read=on_read,
                unresolved=frozenset(unresolved).difference(
                    needs_config.render_context
                ),
            )
    return replace(content_info, **rendered) if rendered else content_info


def template_path(
    needs_config: NeedsSphinxConfig, name: str, template_root: Path | None
) -> Path | None:
    """The file of the need template *name*: ``<needs_template_folder>/<name>.need``,
    a relative folder resolved against *template_root*; ``None`` where a relative
    folder has no root to resolve against. The file may not exist."""
    folder = Path(needs_config.template_folder)
    if not folder.is_absolute():
        if template_root is None:
            return None
        folder = template_root / folder
    return folder / f"{name}.need"


def _render_file(
    needs_config: NeedsSphinxConfig,
    needs_info: NeedItem,
    name: str,
    template_root: Path | None,
    *,
    option: TemplateOption,
    location: Location,
    on_read: Callable[[Path], None] | None,
    unresolved: frozenset[str],
) -> str:
    """The rendered text of the template file *name*, or ``""`` (with a warning)."""
    need_id = needs_info["id"]
    path = template_path(needs_config, name, template_root)
    if path is None:
        _warn(
            f"The {option} {name!r} of need {need_id!r} is not rendered: the template "
            f"folder {needs_config.template_folder!r} is relative and no template root "
            "is given.",
            "template_missing",
            location,
        )
        return ""
    if on_read is not None:
        # a missing file too: creating it must re-read the document
        on_read(path)
    if not path.is_file():
        _warn(
            f"The {option} {name!r} of need {need_id!r} is not rendered: "
            f"the template does not exist: {path}",
            "template_missing",
            location,
        )
        return ""
    with path.open() as handle:
        source = handle.read()
    return _render(
        source,
        {**needs_info.filter_context(), **needs_config.render_context},
        option=option,
        name=name,
        need_id=need_id,
        location=location,
        unresolved=unresolved,
    )


def _render(
    source: str,
    context: dict[str, Any],
    *,
    option: TemplateOption,
    name: str | None,
    need_id: str,
    location: Location,
    unresolved: frozenset[str] = frozenset(),
) -> str:
    """The rendered *source*, or ``""`` (with a warning) for one that cannot be.

    The render is STRICT first: an undefined value used anywhere but in an
    ``is defined`` test or the ``default`` filter is an error. On any error the source
    is rendered again leniently, as it always was, so the output is never changed: if
    that succeeds, an undefined value was used, and it renders empty with one
    ``needs.template_undefined`` warning; if it fails too, the template cannot be
    rendered (``needs.template_syntax`` / ``needs.template_render``). A strict render
    that succeeds is the lenient one's output, since it used no undefined value. A
    render-context function is called once per call the template makes, as before: the
    lenient render replays what the strict one recorded (:class:`_Calls`).

    Each field of *unresolved* the source NAMES (a top-level name it reads,
    :func:`~sphinx_needs._jinja.undeclared_names`) is reported once
    (``needs.template_unresolved``); its value is what the need holds until it is
    resolved, unset.
    """
    what = f"The {option} {name!r}" if name is not None else "The jinja_content"
    if unresolved:
        try:
            named = undeclared_names(source)
        except Exception:
            # a source that does not parse is reported by the render below
            named = frozenset()
        for field in sorted(named & unresolved):
            _warn(
                f"{what} of need {need_id!r} reads field {field!r}, whose value (a "
                "dynamic function, a variant or a derived value) is resolved only "
                "after the template is rendered: it renders as the unset value.",
                "template_unresolved",
                location,
            )
    calls = _Calls(context)
    try:
        return render_template_string(
            source, calls.recording(), autoescape=False, strict=True
        )
    except Exception as strict_error:
        # deliberately broad: MiniJinja raises ``TemplateError`` (its ``kind`` says which
        # error), and a render-context callable may raise anything
        if getattr(strict_error, "kind", None) == "SyntaxError":
            _warn(
                f"{what} of need {need_id!r} is not rendered: {strict_error}",
                "template_syntax",
                location,
            )
            return ""
        try:
            rendered = render_template_string(
                source, calls.replaying(), autoescape=False
            )
        except Exception as error:
            syntax = getattr(error, "kind", None) == "SyntaxError"
            _warn(
                f"{what} of need {need_id!r} is not rendered: {error}",
                "template_syntax" if syntax else "template_render",
                location,
            )
            return ""
        _warn(
            f"{what} of need {need_id!r} uses an undefined value"
            f"{_undefined_expression(source, strict_error)}, which renders empty. "
            "Every field of the need's type is defined (None when unset); "
            "a name only some needs define can be tested with `is defined`.",
            "template_undefined",
            location,
        )
        return rendered


class _Calls:
    """The calls a template makes of the functions in its context, recorded during the
    strict render and replayed during the lenient one.

    Both renders evaluate the template identically up to the expression the strict one
    fails at, so the lenient one makes the same calls in the same order: each is
    answered with what the strict render's call returned (or raised), until a call
    differs, from which on the functions are called through. A function with side
    effects (a counter) or a cost (a graph walk) therefore runs once per call the
    template makes, as with a single render.

    Only the context's own functions are wrapped (a function, a builtin, a method, a
    ``functools.partial``): a callable reached through an object -- an attribute or a
    method of a value of the context, or a callable object -- is not, and runs again in
    the lenient render.
    """

    __slots__ = ("_context", "_diverged", "_log", "_position")

    def __init__(self, context: dict[str, Any]) -> None:
        self._context = context
        # (name, arguments, keyword arguments, raised, result or exception)
        self._log: list[tuple[str, tuple[Any, ...], dict[str, Any], bool, Any]] = []
        self._position = 0
        self._diverged = False

    def recording(self) -> dict[str, Any]:
        """The context, its functions recording each call."""
        return self._wrapped(self._record)

    def replaying(self) -> dict[str, Any]:
        """The context, its functions replaying the recorded calls in order."""
        self._position = 0
        self._diverged = False
        return self._wrapped(self._replay)

    def _wrapped(self, call: Callable[..., Any]) -> dict[str, Any]:
        wrapped = dict(self._context)
        for name, value in self._context.items():
            if _is_plain_function(value):
                wrapped[name] = _wrap(name, value, call)
        return wrapped

    def _record(
        self,
        name: str,
        function: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        key = _call_key(function, args)
        try:
            result = function(*args, **kwargs)
        except Exception as error:
            self._log.append((name, key, dict(kwargs), True, error))
            raise
        self._log.append((name, key, dict(kwargs), False, result))
        return result

    def _replay(
        self,
        name: str,
        function: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        if not self._diverged and self._position < len(self._log):
            logged_name, logged_args, logged_kwargs, raised, outcome = self._log[
                self._position
            ]
            try:
                same = bool(
                    logged_name == name
                    and logged_args == _call_key(function, args)
                    and logged_kwargs == kwargs
                )
            except Exception:
                # deliberately broad: comparing arguments may raise anything
                same = False
            if same:
                self._position += 1
                if raised:
                    raise outcome
                return outcome
        self._diverged = True
        return function(*args, **kwargs)


def _is_plain_function(value: Any) -> bool:
    return (
        inspect.isfunction(value)
        or inspect.isbuiltin(value)
        or inspect.ismethod(value)
        or isinstance(value, functools.partial)
    )


def _call_key(function: Callable[..., Any], args: tuple[Any, ...]) -> tuple[Any, ...]:
    """The arguments a call is matched by: a function MiniJinja passes its state to
    (``minijinja.pass_state``) gets a new state object in each render, left out."""
    if getattr(function, "__minijinja_pass_state__", False):
        return args[1:]
    return args


def _wrap(
    name: str, function: Callable[..., Any], call: Callable[..., Any]
) -> Callable[..., Any]:
    @functools.wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return call(name, function, args, kwargs)

    return wrapper


def _undefined_expression(source: str, error: Exception) -> str:
    """The expression an undefined error is about, as `` `expr` (line n)``, or ``""``."""
    span = getattr(error, "range", None)
    line = getattr(error, "line", None)
    if not (isinstance(span, tuple) and len(span) == 2):
        return ""
    # MiniJinja's range is in bytes of the source
    expression = source.encode()[span[0] : span[1]].decode(errors="replace").strip()
    if not expression:
        return ""
    return f" `{expression}`" + (f" (line {line})" if isinstance(line, int) else "")


def _warn(
    message: str,
    subtype: Literal[
        "template_missing",
        "template_syntax",
        "template_render",
        "template_undefined",
        "template_unresolved",
    ],
    location: Location,
) -> None:
    log_warning(logger, message, subtype, location)


#: What stands for a ``needs_render_context`` value that cannot be compared across
#: builds (it does not survive a pickle round trip unchanged: a function, an object
#: without equality): its change is not detected, rather than detected on every build.
_UNCOMPARABLE = "<uncomparable>"


def _template_inputs(app: Sphinx) -> tuple[str, dict[str, Any]]:
    """The configuration a need template's output depends on: the template folder
    (resolved as a render resolves it) and the comparable ``needs_render_context``."""
    needs_config = NeedsSphinxConfig(app.config)
    folder = Path(needs_config.template_folder)
    if not folder.is_absolute():
        folder = Path(str(app.srcdir)) / folder
    context: dict[str, Any] = {}
    for key, value in needs_config.render_context.items():
        try:
            # the truth of the comparison inside the ``try`` too: an ``==`` may return a
            # value whose truth raises (an array, a data frame)
            same = bool(pickle.loads(pickle.dumps(value)) == value)
        except Exception:
            # deliberately broad: pickling a value, or comparing one, may raise anything
            same = False
        context[key] = value if same else _UNCOMPARABLE
    return str(folder), context


def _is_templated(need: NeedItem) -> bool:
    return bool(
        need["template"]
        or need["pre_template"]
        or need["post_template"]
        or need["jinja_content"]
    )


def reread_on_template_inputs_change(
    app: Sphinx,
    env: BuildEnvironment,
    added: Set[str],
    changed: Set[str],
    removed: Set[str],
) -> list[str]:
    """The documents to re-read because a need template's inputs changed (the
    ``env-get-outdated`` event): every document with a need that names a template, or
    renders its ``jinja_content``, when ``needs_template_folder`` or the comparable part
    of ``needs_render_context`` differs from what the documents were read with.

    Also every document whose ``needimport`` looked for a template it did not find and
    that now exists (``SphinxNeedsData.template_probes``).

    Both options are ``rebuild = "html"``: a ``"env"`` would re-read EVERY document of a
    project whose render context holds a function, on every build, as such a value never
    compares equal to its pickled self. The template files themselves are dependencies
    of the documents (:func:`render_need_templates`'s ``on_read``).
    """
    data = SphinxNeedsData(env)
    # a document whose needimport looked for a template that now exists
    probed = {
        docname
        for docname, paths in data.template_probes.items()
        if any(Path(path).is_file() for path in paths)
    }
    return sorted(
        ((probed | set(_reread_templated(app, env, data))) & env.found_docs)
        - set(removed)
    )


def _reread_templated(
    app: Sphinx, env: BuildEnvironment, data: SphinxNeedsData
) -> list[str]:
    """The documents with a templated need, when the template inputs changed."""
    inputs = _template_inputs(app)
    previous = data.template_inputs_read_with
    # recorded on every build, so that the build after one that adds a templated need
    # compares against what that need was read with
    data.template_inputs_read_with = inputs
    docnames = {
        need["docname"]
        for need in data.get_needs_mutable().values()
        if need["docname"] and _is_templated(need)
    }
    if not docnames or previous is None:
        # no templated need was read: nothing to compare, nothing to re-read
        return []
    try:
        unchanged = bool(previous == inputs)
    except Exception:
        # deliberately broad: a stored value's comparison may raise; re-read
        unchanged = False
    if unchanged:
        return []
    return sorted(docnames)


def purge_template_probes(app: Sphinx, env: BuildEnvironment, docname: str) -> None:
    """Forget a document's template probes when it is purged (``env-purge-doc``)."""
    SphinxNeedsData(env).template_probes.pop(docname, None)


def merge_template_probes(
    app: Sphinx, env: BuildEnvironment, docnames: Set[str], other: BuildEnvironment
) -> None:
    """Take the template probes of the documents a parallel reader read
    (``env-merge-info``)."""
    probes = SphinxNeedsData(env).template_probes
    for docname, paths in SphinxNeedsData(other).template_probes.items():
        if docname in docnames:
            probes[docname] = set(paths)
