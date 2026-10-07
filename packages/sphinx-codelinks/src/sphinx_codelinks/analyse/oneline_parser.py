from dataclasses import dataclass

from sphinx_codelinks.analyse.models import WarningSubTypeEnum
from sphinx_codelinks.config import ESCAPE, UNIX_NEWLINE, OneLineCommentStyle


@dataclass
class OnelineParserInvalidWarning:
    """Invalid oneline comments."""

    sub_type: WarningSubTypeEnum
    msg: str


# @One-line comment parser for traceability markers, IMPL_OLP_1, impl, [FE_DEF, FE_CMT]
def oneline_parser(  # handel warnings
    oneline: str, oneline_config: OneLineCommentStyle
) -> dict[str, str | list[str] | int] | OnelineParserInvalidWarning | None:
    """
    Extract the string from the custom one-line comment style with the following steps.

    - Locate the start and end sequences
    - extract the string between them
    - return ``None`` for an empty content, whatever the start sequence
    - on a one-character start sequence, return ``None`` for a content without the
      field separator where more than one field is required: not a marker, and not a
      warning either. The rule is ubCode's, and so are its words: "when a
      single-character start_sequence (like `@`) matches but the content has no field
      delimiter at all, this is likely a stray match
      (e.g., Doxygen `@param`, `@brief`, `@return`) rather than a real marker.
      Treating these as NoMatch avoids noisy TooFewFields warnings on codebases with
      Doxygen annotations. Multi-character sequences (like `[[`) are specific enough
      that a missing delimiter should still produce a warning."
    - apply custom_split to split the strings into a list of fields by `field_split_char`
    - check the number of required fields and the max number of the given fields
    - split the strings located in the field with `type: list[str]` to a list of string
    - introduce the default values to those fields which are not given
    """
    # find indices start and end char
    start_idx = oneline.find(oneline_config.start_sequence)
    end_idx = oneline.rfind(oneline_config.end_sequence)
    if start_idx == -1 or end_idx == -1:
        # start or end sequences do not exist
        return None

    # A marker whose end sequence is the newline extends to the end of the
    # line, so an unanchored start sequence would swallow trailing prose. Anchor
    # such a marker to the start of the comment content: everything preceding
    # the start sequence must be comment decoration (`//`, `#`, `*`, ...) and
    # whitespace. A word character before it means the start sequence is part of
    # free-form prose (e.g. `// see @author, ...`) and the line is ignored
    # (issue #88). Explicitly-bounded markers (e.g. `[[ ... ]]`) are
    # self-delimiting and may appear anywhere, so they are exempt.
    if oneline_config.end_sequence == UNIX_NEWLINE and any(
        char.isalnum() for char in oneline[:start_idx]
    ):
        return None

    # extract the string wrapped by start and end
    start_idx = start_idx + len(oneline_config.start_sequence)
    string = oneline[start_idx:end_idx].strip()

    # numbers of needs_fields which are required
    cnt_required_fields = oneline_config.get_cnt_required_fields()

    if not string:
        # nothing between the start and end sequences: not a marker either
        return None

    # a documentation tag such as `@param x`, not a marker (see the docstring)
    if (
        len(oneline_config.start_sequence) == 1
        and oneline_config.field_split_char not in string
        and cnt_required_fields > 1
    ):
        return None
    # indices of the field which has type:list[str]
    positions_list_str = oneline_config.get_pos_list_str()

    min_fields = cnt_required_fields
    max_fields = len(oneline_config.needs_fields)

    string_fields = [
        _field.strip(" ")
        for _field in custom_split(
            string, oneline_config.field_split_char, positions_list_str
        )
    ]
    if len(string_fields) < min_fields:
        return OnelineParserInvalidWarning(
            sub_type=WarningSubTypeEnum.too_few_fields,
            msg=f"{len(string_fields)} given fields, minimum is {min_fields}",
        )

    if len(string_fields) > max_fields:
        return OnelineParserInvalidWarning(
            sub_type=WarningSubTypeEnum.too_many_fields,
            msg=f"{len(string_fields)} given fields, maximum is {max_fields}",
        )
    resolved: dict[str, str | list[str] | int] = {}
    for idx in range(len(oneline_config.needs_fields)):
        field_name: str = oneline_config.needs_fields[idx]["name"]
        if len(string_fields) > idx:
            # given fields
            if is_newline_in_field(string_fields[idx]):
                # the case where the field contains a new line character
                return OnelineParserInvalidWarning(
                    sub_type=WarningSubTypeEnum.newline_in_field,
                    msg=f"Field '{field_name}' contains a newline character",
                )
            if oneline_config.needs_fields[idx]["type"] == "str":
                resolved[field_name] = string_fields[idx]
            elif oneline_config.needs_fields[idx]["type"] == "list[str]":
                # find the indices of "[" and "]"
                list_start_idx = string_fields[idx].find("[")
                list_end_idx = string_fields[idx].rfind("]")
                if list_start_idx == -1 or list_end_idx == -1:
                    # brackets are not  found
                    return OnelineParserInvalidWarning(
                        sub_type=WarningSubTypeEnum.missing_square_brackets,
                        msg=f"Field '{field_name}' with 'type': '{oneline_config.needs_fields[idx]['type']}' must be given with '[]' brackets",
                    )

                if list_start_idx != 0 or list_end_idx != len(string_fields[idx]) - 1:
                    # brackets are found but not at the beginning and the end
                    return OnelineParserInvalidWarning(
                        sub_type=WarningSubTypeEnum.not_start_or_end_with_square_brackets,
                        msg=f"Field '{field_name}' with 'type': '{oneline_config.needs_fields[idx]['type']}' must start with '[' and end with ']'",
                    )

                string_items = string_fields[idx][list_start_idx + 1 : list_end_idx]

                if not string_items.strip():
                    # the case where the empty string ("") or only spaces between "[" "]"
                    resolved[field_name] = []
                else:
                    items = [_item.strip() for _item in custom_split(string_items, ",")]
                    resolved[field_name] = [item.strip() for item in items]
        else:
            # for not given fields, introduce the default
            default = oneline_config.needs_fields[idx].get("default")
            if default is None:
                continue
            resolved[field_name] = default

    resolved["start_column"] = start_idx
    resolved["end_column"] = end_idx
    return resolved


