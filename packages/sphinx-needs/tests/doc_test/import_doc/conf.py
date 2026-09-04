version = "1.0"

extensions = ["sphinx_needs"]

needs_id_regex = "^[A-Za-z0-9_]"

needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "RE_",
        "color": "#BFD8D2",
        "style": "node",
    },
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

needs_import_keys = {"key": "needs_test.json"}

needs_template = """
.. _{{id}}:

{% if hide == false -%}
{{type_name}}: **{{title}}** ({{id}})
    {%- if status and  status|upper != "NONE" %}
    | status: {{status}}
    {%- endif -%}
    {%- if tags %}
    | tags: {{tags|join("; ")}}
    {%- endif %}
    | links incoming: :need_incoming:`{{id}}`
    | links outgoing: :need_outgoing:`{{id}}`

    {{content|indent(4) }}

{% endif -%}
"""

needs_json_remove_defaults = True
