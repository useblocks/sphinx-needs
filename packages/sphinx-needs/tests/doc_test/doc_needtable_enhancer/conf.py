"""A project whose needtables exercise the whole markup contract.

Twelve needs, one of them with parts, a numeric field, an ISO-date field, links, a
``:style_row:`` class, ``:colwidths:``, ``:show_filters:`` -- and a second table in the
plain ``:style: table`` style, which the client-side enhancer must leave alone.
"""

extensions = ["sphinx_needs"]

# a stylesheet that does to bare elements what real host themes were measured doing; the
# widget has to be unmoved by it, and `test_the_host_fence_holds` asserts that it is
html_static_path = ["_static"]
html_css_files = ["hostile.css"]

needs_id_regex = "^[A-Za-z0-9_]+"

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

needs_fields = {
    # a genuinely numeric field, so the header can declare `data-type="number"`
    "amount": {"schema": {"type": "integer"}, "nullable": True},
    # a date field the producer does NOT type, so the script has to detect it
    "due": {"nullable": True},
}
