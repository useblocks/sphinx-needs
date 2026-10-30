extensions = ["sphinx_needs", "sphinx_test_reports"]
exclude_patterns = ["_build"]
needs_build_json = True
tr_extra_options = ["owner"]
# the project's own `test` type names the extension's `case_name`: it declares it too
needs_types = [
    {
        "directive": "test",
        "title": "Test Case",
        "prefix": "T_",
        "fields": {"case_name": {}},
    }
]
