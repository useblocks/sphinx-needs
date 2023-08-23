import json

import pytest

from sphinx_needs.filter_common import filter_needs


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs_per_page", "srcdir": "doc_test/doc_needs_builder"}], indirect=True
)
def test_doc_needs_per_page_builder(test_app):
    import os

    from sphinx_needs.utils import unwrap

    app = test_app
    app.build()
    out_dir = app.outdir
    env = unwrap(app.env)
    needs = env.needs_all_needs.values()
    filter_string = app.config.needs_builder_filter
    filtered_needs = filter_needs(app, needs, filter_string)
    needs_per_page_build_path = app.config.needs_per_page_build_path
    needs_per_page_parent_path = os.path.join(out_dir, needs_per_page_build_path)
    for need in filtered_needs:
        need_id = need["id"]
        need_docname = need["docname"]
        need_docname_file = f"{need_docname}.json"
        need_docname_path = os.path.join(needs_per_page_parent_path, need_docname_file)
        # need_docname = os.path.dirname(docs_name_file)
        assert os.path.exists(need_docname_path)

        with open(need_docname_path) as needs_file:
            needs_file_content = needs_file.read()
            needs_list = json.loads(needs_file_content)
            assert isinstance(needs_list["needs"], list)
            need_of_file = needs_list["needs"]
            all_keys = set().union(*(d.keys() for d in need_of_file))

            assert need_id in all_keys
