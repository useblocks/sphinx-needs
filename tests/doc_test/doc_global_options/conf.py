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
    "layout": {"default": "clean_l"},
    "option_1": {"default": "test_global"},
    "option_2": {"default": "[[copy('id')]]"},
    "option_3": {"predicates": [('status == "implemented"', "STATUS_IMPL")]},
    "option_4": {
        "default": "STATUS_UNKNOWN",
        "predicates": [('status == "closed"', "STATUS_CLOSED")],
    },
    "option_5": {
        "predicates": [
            ('status == "implemented"', "STATUS_IMPL"),
            ('status == "closed"', "STATUS_CLOSED"),
        ],
        "default": "final",
    },
    "link1": {"default": ["SPEC_1"]},
    "link2": {
        "predicates": [
            ('status == "implemented"', ["SPEC_2", "[[copy('link1')]]"]),
            ('status == "closed"', ["SPEC_3"]),
        ],
        "default": ["SPEC_1"],
    },
    "tags": {
        "predicates": [
            ('status == "implemented"', ["a", "b"]),
            ('status == "closed"', ["c"]),
        ],
        "default": ["d"],
    },
    "link3": {"default": 1},
    "bad_value_type": {"default": 1.27},
    "too_many_params": {"predicates": [("a", "b", "c", "d")]},
    "unknown": {"default": "unknown"},
}

needs_build_json = True
needs_json_remove_defaults = True
