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

# Deliberately broken Jinja (unclosed expression) to exercise the
# compile-time fallback path in process_need_ref.
needs_role_need_template = "[{{ id }] {{ title }}"
