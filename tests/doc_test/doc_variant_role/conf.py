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
