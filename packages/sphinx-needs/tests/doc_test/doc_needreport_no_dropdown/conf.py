# Deliberately no extension providing a ``dropdown`` directive, and deliberately
# no ``needs_render_context``: this project renders the packaged default template
# with the built-in ``report_directive``, which is the configuration issue #899
# reports and the one the rest of the test suite never exercises.
extensions = ["sphinx_needs"]

needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "R_",
        "color": "#BFD8D2",
        "style": "node",
    },
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "S_",
        "color": "#FEDCD2",
        "style": "node",
    },
]

needs_links = {
    "blocks": {
        "incoming": "is blocked by",
        "outgoing": "blocks",
    },
}

needs_fields = {"priority": {"nullable": True}}

needs_external_needs = [
    {
        "base_url": "http://my_company.com/docs/v1/",
        "json_path": "external_reqs.json",
        "id_prefix": "ext_",
    },
]
