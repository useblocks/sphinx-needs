"""Tests for populate_field_type function in config_utils."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs.needs_schema import FieldSchema, FieldsSchema, LinkSchema
from sphinx_needs.schema.config_utils import populate_field_type


def create_mock_fields_schema(
    extra_fields: dict[str, tuple[str, str | None]] | None = None,
    link_fields: dict[str, tuple[str, str]] | None = None,
    core_fields: dict[str, tuple[str, str | None]] | None = None,
) -> FieldsSchema:
    """Create a mock FieldsSchema with specified fields.

    :param extra_fields: dict of field_name -> (type, item_type)
    :param link_fields: dict of field_name -> (type, item_type)
    :param core_fields: dict of field_name -> (type, item_type)
    """
    mock = MagicMock(spec=FieldsSchema)

    extra_fields = extra_fields or {}
    link_fields = link_fields or {}
    core_fields = core_fields or {}

    def get_extra_field(name: str) -> FieldSchema | None:
        if name in extra_fields:
            field_type, item_type = extra_fields[name]
            field = MagicMock(spec=FieldSchema)
            field.type = field_type
            field.item_type = item_type
            return field
        return None

    def get_link_field(name: str) -> LinkSchema | None:
        if name in link_fields:
            field_type, item_type = link_fields[name]
            field = MagicMock(spec=LinkSchema)
            field.type = field_type
            field.item_type = item_type
            return field
        return None

    def get_core_field(name: str) -> FieldSchema | None:
        if name in core_fields:
            field_type, item_type = core_fields[name]
            field = MagicMock(spec=FieldSchema)
            field.type = field_type
            field.item_type = item_type
            return field
        return None

    mock.get_extra_field = get_extra_field
    mock.get_link_field = get_link_field
    mock.get_core_field = get_core_field

    return mock


class TestPopulateFieldTypeSuccess:
    """Test successful type injection scenarios."""

    def test_empty_schema(self) -> None:
        """Test schema with only idx (minimal valid structure)."""
        schema: dict[str, Any] = {"idx": 0, "validate": {}}
        fields_schema = create_mock_fields_schema()

        populate_field_type(schema, "[0]", fields_schema)

        # No changes expected
        assert schema == {"idx": 0, "validate": {}}

    def test_select_with_properties_injects_object_type(self) -> None:
        """Test that select with properties gets type='object' injected."""
        schema: dict[str, Any] = {
            "idx": 0,
            "select": {"properties": {}},
            "validate": {},
        }
        fields_schema = create_mock_fields_schema()

        populate_field_type(schema, "[0]", fields_schema)

        assert schema["select"]["type"] == "object"

    def test_validate_local_with_properties_injects_object_type(self) -> None:
        """Test that validate.local with properties gets type='object' injected."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {"local": {"properties": {}}},
        }
        fields_schema = create_mock_fields_schema()

        populate_field_type(schema, "[0]", fields_schema)

        assert schema["validate"]["local"]["type"] == "object"

    def test_extra_field_type_injection(self) -> None:
        """Test type injection for extra option fields."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "priority": {},
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            extra_fields={"priority": ("string", None)}
        )

        populate_field_type(schema, "[0]", fields_schema)

        assert schema["validate"]["local"]["properties"]["priority"]["type"] == "string"

    def test_extra_field_array_type_injection(self) -> None:
        """Test type injection for array extra option fields with items."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "categories": {"items": {}},
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            extra_fields={"categories": ("array", "string")}
        )

        populate_field_type(schema, "[0]", fields_schema)

        props = schema["validate"]["local"]["properties"]["categories"]
        assert props["type"] == "array"
        assert props["items"]["type"] == "string"

    def test_extra_field_array_contains_injection(self) -> None:
        """Test type injection for array extra option fields with contains."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "tags": {"contains": {}},
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            extra_fields={"tags": ("array", "string")}
        )

        populate_field_type(schema, "[0]", fields_schema)

        props = schema["validate"]["local"]["properties"]["tags"]
        assert props["type"] == "array"
        assert props["contains"]["type"] == "string"

    def test_link_field_type_injection(self) -> None:
        """Test type injection for link fields."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "links": {},
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            link_fields={"links": ("array", "string")}
        )

        populate_field_type(schema, "[0]", fields_schema)

        assert schema["validate"]["local"]["properties"]["links"]["type"] == "array"

    def test_link_field_items_type_injection(self) -> None:
        """Test type injection for link fields with items."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "links": {"items": {}},
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            link_fields={"links": ("array", "string")}
        )

        populate_field_type(schema, "[0]", fields_schema)

        props = schema["validate"]["local"]["properties"]["links"]
        assert props["type"] == "array"
        assert props["items"]["type"] == "string"

    def test_core_field_from_fields_schema(self) -> None:
        """Test type injection for core fields from FieldsSchema."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "status": {},
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            core_fields={"status": ("string", None)}
        )

        populate_field_type(schema, "[0]", fields_schema)

        assert schema["validate"]["local"]["properties"]["status"]["type"] == "string"

    def test_core_field_fallback_to_needs_core_fields(self) -> None:
        """Test type injection for core fields via NeedsCoreFields fallback."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "id": {},  # 'id' is a known core field
                    }
                }
            },
        }
        # Empty fields_schema - will fallback to NeedsCoreFields
        fields_schema = create_mock_fields_schema()

        populate_field_type(schema, "[0]", fields_schema)

        # 'id' should get type='string' from NeedsCoreFields
        assert schema["validate"]["local"]["properties"]["id"]["type"] == "string"

    def test_network_link_array_type_injection(self) -> None:
        """Test type='array' injection for network resolved links."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "network": {
                    "links": {},
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            link_fields={"links": ("array", "string")}
        )

        populate_field_type(schema, "[0]", fields_schema)

        assert schema["validate"]["network"]["links"]["type"] == "array"

    def test_network_items_recursive_processing(self) -> None:
        """Test recursive processing of network items."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "network": {
                    "links": {
                        "items": {
                            "local": {
                                "properties": {
                                    "priority": {},
                                }
                            }
                        }
                    },
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            link_fields={"links": ("array", "string")},
            extra_fields={"priority": ("integer", None)},
        )

        populate_field_type(schema, "[0]", fields_schema)

        # Check network link gets array type
        assert schema["validate"]["network"]["links"]["type"] == "array"
        # Check nested local properties get processed
        nested_props = schema["validate"]["network"]["links"]["items"]["local"][
            "properties"
        ]
        assert nested_props["priority"]["type"] == "integer"

    def test_network_contains_recursive_processing(self) -> None:
        """Test recursive processing of network contains."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "network": {
                    "links": {
                        "contains": {
                            "local": {
                                "properties": {
                                    "status": {},
                                }
                            }
                        }
                    },
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            link_fields={"links": ("array", "string")},
            core_fields={"status": ("string", None)},
        )

        populate_field_type(schema, "[0]", fields_schema)

        # Check nested contains local properties get processed
        nested_props = schema["validate"]["network"]["links"]["contains"]["local"][
            "properties"
        ]
        assert nested_props["status"]["type"] == "string"

    def test_allof_recursive_processing(self) -> None:
        """Test recursive processing of allOf entries."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "allOf": [
                        {"properties": {"field1": {}}},
                        {"properties": {"field2": {}}},
                    ]
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            extra_fields={
                "field1": ("string", None),
                "field2": ("integer", None),
            }
        )

        populate_field_type(schema, "[0]", fields_schema)

        all_of = schema["validate"]["local"]["allOf"]
        assert all_of[0]["properties"]["field1"]["type"] == "string"
        assert all_of[1]["properties"]["field2"]["type"] == "integer"

    def test_existing_correct_type_preserved(self) -> None:
        """Test that existing correct type is preserved."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "priority": {"type": "string"},
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            extra_fields={"priority": ("string", None)}
        )

        populate_field_type(schema, "[0]", fields_schema)

        assert schema["validate"]["local"]["properties"]["priority"]["type"] == "string"

    def test_ref_skipped(self) -> None:
        """Test that $ref entries are skipped (should be resolved before this)."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {"$ref": "#/$defs/something"},
            },
        }
        fields_schema = create_mock_fields_schema()

        # Should not raise, just skip
        populate_field_type(schema, "[0]", fields_schema)

        assert schema["validate"]["local"] == {"$ref": "#/$defs/something"}

    def test_missing_validate_is_safe(self) -> None:
        """Test that missing validate field doesn't crash."""
        schema: dict[str, Any] = {"idx": 0}
        fields_schema = create_mock_fields_schema()

        # Should not raise
        populate_field_type(schema, "[0]", fields_schema)

    def test_non_dict_values_ignored(self) -> None:
        """Test that non-dict values in unexpected places are safely ignored."""
        schema: dict[str, Any] = {
            "idx": 0,
            "select": "not a dict",  # Malformed but should be ignored
            "validate": {"local": "also not a dict"},
        }
        fields_schema = create_mock_fields_schema()

        # Should not raise - defensive checks should skip non-dicts
        populate_field_type(schema, "[0]", fields_schema)


