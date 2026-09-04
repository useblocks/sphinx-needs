extensions = ["sphinx_needs"]

needs_table_style = "TABLE"

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


def my_custom_warning_check(need, log):
    if need["status"] == "open":
        log.info(f"{need['id']} status must not be 'open'.")
        return True
    return False


needs_warnings = {
    "invalid_status": "status not in ['open', 'closed', 'done', 'example_2', 'example_3']",
    "type_match": my_custom_warning_check,
}


# Needs option to set True or False to raise sphinx-warning for each not passed warning check
# default is False
needs_warnings_always_warn = True
