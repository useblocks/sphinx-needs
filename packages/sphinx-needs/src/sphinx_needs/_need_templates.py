"""Rendering a need's templates: ``:template:``, ``:pre_template:``, ``:post_template:``
and ``:jinja_content:``.

The four are rendered once, when the need is created (:func:`render_need_templates`,
called by ``_generate_need``), against the created need's
:meth:`~sphinx_needs.need_item.NeedItem.filter_context` and ``needs_render_context``.
A template that cannot be rendered -- its file is missing, it does not parse, it fails
while rendering -- never costs the need: its output is empty and one warning is
reported at the need (``needs.template_missing``, ``needs.template_syntax``,
``needs.template_render``).

The executable half of these rules is the shared conformance corpus,
``tests/fixtures/need_templates_conformance.toml``.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from sphinx_needs._jinja import render_template_string
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedsContent

__all__ = ["render_need_templates"]

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
) -> NeedsContent:
    """The need's content with its templates rendered.

    :param content_info: The need's content as authored (``content`` is its body).
    :param jinja_content: Whether the body is itself rendered as a template.
    :param template_root: The directory a relative ``needs_template_folder`` is
        resolved against.
    :param location: Where a template's warnings are reported (the need's directive).
    :return: ``content_info`` with ``content`` (``:jinja_content:``, then
        ``:template:``), ``pre_content`` and ``post_content`` replaced by the rendered
        text of each template the need names; an empty string for one that cannot be
        rendered.
    """
    need_id = needs_info["id"]
    if jinja_content:
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
            ),
        )
    rendered: dict[str, str] = {}
    for option, key in (
        ("template", "content"),
        ("pre_template", "pre_content"),
        ("post_template", "post_content"),
    ):
        if name := needs_info[option]:
            rendered[key] = _render_file(
                needs_config,
                needs_info,
                name,
                template_root,
                option=option,
                location=location,
            )
    return replace(content_info, **rendered) if rendered else content_info


def _render_file(
    needs_config: NeedsSphinxConfig,
    needs_info: NeedItem,
    name: str,
    template_root: Path | None,
    *,
    option: TemplateOption,
    location: Location,
) -> str:
    """The rendered text of the template file *name*, or ``""`` (with a warning)."""
    need_id = needs_info["id"]
    folder = Path(needs_config.template_folder)
    if not folder.is_absolute():
        if template_root is None:
            _warn(
                f"The {option} {name!r} of need {need_id!r} is not rendered: the "
                f"template folder {str(folder)!r} is relative and no template root is "
                "given.",
                "template_missing",
                location,
            )
            return ""
        folder = template_root / folder
    path = folder / f"{name}.need"
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
    )


def _render(
    source: str,
    context: dict[str, Any],
    *,
    option: TemplateOption,
    name: str | None,
    need_id: str,
    location: Location,
) -> str:
    """The rendered *source*, or ``""`` (with a warning) for one that cannot be."""
    what = f"The {option} {name!r}" if name is not None else "The jinja_content"
    try:
        return render_template_string(source, context, autoescape=False)
    except Exception as error:
        # deliberately broad: MiniJinja raises ``TemplateError`` (its ``kind`` says which
        # error), and a render-context callable may raise anything
        syntax = getattr(error, "kind", None) == "SyntaxError"
        _warn(
            f"{what} of need {need_id!r} is not rendered: {error}",
            "template_syntax" if syntax else "template_render",
            location,
        )
        return ""


def _warn(
    message: str,
    subtype: Literal["template_missing", "template_syntax", "template_render"],
    location: Location,
) -> None:
    log_warning(logger, message, subtype, location)
