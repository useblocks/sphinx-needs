"""Parameter data for test_schema_validations()."""

from typing import Optional

# structure:
# test_name, ubproject, rst_content, schemas_json, warnings, warning_type
SCHEMA_VALIDATION_PARAMS: dict[
    str, list[str, str, str, Optional[list[dict]], Optional[list[str]], Optional[str]]
] = {
    "extra_option_valid": [
        """
        [[needs.extra_options]]
        name = "asil"
        """,
        """
        .. feat:: title
            :id: FEAT_01
            :asil: QM
        """,
    ],
    "extra_option_required_valid": [
        """
        [[needs.extra_options]]
        name = "asil"
        """,
        """
        .. feat:: title
           :id: FEAT_01
        """,
        [
            {"local_schema": {"required": ["asil"]}},
        ],
        ["allOf > 0 > required", "'asil' is a required property"],
        "sn_schema.validation_fail",
    ],
    "format_date_invalid": [
        """
        [[needs.extra_options]]
        name = "start_date"
        [needs.extra_options.schema]
        type = "string"
        format = "date"
        """,
        """
        .. feat:: title
           :id: FEAT_01
           :start_date: not-a-date
        """,
        [],
        [
            "properties > start_date > format",
            "'not-a-date' is not a 'date'",
        ],
        "sn_schema.validation_fail",
    ],
    "extra_option_type_string_valid": [
        """
        [[needs.extra_options]]
        name = "asil"
        [needs.extra_options.schema]
        type = "string"
        """,
        """
        .. feat:: title
            :id: FEAT_01
            :asil: QM
        """,
    ],
    "extra_option_type_integer_invalid": [
        """
        [[needs.extra_options]]
        name = "asil"
        [needs.extra_options.schema]
        type = "integer"
        """,
        """
        .. feat:: title
            :id: FEAT_01
            :asil: QM
        """,
        [],
        ["cannot coerce 'QM' to integer"],
        "sn_schema.option_type_error",
    ],
    "extra_option_type_boolean_invalid": [
        """
        [[needs.extra_options]]
        name = "asil"
        [needs.extra_options.schema]
        type = "boolean"
        """,
        """
        .. feat:: title
            :id: FEAT_01
            :asil: QM
        """,
        [],
        ["cannot coerce 'QM' to boolean"],
        "sn_schema.option_type_error",
    ],
    "extra_option_type_number_invalid": [
        """
        [[needs.extra_options]]
        name = "asil"
        [needs.extra_options.schema]
        type = "number"
        """,
        """
        .. feat:: title
            :id: FEAT_01
            :asil: QM
        """,
        [],
        ["cannot coerce 'QM' to number"],
        "sn_schema.option_type_error",
    ],
    "extra_option_enum_valid": [
        """
        [[needs.extra_options]]
        name = "asil"
        [needs.extra_options.schema]
        type = "string"
        enum = ["QM", "A", "B", "C", "D"]
        """,
        """
        .. feat:: title
            :id: FEAT_01
            :asil: QM
        """,
    ],
    "extra_option_enum_invalid": [
        """
        [[needs.extra_options]]
        name = "asil"
        [needs.extra_options.schema]
        type = "string"
        enum = ["QM", "A", "B", "C", "D"]
        """,
        """
        .. feat:: title
            :id: FEAT_01
            :asil: E
        """,
        [],
        [
            "properties > asil > enum",
            "'E' is not one of ['QM', 'A', 'B', 'C', 'D']",
        ],
        "sn_schema.validation_fail",
    ],
    "extra_option_format_date_valid": [
        """
        [[needs.extra_options]]
        name = "start_date"
        [needs.extra_options.schema]
        type = "string"
        format = "date"
        """,
        """
        .. feat:: title
            :id: FEAT_01
            :start_date: 2023-01-01
        """,
    ],
    "extra_option_format_date_invalid": [
        """
        [[needs.extra_options]]
        name = "start_date"
        [needs.extra_options.schema]
        type = "string"
        format = "date"
        """,
        """
        .. feat:: title
            :id: FEAT_01
            :start_date: not-a-date
        """,
        [],
        [
            "properties > start_date > format",
            "'not-a-date' is not a 'date'",
        ],
        "sn_schema.validation_fail",
    ],
}
