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
        "default": ["SPEC_1"],
    },
    {
        "option": "link2",
        "incoming": "is linked by",
        "outgoing": "links to",
        "predicates": [
            ('status == "implemented"', ["SPEC_2", "[[copy('link1')]]"]),
            ('status == "closed"', ["SPEC_3"]),
        ],
        "default": ["SPEC_1"],
    },
    {
        "option": "link3",
        "incoming": "is linked by",
        "outgoing": "links to",
        "default": 1,
    },
]

needs_fields = {
    "tags": {
        "predicates": [
            ('status == "implemented"', ["a", "b"]),
            ('status == "closed"', ["c", "[[copy('status')]]"]),
        ],
        "default": ["d"],
    },
    "collapse": {"default": True},
    "hide": {"default": False},
    "layout": {"default": "clean_l"},
    "option_1": {"default": "test_global"},
    "option_2": {"default": "[[copy('id')]]"},
    "option_3": {
        "nullable": True,
        "predicates": [('status == "implemented"', "STATUS_IMPL")],
    },
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
    "bad_value_type": {"default": 1.27},
    "too_many_params": {"nullable": True, "predicates": [("a", "b", "c", "d")]},
}

needs_build_json = True
needs_json_remove_defaults = True
needs_json_exclude_fields = [
    "id_complete",
    "id_parent",
    "lineno_content",
    "type_color",
    "type_prefix",
    "type_style",
]
