extensions = ["sphinx_needs"]

needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "REQ_",
        "color": "#BFD8D2",
        "style": "node",
    },
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
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

needs_fields = {"platform": {"nullable": True}}

needs_warnings = {
    "wrong_platform": "platform is not None and var.platform != platform",
}

needs_warnings_always_warn = True
