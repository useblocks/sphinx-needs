extensions = ["sphinx_needs"]

needs_types = [
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
    }
]

needs_extra_links = [
    {
        "option": "link1",
        "incoming": "is linked by",
        "outgoing": "links to",
    },
    {
        "option": "link2",
        "incoming": "is linked by",
        "outgoing": "links to",
    },
    {
        "option": "link3",
        "incoming": "is linked by",
        "outgoing": "links to",
    },
]

needs_extra_options = [
    "option_1",
    "option_2",
    "option_3",
    "option_4",
    "option_5",
    "bad_value_type",
    "too_many_params",
]

needs_global_options = {
    "layout": "clean_l",
    "option_1": "test_global",
    "option_2": "[[copy('id')]]",
    "option_3": ("STATUS_IMPL", 'status == "implemented"'),
    "option_4": ("STATUS_CLOSED", 'status == "closed"', "STATUS_UNKNOWN"),
    "option_5": [
        ("STATUS_IMPL", 'status == "implemented"', "bad"),
        ("STATUS_CLOSED", 'status == "closed"', "final"),
    ],
    "link1": "SPEC_1",
    "link2": [
        ("SPEC_2,[[copy('link1')", 'status == "implemented"'),
        ("SPEC_3", 'status == "closed"', ["SPEC_1"]),
    ],
    "link3": 1,
    "tags": [
        ("a,b", 'status == "implemented"'),
        ("c", 'status == "closed"', ["d"]),
    ],
    "bad_value_type": 1.27,
    "too_many_params": ("a", "b", "c", "d"),
    "unknown": "unknown",
}

needs_build_json = True
needs_json_remove_defaults = True
