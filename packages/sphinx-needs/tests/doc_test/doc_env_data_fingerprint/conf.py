import os
import sys

# the local extension lives beside this file; each build imports it from its own copy of
# the project
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("env_fingerprint_ext", None)

extensions = ["sphinx_needs", "sphinxcontrib.plantuml", "env_fingerprint_ext"]

needs_fields = {
    "effort": {"schema": {"type": "integer"}},
    # a derived field: computed, by its rule, for every req
    "linked": {
        "schema": {"type": "integer"},
        "derive_by_type": {"req": {"kind": "count", "over": "links"}},
    },
}
needs_links = {"tests": {"incoming": "tested by", "outgoing": "tests"}}
needs_external_needs = [
    {"base_url": "http://example.org", "json_path": "ext.json", "id_prefix": "EXT_"}
]
needs_variants = {"full": "tags and 'a' in tags"}
needs_variant_data = {"arch": "arm"}
needs_render_context = {"report_directive": "admonition"}
needs_schema_definitions = {
    "schemas": [
        {
            "id": "spec-links",
            "select": {"properties": {"type": {"const": "spec"}}},
            "validate": {
                "local": {"properties": {"id": {"pattern": "^SPEC_[A-Z0-9_]+$"}}},
                "network": {
                    "links": {
                        "items": {"local": {"properties": {"type": {"const": "req"}}}}
                    }
                },
            },
        }
    ]
}
# a need type's own declarations: a field, back links, and a link type of its own
needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "R_",
        "fields": {"owner": {"schema": {"type": "string"}}},
        "back_links": {
            "links": {"description": "the specs", "schema": {"minItems": 0}}
        },
        "links": {"refines": {"incoming": "refined by", "outgoing": "refines"}},
    },
    {"directive": "spec", "title": "Specification", "prefix": "S_"},
]
