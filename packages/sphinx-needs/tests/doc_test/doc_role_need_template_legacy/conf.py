extensions = ["sphinx_needs"]

needs_types = [
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
        "style": "node",
    },
]

# Legacy str.format-style template (pre-Jinja). Must keep working, with a
# deprecation warning, so existing configs are not silently broken.
needs_role_need_template = "[{id}] {title} ({status})"
