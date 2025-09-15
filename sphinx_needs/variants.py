from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from docutils import nodes

from sphinx_needs.logging import get_logger, log_warning

LOGGER = get_logger(__name__)


class VariantParsingException(BaseException):
    """Called if parsing of given function string has not worked"""


@dataclass(frozen=True, slots=True)
class VariantFunctionParsed:
    """A variant function call."""

    expressions: tuple[tuple[str, bool, str], ...]
    final_value: str | None

    @classmethod
    def from_string(cls, text: str) -> VariantFunctionParsed:
        """Parse a variant function string into expressions and final value.

        :raises VariantParsingException: if parsing fails
        """
        reminaing = text.lstrip()
        exprs: list[tuple[str, bool, str]] = []
        final_value: str | None = None
        while reminaing:
            # is it an enclosed `[expr]:`, a simple `name:`, or a final option without expr?
            if reminaing[0] == "[":
                end_expr = reminaing.find("]:")
                if end_expr == -1:
                    raise VariantParsingException(
                        f"Unclosed variant expression: {text}"
                    )
                bracketed = True
                expr = reminaing[1:end_expr]
                reminaing = reminaing[end_expr + 2 :].lstrip()
            else:
                end_expr = reminaing.find(":")
                if end_expr == -1:
                    final_value = reminaing.strip()
                    break
                bracketed = False
                expr = reminaing[:end_expr]
                reminaing = reminaing[end_expr + 1 :].lstrip()

            # the value is until the next `,` or `;` or end of string
            end_comma = reminaing.find(",")
            end_semicolon = reminaing.find(";")
            if end_comma == -1 and end_semicolon == -1:
                value = reminaing.strip()
                reminaing = ""
            elif end_comma != -1 and (end_semicolon == -1 or end_comma < end_semicolon):
                value = reminaing[:end_comma].strip()
                reminaing = reminaing[end_comma + 1 :].lstrip()
            else:
                value = reminaing[:end_semicolon].strip()
                reminaing = reminaing[end_semicolon + 1 :].lstrip()

            exprs.append((expr, bracketed, value))

        return cls(tuple(exprs), final_value)


def match_variants(
    options: str | None,
    context: dict[str, Any],
    variants: dict[str, str],
    *,
    location: str | tuple[str | None, int | None] | nodes.Node | None = None,
) -> str | None:
    """Evaluate an options list and return the first matching variant.

    Each item should have the format ``<expression>:<value>``,
    where ``<expression>`` is evaluated in the context and if it is ``True``, the value is returned.

    The ``<expression>`` can also be a key in the ``variants`` dict,
    with the actual expression.

    The last item in the list can be a ``<value>`` without an expression,
    which is returned if no other variant matches.

    :param options: A string (delimited by , or ;)
    :param context: Mapping of variables to values used in the expressions
    :param variants: mapping of variables to expressions
    :param location: The source location of the option value,
         which can be a string (the docname or docname:lineno), a tuple of (docname, lineno).
         Used for logging warnings.
    :return: A string if a variant is matched, else None
    """
    if not isinstance(options, (str | None)):
        log_warning(
            LOGGER,
            f"options must be a string or None: {options!r}",
            "variant",
            location=location,
        )
        return None

    if not options:
        return None

    try:
        variant = VariantFunctionParsed.from_string(options)
    except VariantParsingException as e:
        log_warning(
            LOGGER,
            f"Error parsing variant options {options!r}: {e}",
            "variant",
            location=location,
        )
        return None

    for expr, _, value in variant.expressions:
        expr = variants.get(expr, expr)
        try:
            if bool(eval(expr, context.copy())):
                return value
        except Exception as e:
            log_warning(
                LOGGER,
                f"Error in variant expression {expr!r}: {e}",
                "variant",
                location=location,
            )

    return variant.final_value
