extensions = ["sphinx_needs"]

needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "REQ_",
        "color": "#BFD8D2",
        "style": "node",
    },
]

needs_variant_data = {
    "platform": "arm",
    "build": {
        "debug": True,
        "opt_level": 2,
    },
    "archs": ["arm", "x86"],
}

needs_fields = {
    "mystring": {
        "schema": {"type": "string"},
        "parse_variants": True,
        "nullable": True,
    },
    "myint": {"schema": {"type": "integer"}, "parse_variants": True, "nullable": True},
    "myarray": {
        "schema": {"type": "array", "items": {"type": "string"}},
        "parse_variants": True,
        "nullable": True,
    },
}

needs_build_json = True
needs_json_remove_defaults = True
