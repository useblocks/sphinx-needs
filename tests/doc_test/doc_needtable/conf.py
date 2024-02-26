extensions = ["sphinx_needs"]

needs_table_style = "TABLE"

needs_id_regex = "^[A-Za-z0-9_]"

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

needs_extra_options = [
    "my_extra_option",
    "another_option",
    "author",
    "comment",
    "amount",
    "hours",
    "image",
    "config",
    "github",
    "value",
    "unit",
    "special-chars!",
]

needs_string_links = {
    "config_link": {
        "regex": r"^(?P<value>\w+)$",
        "link_url": 'https://sphinxcontrib-needs.readthedocs.io/en/latest/configuration.html#{{value | replace("_", "-")}}',
        "link_name": 'Sphinx-Needs docs for {{value | replace("_", "-") }}',
        "options": ["config"],
    },
    "github_link": {
        "regex": r"^(?P<value>\w+)$",
        "link_url": "https://github.com/useblocks/sphinxcontrib-needs/issues/{{value}}",
        "link_name": "GitHub #{{value}}",
        "options": ["github"],
    },
}
