from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/doc_needs_external_needs")
def test_doc_build_html(app, status, warning):
    import subprocess

    src_dir = "doc_test/doc_needs_external_needs"
    out_dir = Path(app.outdir)
    output = subprocess.run(["sphinx-build", "-M", "html", src_dir, out_dir], capture_output=True)
    assert not output.stderr

    # run second time and check
    output_second = subprocess.run(["sphinx-build", "-M", "html", src_dir, out_dir], capture_output=True)
    assert not output_second.stderr

    # check if incremental build used
    # first build output
    assert "making output directory" in output.stdout.decode("utf-8")
    assert "updating environment: [new config] 3 added, 0 changed, 0 removed" in output.stdout.decode("utf-8")
    # second build output
    assert "making output directory" not in output_second.stdout.decode("utf-8")
    assert "loading pickled environment" in output_second.stdout.decode("utf-8")
    assert "updating environment: [new config] 3 added, 0 changed, 0 removed" not in output_second.stdout.decode(
        "utf-8"
    )
    assert "updating environment: 0 added, 0 changed, 0 removed" in output_second.stdout.decode("utf-8")


@with_app(buildername="html", srcdir="doc_test/doc_needs_external_needs")
def test_external_needs_base_url_relative_path(app, status, warning):
    app.build()

    # check base_url full path from conf.py
    base_url_full_path = app.config.needs_external_needs[0]["base_url"]
    assert base_url_full_path == "http://my_company.com/docs/v1"

    # check base_url relative path from conf.py
    base_url_rel_path = app.config.needs_external_needs[1]["base_url"]
    assert base_url_rel_path == "../../_build/html"

    from lxml import html as html_parser

    # check usage in project root level
    html_path = str(Path(app.outdir, "index.html"))
    root_tree = html_parser.parse(html_path)

    # check needlist usage for base_url in root level
    root_list_hrefs = root_tree.xpath("//div/a")
    for ext_link in root_list_hrefs:
        if "class" in ext_link.attrib:
            assert ext_link.attrib["class"] == "external_link reference external"
    # check base_url relative path
    assert root_list_hrefs[4].attrib["href"] == "../../_build/html/index.html#TEST_02"
    assert root_list_hrefs[4].text == "EXT_REL_PATH_TEST_02: TEST_02 DESCRIPTION"
    # check base_url url
    assert root_list_hrefs[1].attrib["href"] == "http://my_company.com/docs/v1/index.html#TEST_02"
    assert root_list_hrefs[1].text == "EXT_TEST_02: TEST_02 DESCRIPTION"

    # check needtable usage for base_url in root level
    root_table_hrefs = root_tree.xpath("//table/tbody/tr/td/p/a")
    for external_link in root_table_hrefs:
        if "class" in external_link.attrib:
            assert external_link.attrib["class"] == "external_link reference external"
    # check base_url relative path in root level
    assert root_table_hrefs[0].attrib["href"] == "../../_build/html/index.html#TEST_01"
    assert root_table_hrefs[0].text == "EXT_REL_PATH_TEST_01"
    # check base_url url in root level
    assert root_table_hrefs[4].attrib["href"] == "http://my_company.com/docs/v1/index.html#TEST_01"
    assert root_table_hrefs[4].text == "EXT_TEST_01"

    # check needflow usage for base_url in root level
    root_flow_hrefs = root_tree.xpath("//figure/p/object/a/img")
    assert root_tree.xpath("//figure/figcaption/p/span/a")[0].text == "My needflow"
    # check base_url url in root level
    assert "as EXT_TEST_01 [[http://my_company.com/docs/v1/index.html#TEST_01]]" in root_flow_hrefs[0].attrib["alt"]
    # check base_url relative path in root level
    assert "as EXT_REL_PATH_TEST_01 [[../../_build/html/index.html#TEST_01]]" in root_flow_hrefs[0].attrib["alt"]

    # check role need_outgoing and need_incoming for base_url in root level
    for element in root_tree.xpath("//p/span/a"):
        # check link for need_outgoing
        if element.text == "EXT_TEST_01":
            assert element.attrib["href"] == "http://my_company.com/docs/v1/index.html#TEST_01"
        # check link for need_incoming
        if element.text == "EXT_REL_PATH_TEST_02":
            assert element.attrib["href"] == "../../_build/html/index.html#TEST_02"

    # check usage in subfolder level
    sub_html_path = str(Path(app.outdir, "subfolder_a", "index.html"))
    sub_tree = html_parser.parse(sub_html_path)

    # check needlist usage for base_url in subfolder level
    sub_list_hrefs = sub_tree.xpath("//div/a")
    for ext_link in sub_list_hrefs:
        if "class" in ext_link.attrib:
            assert ext_link.attrib["class"] == "external_link reference external"
    # check base_url relative path in subfolder level, one level deeper than base_url
    assert sub_list_hrefs[3].attrib["href"] == "../../../_build/html/index.html#TEST_01"
    assert sub_list_hrefs[3].text == "EXT_REL_PATH_TEST_01: TEST_01 DESCRIPTION"
    # check base_url url in subfolder level
    assert sub_list_hrefs[0].attrib["href"] == "http://my_company.com/docs/v1/index.html#TEST_01"
    assert sub_list_hrefs[0].text == "EXT_TEST_01: TEST_01 DESCRIPTION"

    # check needtable usage for base_url in subfolder level
    sub_table_hrefs = sub_tree.xpath("//table/tbody/tr/td/p/a")
    for external_link in sub_table_hrefs:
        if "class" in external_link.attrib:
            assert external_link.attrib["class"] == "external_link reference external"
    # check base_url relative path in subfolder level, one level deeper than base_url
    assert sub_table_hrefs[0].attrib["href"] == "../../../_build/html/index.html#TEST_01"
    assert sub_table_hrefs[0].text == "EXT_REL_PATH_TEST_01"
    # check base_url url in subfolder level
    assert sub_table_hrefs[4].attrib["href"] == "http://my_company.com/docs/v1/index.html#TEST_01"
    assert sub_table_hrefs[4].text == "EXT_TEST_01"

    # check needflow usage for base_url in subfolder level
    sub_flow_hrefs = sub_tree.xpath("//figure/p/object/a/img")
    assert sub_tree.xpath("//figure/figcaption/p/span/a")[0].text == "My needflow"
    # check base_url url in root level
    assert "as EXT_TEST_01 [[http://my_company.com/docs/v1/index.html#TEST_01]]" in sub_flow_hrefs[0].attrib["alt"]
    # check base_url relative path in subfolder level, one level deeper than base_url
    assert "as EXT_REL_PATH_TEST_01 [[../../../_build/html/index.html#TEST_01]]" in sub_flow_hrefs[0].attrib["alt"]

    # check role need_outgoing and need_incoming for base_url in subfolder level
    for element in sub_tree.xpath("//p/span/a"):
        # check link for need_outgoing
        if element.text == "EXT_TEST_01":
            assert element.attrib["href"] == "http://my_company.com/docs/v1/index.html#TEST_01"
        # check link for need_incoming
        if element.text == "EXT_REL_PATH_TEST_02":
            assert element.attrib["href"] == "../../../_build/html/index.html#TEST_02"

    # check usage in sub subfolder level
    sub_sub_html_path = str(Path(app.outdir, "subfolder_b", "subfolder_c", "index.html"))
    sub_sub_tree = html_parser.parse(sub_sub_html_path)

    # check needlist usage for base_url in subsubfolder level
    sub_sub_list_hrefs = sub_sub_tree.xpath("//div/a")
    for ext_link in sub_sub_list_hrefs:
        if "class" in ext_link.attrib:
            assert ext_link.attrib["class"] == "external_link reference external"
    # check base_url relative path in subsubfolder level, two level deeper than base_url
    assert sub_sub_list_hrefs[3].attrib["href"] == "../../../../_build/html/index.html#TEST_01"
    assert sub_sub_list_hrefs[3].text == "EXT_REL_PATH_TEST_01: TEST_01 DESCRIPTION"
    # check base_url url in subsubfolder level
    assert sub_sub_list_hrefs[0].attrib["href"] == "http://my_company.com/docs/v1/index.html#TEST_01"
    assert sub_sub_list_hrefs[0].text == "EXT_TEST_01: TEST_01 DESCRIPTION"

    # check needtable usage for base_url in subsubfolder level
    sub_sub_table_hrefs = sub_sub_tree.xpath("//table/tbody/tr/td/p/a")
    for external_link in sub_sub_table_hrefs:
        if "class" in external_link.attrib:
            assert external_link.attrib["class"] == "external_link reference external"
    # check base_url relative path in subsubfolder level, two level deeper than base_url
    assert sub_sub_table_hrefs[0].attrib["href"] == "../../../../_build/html/index.html#TEST_01"
    assert sub_sub_table_hrefs[0].text == "EXT_REL_PATH_TEST_01"
    # check base_url url in subsubfolder level
    assert sub_sub_table_hrefs[4].attrib["href"] == "http://my_company.com/docs/v1/index.html#TEST_01"
    assert sub_sub_table_hrefs[4].text == "EXT_TEST_01"

    # check needflow usage for base_url in subsubfolder level
    sub_sub_flow_hrefs = sub_sub_tree.xpath("//figure/p/object/a/img")
    assert sub_sub_tree.xpath("//figure/figcaption/p/span/a")[0].text == "My needflow"
    # check base_url url in subsubfolder level
    assert "as EXT_TEST_01 [[http://my_company.com/docs/v1/index.html#TEST_01]]" in sub_sub_flow_hrefs[0].attrib["alt"]
    # check base_url relative path in subsubfolder level, two level deeper than base_url
    assert (
        "as EXT_REL_PATH_TEST_01 [[../../../../_build/html/index.html#TEST_01]]" in sub_sub_flow_hrefs[0].attrib["alt"]
    )

    # check role need_outgoing and need_incoming for base_url in subsubfolder level
    for element in sub_sub_tree.xpath("//p/span/a"):
        # check link for need_outgoing
        if element.text == "EXT_TEST_01":
            assert element.attrib["href"] == "http://my_company.com/docs/v1/index.html#TEST_01"
        # check link for need_incoming
        if element.text == "EXT_REL_PATH_TEST_02":
            assert element.attrib["href"] == "../../../../_build/html/index.html#TEST_02"