def custom_split(
    string: str, delimiter: str, positions_list_str: list[int] | None = None
) -> list[str]:
    """
    A string shall be split with the following conditions:

    - To use special chars in literal , escape ('\') must be used
    - String shall be split by the given delimiter
    - In a field with `type: str`:
        - Special chars are delimiter, '\', '[' and ']'
    - In a field with `type: list[str]`:
        - Special chars are only '[' and ']'

    When the string is given without any fields with `type: list[str]` (positions_list_str=None),
    it's considered as it is in a field with `type: str`.
    """
    if positions_list_str is None:
        positions_list_str = []
    escape_chars = [delimiter, "[", "]", ESCAPE]
    field = []  # a list of string for a field
    fields: list[str] = []  # a list of string which contains
    leading_escape = False
    expect_closing_bracket = False

    for char in string:
        # +1 to locate the current field position
        current_field_idx = len(fields) + 1
        is_list_str_field = current_field_idx in positions_list_str

        if leading_escape:
            if char not in escape_chars:
                # leading escape is considered as a literal
                field.append(ESCAPE)
            field.append(char)
            leading_escape = False
            continue

        if char == ESCAPE and not is_list_str_field:
            leading_escape = True
            continue

        if char == delimiter:
            if is_list_str_field and expect_closing_bracket:
                # delimiter occurs in the field with type:list[str]
                field.append(char)
            else:
                fields.append("".join(field))
                field = []
            continue

        if is_list_str_field:
            if char == "[":
                expect_closing_bracket = True
            if char == "]":
                expect_closing_bracket = False

        field.append(char)

    # add last field
    fields.append("".join(field))
    return fields


def is_newline_in_field(field: str) -> bool:
    """
    Check if the field contains a new line character.
    """
    return UNIX_NEWLINE in field
