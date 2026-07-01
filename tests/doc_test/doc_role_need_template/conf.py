extensions = ["sphinx_needs"]

needs_build_json = True

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

# Exercises: control structures ({% if %}), the ``is_need``/``is_part`` flags,
# the id/id_complete/id_parent/id_part variables, a Jinja filter (``upper``)
# and whitespace control (``-%}``).
needs_role_need_template = (
    ""
    "{% if is_need %}[NEED] {% endif -%}"
    "{% if is_part %}[NEEDPART]{% endif -%}"
    "[{{ id }}] [{{ id_complete }}] [{{ id_parent }}] [{{ id_part }}] "
    "[{{ type | upper }}] [{{ id }}] {{ title }} ({{ status }}) "
    "{{ type_name }}/{{ type }} - {{ tags }} - {{ links }} - {{ links_back }} - {{ content }}"
)
