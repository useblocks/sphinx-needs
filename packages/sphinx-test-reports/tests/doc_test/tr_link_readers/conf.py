# Readers of the links `tr_link` computes, in the step that computes them.
extensions = ["sphinx_needs", "sphinx_test_reports"]

needs_id_regex = "^.+$"
# the default `test` type carries sphinx-test-reports' `classname`, which the
# extension declares on its test cases alone: the entry names it, so `test` does too
needs_types = {"test": {"fields": {"classname": {}}}}
needs_links = {
    "covers": {},
    "cov_u": {},
    "extra": {},
    "verified": {
        "derive": {"kind": "links", "where": "type == 'test' and len(links) > 0"}
    },
    "all_links": {"derive": {"kind": "union", "fields": ["links", "extra"]}},
}

master_doc = "index"
project = "tr_link readers"
exclude_patterns = ["_build"]
