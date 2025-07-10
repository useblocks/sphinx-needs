from dataclasses import dataclass
from enum import Enum
import logging
import os

from sphinx_codelinks.virtual_docs.config import (
    ESCAPE,
    SUPPORTED_COMMENT_TYPES,
    OneLineCommentStyle,
)

# initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# log to the console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)


class WarningSubTypeEnum(str, Enum):
    """Enum for warning sub types."""

    too_many_fields = "too_many_fields"
    too_few_fields = "too_few_fields"
    missing_square_brackets = "missing_square_brackets"
    not_start_or_end_with_square_brackets = "not_start_or_end_with_square_brackets"
    newline_in_field = "newline_in_field"


@dataclass
class OnelineParserInvalidWarning:
    """Invalid oneline comments."""

    sub_type: WarningSubTypeEnum
    msg: str


def oneline_parser(  # noqa: PLR0912, PLR0911 # handel warnings
    oneline: str, oneline_config: OneLineCommentStyle
) -> dict[str, str | list[str]] | OnelineParserInvalidWarning | None:
    """
    Extract the string from the custom one-line comment style with the following steps.

    - Locate the start and end sequences
    - extract the string between them
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

    # extract the string wrapped by start and end
    string = oneline[start_idx + len(oneline_config.start_sequence) : end_idx]

    # numbers of needs_fields which are required
    cnt_required_fields = oneline_config.get_cnt_required_fields()
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
            msg=f"{len(string_fields)} given fields. They shall be more than {min_fields}",
        )

    if len(string_fields) > max_fields:
        return OnelineParserInvalidWarning(
            sub_type=WarningSubTypeEnum.too_many_fields,
            msg=f"{len(string_fields)} given fields. They shall be less than {max_fields}",
        )
    resolved: dict[str, str | list[str]] = {}
    for idx in range(len(oneline_config.needs_fields)):
        field_name: str = oneline_config.needs_fields[idx]["name"]
        if len(string_fields) > idx:
            # given fields
            if is_newline_in_field(string_fields[idx]):
                # the case where the field contains a new line character
                return OnelineParserInvalidWarning(
                    sub_type=WarningSubTypeEnum.newline_in_field,
                    msg=f"Field {field_name} has newline character. It is not allowed",
                )
            if oneline_config.needs_fields[idx]["type"] == "str":
                resolved[field_name] = string_fields[idx]
            elif oneline_config.needs_fields[idx]["type"] == "list[str]":
                # find the indices of "[" and "]"
                start_idx = string_fields[idx].find("[")
                end_idx = string_fields[idx].rfind("]")
                if start_idx == -1 or end_idx == -1:
                    # brackets are not  found
                    return OnelineParserInvalidWarning(
                        sub_type=WarningSubTypeEnum.missing_square_brackets,
                        msg=f"Field {field_name} with 'type': '{oneline_config.needs_fields[idx]['type']}' must be given with '[]' brackets",
                    )

                if start_idx != 0 or end_idx != len(string_fields[idx]) - 1:
                    # brackets are found but not at the beginning and the end
                    return OnelineParserInvalidWarning(
                        sub_type=WarningSubTypeEnum.not_start_or_end_with_square_brackets,
                        msg=f"Field {field_name} with 'type': '{oneline_config.needs_fields[idx]['type']}' must start with '[' and end with ']'",
                    )

                string_items = string_fields[idx][start_idx + 1 : end_idx]

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
    return os.linesep in field


def get_file_types(comment_type: str) -> list[str] | None:
    """
    Get the list of file types to be discovered.
    """
    file_types = (
        list(SUPPORTED_COMMENT_TYPES)
        if comment_type in SUPPORTED_COMMENT_TYPES
        else None
    )
    return file_types
