# `tr_link` with `include_parts`: the parts of every need are candidates too.
extensions = ["sphinx_needs", "sphinx_test_reports"]

needs_fields = {"case": {"schema": {"type": "string"}}}
needs_links = {
    "off": {},
    "by_address": {},
    "by_part_id": {},
    "by_case": {},
    "by_case_parts": {},
    "covered": {
        "derive": {"kind": "links", "where": "'REQ_1.p1' in by_address"},
    },
}

master_doc = "index"
project = "tr_link with need parts"
exclude_patterns = ["_build"]
