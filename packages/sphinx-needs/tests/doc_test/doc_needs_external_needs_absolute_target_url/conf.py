extensions = ["sphinx_needs"]

needs_table_style = "TABLE"

needs_types = [
    {
        "directive": "impl",
        "title": "Implementation",
        "prefix": "IM_",
        "color": "#DF744A",
        "style": "node",
    },
]

needs_fields = {"remote_url": {"nullable": True}}

SITE = "https://site.example/docs/"

# each template, under a base_url that is a site and under an empty one (the id
# prefix says which); the test reads every link by its prefixed id
_TEMPLATES = {
    # absolute renders: used as they are
    "ABS": "{{need.remote_url}}",  # the route the converter's docs give
    "UPPER": "HTTPS://GitHub.com/o/r/{{need['id']}}",
    "SCHEMEREL": "//cdn.example/x/{{need['id']}}",
    "FILE": "file:///tmp/ext/{{need['id']}}.html",
    # every other render: joined to base_url, as before
    "OPAQUE": "{{need['type']}}:{{need['id']}}",
    "SPACE": " {{need['remote_url']}}",
    "REL": "issue/{{need['id']}}",
}

needs_external_needs = [
    {
        "base_url": base_url,
        "target_url": template,
        "json_path": "needs.json",
        "id_prefix": f"{name}_{label}_",
    }
    for name, template in _TEMPLATES.items()
    for label, base_url in (("SITE", SITE), ("EMPTY", ""))
]
