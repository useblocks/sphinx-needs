extensions = ["sphinx_needs"]

# One upstream needs.json (written by sphinx-needs: its HTML page mints a
# ``<span class="need-part" id="UP_001.p1">`` anchor for each part), read by four sources:
# the default URL with and without an ``id_prefix``, and two ``target_url`` shapes.
needs_external_needs = [
    {
        "base_url": "https://up.example.org/docs",
        "json_path": "upstream_needs.json",
    },
    {
        "base_url": "https://up.example.org/docs",
        "json_path": "upstream_needs.json",
        "id_prefix": "EXT_",
    },
    {
        "base_url": "https://up.example.org/docs",
        "json_path": "upstream_needs.json",
        "id_prefix": "TGT_",
        "target_url": "issue/{{ need['id'] }}",
    },
    {
        "base_url": "https://up.example.org/docs",
        "json_path": "upstream_needs.json",
        "id_prefix": "ANC_",
        "target_url": "page.html#req-{{ need['id'] }}",
    },
]
