from sphinx_needs.schema.config import NeedFieldsSchemaWithVersionType


def get_properties_from_schema(
    schema: NeedFieldsSchemaWithVersionType,
) -> set[str]:
    """
    Extract a list of property names from a given JSON schema.

    It searches both the top-level "properties" and any nested properties in "allOf" schemas.
    """
    properties: set[str] = set()

    # Extract properties in the main "properties" field
    if "properties" in schema and isinstance(schema["properties"], dict):
        properties.update(schema["properties"].keys())

    # If there is an "allOf" key with additional schemas, extract their properties as well
    if "allOf" in schema and isinstance(schema["allOf"], list):
        for subschema in schema["allOf"]:
            assert "$ref" not in subschema, "$ref have already been resolved"
            if "properties" in subschema and isinstance(subschema["properties"], dict):
                properties.update(subschema["properties"].keys())

    return properties
