"""Parameter data for test_schema_validations()."""

from typing import Optional

_bool_valid_base = [
    """
    [[needs.extra_options]]
    name = "accepted"
    [needs.extra_options.schema]
    type = "boolean"
    """,
    """
    .. feat:: title
        :id: FEAT_1
        :accepted: {value}
    """,
]
_bool_valid_params = {
    f"extra_option_type_boolean_{value}_valid": [
        _bool_valid_base[0],
        _bool_valid_base[1].format(value=value),
    ]
    for value in [
        "true",
        "True",
        "false",
        "False",
        "y",
        "Y",
        "n",
        "N",
        "1",
        "0",
        "on",
        "On",
        "off",
        "Off",
    ]
}

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
            :id: FEAT_1
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
           :id: FEAT_1
           :asil: QM
        """,
        [
            {"local_schema": {"required": ["asil"]}},
        ],
    ],
    "extra_option_cond_required_dep_missing_valid": [
        """
        [[needs.extra_options]]
        name = "asil"
        [[needs.extra_options]]
        name = "efforts"
        [needs.extra_options.schema]
        type = "integer"
        """,
        """
        .. feat:: title
           :id: FEAT_1
        """,
        [
            {
                "trigger_schema": {
                    "properties": {"efforts": {"minimum": 15}},
                    "required": ["efforts"],
                },
                "local_schema": {"required": ["asil"]},
            },
        ],
    ],
    "extra_option_cond_required_dep_min_valid": [
        """
        [needs]
        schemas_debug_active = true
        schemas_debug_ignore = []
        [[needs.extra_options]]
        name = "asil"
        [[needs.extra_options]]
        name = "efforts"
        [needs.extra_options.schema]
        type = "integer"
        """,
        """
        .. feat:: title
           :id: FEAT_1
           :efforts: 14
        """,
        [
            {
                "trigger_schema": {"properties": {"efforts": {"minimum": 15}}},
                "local_schema": {"required": ["asil"]},
            },
        ],
    ],
    "extra_option_cond_required_dep_min_invalid": [
        """
        [[needs.extra_options]]
        name = "asil"
        [[needs.extra_options]]
        name = "efforts"
        [needs.extra_options.schema]
        type = "integer"
        """,
        """
        .. feat:: title
           :id: FEAT_1
           :efforts: 16
        """,
        [
            {
                "trigger_schema": {"properties": {"efforts": {"minimum": 15}}},
                "local_schema": {"required": ["asil"]},
            },
        ],
        ["'asil' is a required property"],
        "sn_schema.validation_fail",
    ],
    "extra_option_required_invalid": [
        """
        [[needs.extra_options]]
        name = "asil"
        """,
        """
        .. feat:: title
           :id: FEAT_1
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
           :id: FEAT_1
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
            :id: FEAT_1
            :asil: QM
        """,
    ],
    "extra_option_type_integer_is_string_invalid": [
        """
        [[needs.extra_options]]
        name = "efforts"
        [needs.extra_options.schema]
        type = "integer"
        """,
        """
        .. feat:: title
            :id: FEAT_1
            :efforts: QM
        """,
        [],
        ["cannot coerce 'QM' to integer"],
        "sn_schema.option_type_error",
    ],
    "extra_option_type_integer_is_float_invalid": [
        """
        [[needs.extra_options]]
        name = "efforts"
        [needs.extra_options.schema]
        type = "integer"
        """,
        """
        .. feat:: title
            :id: FEAT_1
            :efforts: 1.2
        """,
        [],
        ["Field 'efforts': cannot coerce '1.2' to integer"],
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
            :id: FEAT_1
            :asil: QM
        """,
        [],
        ["cannot coerce 'QM' to boolean"],
        "sn_schema.option_type_error",
    ],
    **_bool_valid_params,
    "extra_option_type_boolean_True_valid": [
        """
        [[needs.extra_options]]
        name = "accepted"
        [needs.extra_options.schema]
        type = "boolean"
        """,
        """
        .. feat:: title
            :id: FEAT_1
            :accepted: True
        """,
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
            :id: FEAT_1
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
            :id: FEAT_1
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
            :id: FEAT_1
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
            :id: FEAT_1
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
            :id: FEAT_1
            :start_date: not-a-date
        """,
        [],
        [
            "properties > start_date > format",
            "'not-a-date' is not a 'date'",
        ],
        "sn_schema.validation_fail",
    ],
    "link_option_min_valid": [
        "",
        """
        .. spec:: title
            :id: SPEC_1

        .. impl:: title
            :id: IMPL_1
            :links: SPEC_1
        """,
        [
            {
                "types": ["impl"],
                "link_schema": {
                    "links": {
                        "minItems": 1,
                    }
                },
            }
        ],
    ],
    "link_option_min_invalid": [
        "",
        """
        .. spec:: title
            :id: SPEC_1

        .. impl:: title
            :id: IMPL_1
            :links: SPEC_1
        """,
        [
            {
                "types": ["impl"],
                "link_schema": {
                    "links": {
                        "minItems": 2,
                    }
                },
            }
        ],
        ["Need 'IMPL_1' has too few links of type 'links' (1 < 2)"],
        "sn_schema.too_few_links",
    ],
    "link_option_max_valid": [
        "",
        """
        .. spec:: title
            :id: SPEC_1

        .. impl:: title
            :id: IMPL_1
            :links: SPEC_1
        """,
        [
            {
                "types": ["impl"],
                "link_schema": {
                    "links": {
                        "maxItems": 1,
                    }
                },
            }
        ],
    ],
    "link_option_max_invalid": [
        "",
        """
        .. spec:: title
            :id: SPEC_1

        .. spec:: title
            :id: SPEC_2
            
        .. impl:: title
            :id: IMPL_1
            :links: SPEC_1, SPEC_2
        """,
        [
            {
                "types": ["impl"],
                "link_schema": {
                    "links": {
                        "maxItems": 1,
                    }
                },
            }
        ],
        ["Need 'IMPL_1' has too many links of type 'links' (2 > 1)"],
        "sn_schema.too_many_links",
    ],
    "link_chain_valid": [
        """
        [[needs.extra_options]]
        name = "asil"
        [needs.extra_options.schema]
        type = "string"
        enum = ["QM", "A", "B", "C", "D"]
        """,
        """
        .. feat:: safe feat
           :id: FEAT_SAFE
           :asil: C

        .. spec:: safe spec
           :id: SPEC_SAFE
           :asil: B
           :links: FEAT_SAFE

        .. impl:: safe impl
           :id: IMPL_SAFE
           :asil: A
           :links: SPEC_SAFE
        """,
        [
            {
                "id": "safe-need",
                "types": [],
                "trigger_schema": {},
                "local_schema": {
                    "properties": {"asil": {"enum": ["A", "B", "C", "D"]}},
                    "required": ["asil"],
                },
                "dependency": True,
            },
            {
                "id": "safe-feat",
                "types": ["feat"],
                "trigger_schema": {},
                "local_schema": {
                    "properties": {"asil": {"enum": ["A", "B", "C", "D"]}},
                    "required": ["asil"],
                },
                "dependency": True,
            },
            {
                "id": "safe-spec--links--safe-feat",
                "types": ["spec"],
                "trigger_schema_id": "safe-need",
                "link_schema": {
                    "links": {
                        "schema_id": "safe-feat",
                        "minItems": 1,
                        "maxItems": 4,
                    }
                },
            },
            {
                "id": "safe-impl--links--safe-req--links--safe-feat",
                "message": "Safe impl links to safe req to safe feat",
                "types": ["impl"],
                "trigger_schema_id": "safe-need",
                "link_schema": {
                    "links": {
                        "schema_id": "safe-spec--links--safe-feat",
                        "minItems": 1,
                    }
                },
            },
        ],
    ],
    "link_chain_hop_1_invalid": [
        """
        [[needs.extra_options]]
        name = "asil"
        [needs.extra_options.schema]
        type = "string"
        enum = ["QM", "A", "B", "C", "D"]
        """,
        """
        .. feat:: safe feat
           :id: FEAT_SAFE
           :asil: C

        .. spec:: safe spec
           :id: SPEC_UNSAFE
           :asil: QM
           :links: FEAT_SAFE

        .. impl:: safe impl
           :id: IMPL_SAFE
           :asil: A
           :links: SPEC_UNSAFE
        """,
        [
            {
                "id": "safe-need",
                "types": [],
                "trigger_schema": {},
                "local_schema": {
                    "properties": {"asil": {"enum": ["A", "B", "C", "D"]}},
                    "required": ["asil"],
                },
                "dependency": True,
            },
            {
                "id": "safe-feat",
                "types": ["feat"],
                "trigger_schema": {},
                "local_schema": {
                    "properties": {"asil": {"enum": ["A", "B", "C", "D"]}},
                    "required": ["asil"],
                },
                "dependency": True,
            },
            {
                "id": "safe-spec--links--safe-feat",
                "types": ["spec"],
                "trigger_schema_id": "safe-need",
                "link_schema": {
                    "links": {
                        "schema_id": "safe-feat",
                        "minItems": 1,
                        "maxItems": 4,
                    }
                },
                "dependency": True,
            },
            {
                "id": "safe-impl--links--safe-req--links--safe-feat",
                "message": "Safe impl links to safe req to safe feat",
                "types": ["impl"],
                "trigger_schema_id": "safe-need",
                "link_schema": {
                    "links": {
                        "schema_id": "safe-spec--links--safe-feat",
                        "minItems": 1,
                    }
                },
            },
        ],
        [
            "Need 'IMPL_SAFE' has validation errors",
            "Field: links",
            "Need path:",
            "IMPL_SAFE > links",
            "Schema path",
            "safe-impl--links--safe-req--links--safe-feat[3] > link_schema > links > schema_id[safe-spec--links--safe-feat]",
            "Schema message",
            "Too few valid links of type 'links' (0 < 1) / nok: SPEC_UNSAFE",
        ],
        "sn_schema.too_few_links",
    ],
    "link_chain_hop_2_invalid": [
        """
        [[needs.extra_options]]
        name = "asil"
        [needs.extra_options.schema]
        type = "string"
        enum = ["QM", "A", "B", "C", "D"]
        """,
        """
        .. feat:: safe feat
           :id: FEAT_UNSAFE
           :asil: QM

        .. spec:: safe spec
           :id: SPEC_SAFE
           :asil: B
           :links: FEAT_UNSAFE

        .. impl:: safe impl
           :id: IMPL_SAFE
           :asil: A
           :links: SPEC_SAFE
        """,
        [
            {
                "id": "safe-need",
                "types": [],
                "trigger_schema": {},
                "local_schema": {
                    "properties": {"asil": {"enum": ["A", "B", "C", "D"]}},
                    "required": ["asil"],
                },
                "dependency": True,
            },
            {
                "id": "safe-feat",
                "types": ["feat"],
                "trigger_schema": {},
                "local_schema": {
                    "properties": {"asil": {"enum": ["A", "B", "C", "D"]}},
                    "required": ["asil"],
                },
                "dependency": True,
            },
            {
                "id": "safe-spec--links--safe-feat",
                "types": ["spec"],
                "trigger_schema_id": "safe-need",
                "link_schema": {
                    "links": {
                        "schema_id": "safe-feat",
                        "minItems": 1,
                        "maxItems": 4,
                    }
                },
                "dependency": True,
            },
            {
                "id": "safe-impl--links--safe-req--links--safe-feat",
                "message": "Safe impl links to safe req to safe feat",
                "types": ["impl"],
                "trigger_schema_id": "safe-need",
                "link_schema": {
                    "links": {
                        "schema_id": "safe-spec--links--safe-feat",
                        "minItems": 1,
                    }
                },
            },
        ],
        [
            "Need 'IMPL_SAFE' has validation errors",
            "Field: links",
            "Need path:",
            "IMPL_SAFE > links",
            "Schema path",
            "safe-impl--links--safe-req--links--safe-feat[3] > link_schema > links > schema_id[safe-spec--links--safe-feat]",
            "Schema message",
            "Too few valid links of type 'links' (0 < 1) / nok: SPEC_SAFE",
        ],
        "sn_schema.too_few_links",
    ],
}

# structure:
# test_name, ubproject, rst_content, schemas_json, warnings
SCHEMA_CONFIG_ERROR_PARAMS: dict[
    str, list[str, str, str, Optional[list[dict]], str]
] = {
    "extra_option_missing_type": [
        """
        [[needs.extra_options]]
        name = "asil"
        [needs.extra_options.schema]
        format = "date"
        """,
        "",
        [],
        ["Missing types in schema definition for extra_options: asil"],
    ],
    "extra_option_missing_type_trigger_schema": [
        """
        [[needs.extra_options]]
        name = "efforts"
        """,
        "",
        [
            {
                "trigger_schema": {"properties": {"efforts": {"minimum": 15}}},
            },
        ],
        [
            "Schemas entry [0] is referencing extra option 'efforts' without a type specification"
        ],
    ],
    "extra_option_missing_type_local_schema": [
        """
        [[needs.extra_options]]
        name = "efforts"
        """,
        "",
        [
            {
                "local_schema": {"properties": {"efforts": {"minimum": 15}}},
            },
        ],
        [
            "Schemas entry [0] is referencing extra option 'efforts' without a type specification"
        ],
    ],
    "extra_option_broken_schema": [
        """
        [[needs.extra_options]]
        name = "efforts"
        [needs.extra_options.schema]
        type = "unknown_type"
        """,
        "",
        [],
        ["'unknown_type' is not valid under any of the given schemas"],
    ],
    "extra_option_broken_trigger_schema": [
        """
        [[needs.extra_options]]
        name = "efforts"
        """,
        "",
        [
            {
                "trigger_schema": {"properties": {"efforts": {"type": "unknown_type"}}},
            },
        ],
        ["'unknown_type' is not valid under any of the given schemas"],
    ],
    "extra_option_broken_local_schema": [
        """
        [[needs.extra_options]]
        name = "efforts"
        """,
        "",
        [
            {
                "local_schema": {"properties": {"efforts": {"type": "unknown_type"}}},
            },
        ],
        ["'unknown_type' is not valid under any of the given schemas"],
    ],
    "link_option_link_type_invalid": [
        "",
        "",
        [
            {
                "link_schema": {
                    "links2": {
                        "minItems": 2,
                    }
                }
            }
        ],
        ["Link type 'links2' in schema '[0]' is not defined in needs_extra_links"],
    ],
    "trigger_schema_id_invalid": [
        "",
        "",
        [
            {
                "trigger_schema_id": "invalid_id",
            }
        ],
        [
            "Schema '[0]' is referencing trigger_schema_id 'invalid_id' which does not exist"
        ],
    ],
    "link_schema_id_invalid": [
        "",
        "",
        [
            {
                "link_schema": {
                    "links": {
                        "schema_id": "invalid_id",
                    }
                }
            }
        ],
        [
            "Link type 'links' in schema '[0]' is referencing schema_id 'invalid_id' which does not exist"
        ],
    ],
}
