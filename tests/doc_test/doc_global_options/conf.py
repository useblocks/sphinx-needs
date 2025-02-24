extensions = ["sphinx_needs"]

needs_types = [
    {
        "directive": "story",
        "title": "User Story",
        "prefix": "US_",
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
    {
        "directive": "impl",
        "title": "Implementation",
        "prefix": "IM_",
        "color": "#DF744A",
        "style": "node",
    },
    {
        "directive": "test",
        "title": "Test Case",
        "prefix": "TC_",
        "color": "#DCB239",
        "style": "node",
    },
]

needs_extra_options = ["global_1", "global_2", "global_3", "global_4"]

needs_global_options = {
    "global_1": "test_global",
    "global_2": 1.27,
    "global_3": "[[test()]]",
    "global_4": ("STATUS_IMPL", 'status == "implemented"'),
    "global_5": ("STATUS_CLOSED", 'status == "closed"', "STATUS_UNKNOWN"),
}

needs_build_json = True
needs_json_remove_defaults = True
