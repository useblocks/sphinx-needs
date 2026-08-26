"""Project where an extension writes the variant data after it has been resolved.

The ``config-inited`` handler registered below runs at the default priority, so it
writes the map after Sphinx-Needs has resolved it, and its value is therefore neither
merged with the file nor validated. What the build must not do is read two different
maps: the ``variant`` role and ``var.*`` filter expressions have to agree on whatever
value ends up in the configuration.
"""

extensions = ["sphinx_needs"]

needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "REQ_",
        "color": "#BFD8D2",
        "style": "node",
    },
]

# File provides: {"env": "production"}
needs_variant_data_file = "variant_data.json"


def _overwrite_variant_data(_app, config):
    """Overwrite the resolved map, as a third-party extension could."""
    config.needs_variant_data = {"env": "from_extension"}


def setup(app):
    # default priority (500), so this runs after Sphinx-Needs' resolution
    app.connect("config-inited", _overwrite_variant_data)