class TestPopulateFieldTypeFailure:
    """Test error handling scenarios."""

    def test_unknown_field_raises_error(self) -> None:
        """Test that unknown field in properties raises NeedsConfigException."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "unknown_field": {},
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema()

        with pytest.raises(NeedsConfigException) as exc_info:
            populate_field_type(schema, "[0]", fields_schema)

        assert "unknown_field" in str(exc_info.value)
        assert "not a known extra option, extra link, or core field" in str(
            exc_info.value
        )

    def test_type_mismatch_extra_field(self) -> None:
        """Test that type mismatch for extra field raises error."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "priority": {"type": "integer"},  # Wrong type
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            extra_fields={"priority": ("string", None)}
        )

        with pytest.raises(NeedsConfigException) as exc_info:
            populate_field_type(schema, "[0]", fields_schema)

        assert "priority" in str(exc_info.value)
        assert "has type 'integer'" in str(exc_info.value)
        assert "expected 'string'" in str(exc_info.value)

    def test_type_mismatch_link_field(self) -> None:
        """Test that type mismatch for link field raises error."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "links": {"type": "string"},  # Should be array
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            link_fields={"links": ("array", "string")}
        )

        with pytest.raises(NeedsConfigException) as exc_info:
            populate_field_type(schema, "[0]", fields_schema)

        assert "links" in str(exc_info.value)
        assert "has type 'string'" in str(exc_info.value)
        assert "expected 'array'" in str(exc_info.value)

    def test_item_type_mismatch(self) -> None:
        """Test that item type mismatch raises error."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "tags": {
                            "items": {"type": "integer"},  # Should be string
                        },
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            extra_fields={"tags": ("array", "string")}
        )

        with pytest.raises(NeedsConfigException) as exc_info:
            populate_field_type(schema, "[0]", fields_schema)

        assert "tags" in str(exc_info.value)
        assert "items.type 'integer'" in str(exc_info.value)
        assert "expected 'string'" in str(exc_info.value)

    def test_contains_type_mismatch(self) -> None:
        """Test that contains type mismatch raises error."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "categories": {
                            "contains": {"type": "boolean"},  # Should be string
                        },
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            extra_fields={"categories": ("array", "string")}
        )

        with pytest.raises(NeedsConfigException) as exc_info:
            populate_field_type(schema, "[0]", fields_schema)

        assert "categories" in str(exc_info.value)
        assert "contains.type 'boolean'" in str(exc_info.value)
        assert "expected 'string'" in str(exc_info.value)

    def test_object_type_conflict_with_properties(self) -> None:
        """Test that type != 'object' with properties keyword raises error."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "type": "array",  # Conflict with properties
                    "properties": {},
                }
            },
        }
        fields_schema = create_mock_fields_schema()

        with pytest.raises(NeedsConfigException) as exc_info:
            populate_field_type(schema, "[0]", fields_schema)

        assert "object keywords" in str(exc_info.value)
        assert "type is 'array'" in str(exc_info.value)
        assert "expected 'object'" in str(exc_info.value)

    def test_error_includes_path(self) -> None:
        """Test that error messages include the schema path."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "network": {
                    "links": {
                        "items": {
                            "local": {
                                "properties": {
                                    "unknown": {},
                                }
                            }
                        }
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            link_fields={"links": ("array", "string")}
        )

        with pytest.raises(NeedsConfigException) as exc_info:
            populate_field_type(schema, "test_schema[0]", fields_schema)

        error_msg = str(exc_info.value)
        assert "test_schema[0]" in error_msg
        assert "validate.network.links.items.local.properties.unknown" in error_msg


class TestPopulateFieldTypeEdgeCases:
    """Test edge cases and defensive behavior."""

    def test_deeply_nested_allof(self) -> None:
        """Test deeply nested allOf structures."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "allOf": [
                        {
                            "allOf": [
                                {"properties": {"deep_field": {}}},
                            ]
                        },
                    ]
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            extra_fields={"deep_field": ("boolean", None)}
        )

        populate_field_type(schema, "[0]", fields_schema)

        deep_props = schema["validate"]["local"]["allOf"][0]["allOf"][0]["properties"]
        assert deep_props["deep_field"]["type"] == "boolean"

    def test_multiple_fields_in_properties(self) -> None:
        """Test multiple fields processed correctly."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {
                    "properties": {
                        "field1": {},
                        "field2": {},
                        "field3": {"items": {}},
                    }
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            extra_fields={
                "field1": ("string", None),
                "field2": ("integer", None),
                "field3": ("array", "number"),
            }
        )

        populate_field_type(schema, "[0]", fields_schema)

        props = schema["validate"]["local"]["properties"]
        assert props["field1"]["type"] == "string"
        assert props["field2"]["type"] == "integer"
        assert props["field3"]["type"] == "array"
        assert props["field3"]["items"]["type"] == "number"

    def test_select_and_validate_both_processed(self) -> None:
        """Test both select and validate are processed."""
        schema: dict[str, Any] = {
            "idx": 0,
            "select": {"properties": {"type": {}}},
            "validate": {
                "local": {"properties": {"status": {}}},
            },
        }
        fields_schema = create_mock_fields_schema(
            core_fields={
                "type": ("string", None),
                "status": ("string", None),
            }
        )

        populate_field_type(schema, "[0]", fields_schema)

        assert schema["select"]["properties"]["type"]["type"] == "string"
        assert schema["validate"]["local"]["properties"]["status"]["type"] == "string"

    def test_network_multiple_link_types(self) -> None:
        """Test multiple link types in network."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "network": {
                    "links": {},
                    "parent": {},
                }
            },
        }
        fields_schema = create_mock_fields_schema(
            link_fields={
                "links": ("array", "string"),
                "parent": ("array", "string"),
            }
        )

        populate_field_type(schema, "[0]", fields_schema)

        assert schema["validate"]["network"]["links"]["type"] == "array"
        assert schema["validate"]["network"]["parent"]["type"] == "array"

    def test_empty_properties_dict(self) -> None:
        """Test empty properties dict is handled."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {"properties": {}},
            },
        }
        fields_schema = create_mock_fields_schema()

        populate_field_type(schema, "[0]", fields_schema)

        assert schema["validate"]["local"]["type"] == "object"
        assert schema["validate"]["local"]["properties"] == {}

    def test_required_without_properties(self) -> None:
        """Test required keyword alone triggers object type injection."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {"required": ["field1"]},
            },
        }
        fields_schema = create_mock_fields_schema()

        populate_field_type(schema, "[0]", fields_schema)

        assert schema["validate"]["local"]["type"] == "object"

    def test_unevaluated_properties_triggers_object_type(self) -> None:
        """Test unevaluatedProperties keyword triggers object type injection."""
        schema: dict[str, Any] = {
            "idx": 0,
            "validate": {
                "local": {"unevaluatedProperties": False},
            },
        }
        fields_schema = create_mock_fields_schema()

        populate_field_type(schema, "[0]", fields_schema)

        assert schema["validate"]["local"]["type"] == "object"
