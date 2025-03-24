extensions = ["sphinx_needs"]

needs_build_json = True
needs_json_remove_defaults = True

needs_id_regex = "^[A-Za-z0-9_]+"

needs_extra_options = ["author"]

needs_extra_links = [
    {"option": "checks", "incoming": "is checked by", "outgoing": "checks"},
    {"option": "triggers", "incoming": "is triggered by", "outgoing": "triggers"},
    {"option": "blocks", "incoming": "is blocked by", "outgoing": "blocks"},
    {"option": "tests", "incoming": "is tested by", "outgoing": "tests"},
]
