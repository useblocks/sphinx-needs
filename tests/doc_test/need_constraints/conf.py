extensions = ["sphinx_needs"]

needs_build_json = True
needs_table_style = "TABLE"

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

needs_external_needs = [
    {
        "base_url": "http://my_company.com/docs/v1/",
        "json_path": "needs_test_small.json",
        "id_prefix": "ext_",
    }
]


def my_custom_warning_check(need, log):
    if need["status"] == "open":
        log.info(f"{need['id']} status must not be 'open'.")
        return True
    return False


needs_warnings = {
    "invalid_status": "status not in ['open', 'closed', 'done', 'example_2', 'example_3']",
    "type_match": my_custom_warning_check,
}


def custom_warning_func(need, log):
    return need["status"] == "example_3"


def setup(app):
    from sphinx_needs.api.configuration import add_warning

    add_warning(app, "api_warning_filter", filter_string="status == 'example_2'")
    add_warning(app, "api_warning_func", custom_warning_func)
    add_warning(
        app,
        "invalid_status",
        "status not in ['open', 'closed', 'done', 'example_2', 'example_3']",
    )


# Needs option to set True or False to raise sphinx-warning for each not passed warning check
# default is False
needs_warnings_always_warn = True

needs_extra_options = []

needs_constraints = {
    "security": {"check_0": "'security' in tags", "severity": "CRITICAL"},
    "team": {"check_0": "'team_requirement' in links", "severity": "MEDIUM"},
    "critical": {
        "check_0": "'critical' in tags",
        "severity": "CRITICAL",
        "error_message": "need {{id}} does not fulfill CRITICAL constraint, because tags are {{tags}}",
    },
}


needs_constraint_failed_options = {
    "CRITICAL": {"on_fail": ["warn"], "style": ["red_bar"], "force_style": True},
    "HIGH": {"on_fail": ["warn"], "style": ["orange_bar"], "force_style": True},
    "MEDIUM": {"on_fail": ["warn"], "style": ["yellow_bar"], "force_style": False},
    "LOW": {"on_fail": [], "style": ["yellow_bar"], "force_style": False},
}
