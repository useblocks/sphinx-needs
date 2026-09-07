"""Project checking that variant data is resolved during ``config-inited``.

The ``config-inited`` handler registered below runs at the default priority, so it
records the variant data as any later handler of that event would see it, which is
the fully merged map only if Sphinx-Needs has already resolved it by then.
"""

from copy import deepcopy

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

# File provides: {"env": "production", "build": {"debug": true, "opt_level": 1}}
needs_variant_data_file = "variant_data.json"

# Inline overrides a single nested leaf; its siblings must survive the merge
needs_variant_data = {"build": {"opt_level": 3}}


def _record_variant_data(app, config):
    """Record the variant data seen by a later ``config-inited`` handler."""
    app.variant_data_at_config_inited = deepcopy(config.needs_variant_data)


def setup(app):
    app.connect("config-inited", _record_variant_data)
