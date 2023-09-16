extensions = ["sphinx_needs"]

needs_extra_options = ["author"]
needs_constraints = {
    "team": {"check_0": 'author == "Bob"', "severity": "CRITICAL"},
}
needs_constraint_failed_options = {
    "CRITICAL": {"on_fail": ["warn"], "style": ["red_bar"], "force_style": True},
}
needs_global_options = {"constraints": ("team", 'type == "req" ')}
