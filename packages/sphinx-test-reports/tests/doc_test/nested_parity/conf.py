# The parity project of #2050: ubCode's shared fixture `test_reports_auto` (useblocks/ubcode
# `e9fe0b2b16`, `rust/ubc_parser_ctrl/tests/build_fixtures/test_reports_auto/`), page
# `docs/nested.rst`, verbatim as `nested.rst`. Its `ubproject.toml` sets no id length and no
# `deterministic_case_ids`, so both tools run on the defaults, written out here.
import os

extensions = ["sphinx_needs", "sphinx_test_reports"]
master_doc = "index"
project = "test-report nested parity"
exclude_patterns = ["_build"]
tr_rootdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils")
tr_suite_id_length = 3
tr_case_id_length = 5
tr_deterministic_case_ids = False
