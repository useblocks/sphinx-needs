import os
import sys
from pathlib import Path

import pytest
import responses
from docutils import __version__ as doc_ver
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needs_external_needs"}],
    indirect=True,
)
def test_doc_build_html(test_app, sphinx_test_tempdir):
    import subprocess

    app = test_app

    src_dir = Path(app.srcdir)
    out_dir = Path(app.outdir)
    plantuml = r"java -Djava.awt.headless=true -jar {}".format(
        os.path.join(sphinx_test_tempdir, "utils", "plantuml.jar")
    )
    output = subprocess.run(
        ["sphinx-build", "-b", "html", "-D", rf"plantuml={plantuml}", src_dir, out_dir],
        capture_output=True,
    )
    assert strip_colors(output.stderr.decode("utf-8")).splitlines() == [
        "WARNING: http://my_company.com/docs/v1/index.html#TEST_01: Need 'EXT_TEST_01' has unknown outgoing link 'SPEC_1' in field 'links' [needs.external_link_outgoing]",
        "WARNING: ../../_build/html/index.html#TEST_01: Need 'EXT_REL_PATH_TEST_01' has unknown outgoing link 'SPEC_1' in field 'links' [needs.external_link_outgoing]",
    ]

    # run second time and check
    output_second = subprocess.run(
        ["sphinx-build", "-b", "html", "-D", rf"plantuml={plantuml}", src_dir, out_dir],
        capture_output=True,
    )
    assert not output_second.stderr

    # check if incremental build used
    # first build output
    assert (
        "updating environment: [new config] 3 added, 0 changed, 0 removed"
        in strip_colors(output.stdout.decode("utf-8"))
    )
    # second build output
    assert "loading pickled environment" in output_second.stdout.decode("utf-8")
    assert (
        "updating environment: [new config] 3 added, 0 changed, 0 removed"
        not in strip_colors(output_second.stdout.decode("utf-8"))
    )
    assert "updating environment: 0 added, 0 changed, 0 removed" in strip_colors(
        output_second.stdout.decode("utf-8")
    )


@pytest.mark.skipif(
    sys.platform == "win32", reason="assert fails on windows, need to fix later."
)
@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needs_external_needs"}],
    indirect=True,
)
def test_external_needs_base_url_relative_path(test_app):
    app = test_app
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
    assert (
        root_list_hrefs[1].attrib["href"]
        == "http://my_company.com/docs/v1/index.html#TEST_02"
    )
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
    assert (
        root_table_hrefs[4].attrib["href"]
        == "http://my_company.com/docs/v1/index.html#TEST_01"
    )
    assert root_table_hrefs[4].text == "EXT_TEST_01"

    # check needflow usage for base_url in root level
    if int(doc_ver.split(".")[1]) >= 18:
        root_flow_hrefs = root_tree.xpath("//figure/p/object/a/img")
        assert root_tree.xpath("//figure/figcaption/p/span/a")[0].text == "My needflow"
    else:
        root_flow_hrefs = root_tree.xpath(
            "//div[@class='figure align-center']/p/object/a/img"
        )
        assert (
            root_tree.xpath(
                "//div[@class='figure align-center']/p[@class='caption']/span/a"
            )[0].text
            == "My needflow"
        )
    # check base_url url in root level
    assert (
        "as EXT_TEST_01 [[http://my_company.com/docs/v1/index.html#TEST_01]]"
        in root_flow_hrefs[0].attrib["alt"]
    )
    # check base_url relative path in root level
    assert (
        "as EXT_REL_PATH_TEST_01 [[../../../_build/html/index.html#TEST_01]]"
        in root_flow_hrefs[0].attrib["alt"]
    )

    # check role need_outgoing and need_incoming for base_url in root level
    for element in root_tree.xpath("//p/span/a"):
        # check link for need_outgoing
        if element.text == "EXT_TEST_01":
            assert (
                element.attrib["href"]
                == "http://my_company.com/docs/v1/index.html#TEST_01"
            )
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
    assert (
        sub_list_hrefs[0].attrib["href"]
        == "http://my_company.com/docs/v1/index.html#TEST_01"
    )
    assert sub_list_hrefs[0].text == "EXT_TEST_01: TEST_01 DESCRIPTION"

    # check needtable usage for base_url in subfolder level
    sub_table_hrefs = sub_tree.xpath("//table/tbody/tr/td/p/a")
    for external_link in sub_table_hrefs:
        if "class" in external_link.attrib:
            assert external_link.attrib["class"] == "external_link reference external"
    # check base_url relative path in subfolder level, one level deeper than base_url
    assert (
        sub_table_hrefs[0].attrib["href"] == "../../../_build/html/index.html#TEST_01"
    )
    assert sub_table_hrefs[0].text == "EXT_REL_PATH_TEST_01"
    # check base_url url in subfolder level
    assert (
        sub_table_hrefs[4].attrib["href"]
        == "http://my_company.com/docs/v1/index.html#TEST_01"
    )
    assert sub_table_hrefs[4].text == "EXT_TEST_01"

    # check needflow usage for base_url in subfolder level
    if int(doc_ver.split(".")[1]) >= 18:
        sub_flow_hrefs = sub_tree.xpath("//figure/p/object/a/img")
        assert sub_tree.xpath("//figure/figcaption/p/span/a")[0].text == "My needflow"
    else:
        sub_flow_hrefs = sub_tree.xpath(
            "//div[@class='figure align-center']/p/object/a/img"
        )
        assert (
            sub_tree.xpath(
                "//div[@class='figure align-center']/p[@class='caption']/span/a"
            )[0].text
            == "My needflow"
        )
    # check base_url url in root level
    assert (
        "as EXT_TEST_01 [[http://my_company.com/docs/v1/index.html#TEST_01]]"
        in sub_flow_hrefs[0].attrib["alt"]
    )
    # check base_url relative path in subfolder level, one level deeper than base_url
    assert (
        "as EXT_REL_PATH_TEST_01 [[../../../_build/html/index.html#TEST_01]]"
        in sub_flow_hrefs[0].attrib["alt"]
    )

    # check role need_outgoing and need_incoming for base_url in subfolder level
    for element in sub_tree.xpath("//p/span/a"):
        # check link for need_outgoing
        if element.text == "EXT_TEST_01":
            assert (
                element.attrib["href"]
                == "http://my_company.com/docs/v1/index.html#TEST_01"
            )
        # check link for need_incoming
        if element.text == "EXT_REL_PATH_TEST_02":
            assert element.attrib["href"] == "../../../_build/html/index.html#TEST_02"

    # check usage in sub subfolder level
    sub_sub_html_path = str(
        Path(app.outdir, "subfolder_b", "subfolder_c", "index.html")
    )
    sub_sub_tree = html_parser.parse(sub_sub_html_path)

    # check needlist usage for base_url in subsubfolder level
    sub_sub_list_hrefs = sub_sub_tree.xpath("//div/a")
    for ext_link in sub_sub_list_hrefs:
        if "class" in ext_link.attrib:
            assert ext_link.attrib["class"] == "external_link reference external"
    # check base_url relative path in subsubfolder level, two level deeper than base_url
    assert (
        sub_sub_list_hrefs[3].attrib["href"]
        == "../../../../_build/html/index.html#TEST_01"
    )
    assert sub_sub_list_hrefs[3].text == "EXT_REL_PATH_TEST_01: TEST_01 DESCRIPTION"
    # check base_url url in subsubfolder level
    assert (
        sub_sub_list_hrefs[0].attrib["href"]
        == "http://my_company.com/docs/v1/index.html#TEST_01"
    )
    assert sub_sub_list_hrefs[0].text == "EXT_TEST_01: TEST_01 DESCRIPTION"

    # check needtable usage for base_url in subsubfolder level
    sub_sub_table_hrefs = sub_sub_tree.xpath("//table/tbody/tr/td/p/a")
    for external_link in sub_sub_table_hrefs:
        if "class" in external_link.attrib:
            assert external_link.attrib["class"] == "external_link reference external"
    # check base_url relative path in subsubfolder level, two level deeper than base_url
    assert (
        sub_sub_table_hrefs[0].attrib["href"]
        == "../../../../_build/html/index.html#TEST_01"
    )
    assert sub_sub_table_hrefs[0].text == "EXT_REL_PATH_TEST_01"
    # check base_url url in subsubfolder level
    assert (
        sub_sub_table_hrefs[4].attrib["href"]
        == "http://my_company.com/docs/v1/index.html#TEST_01"
    )
    assert sub_sub_table_hrefs[4].text == "EXT_TEST_01"

    # check needflow usage for base_url in subsubfolder level
    if int(doc_ver.split(".")[1]) >= 18:
        sub_sub_flow_hrefs = sub_sub_tree.xpath("//figure/p/object/a/img")
        assert (
            sub_sub_tree.xpath("//figure/figcaption/p/span/a")[0].text == "My needflow"
        )
    else:
        sub_sub_flow_hrefs = sub_tree.xpath(
            "//div[@class='figure align-center']/p/object/a/img"
        )
        assert (
            sub_sub_tree.xpath(
                "//div[@class='figure align-center']/p[@class='caption']/span/a"
            )[0].text
            == "My needflow"
        )

    # check base_url url in subsubfolder level
    assert (
        "as EXT_TEST_01 [[http://my_company.com/docs/v1/index.html#TEST_01]]"
        in sub_sub_flow_hrefs[0].attrib["alt"]
    )
    # check base_url relative path in subsubfolder level, two level deeper than base_url
    assert (
        "as EXT_REL_PATH_TEST_01 [[../../../_build/html/index.html#TEST_01]]"
        in sub_sub_flow_hrefs[0].attrib["alt"]
    )

    # check role need_outgoing and need_incoming for base_url in subsubfolder level
    for element in sub_sub_tree.xpath("//p/span/a"):
        # check link for need_outgoing
        if element.text == "EXT_TEST_01":
            assert (
                element.attrib["href"]
                == "http://my_company.com/docs/v1/index.html#TEST_01"
            )
        # check link for need_incoming
        if element.text == "EXT_REL_PATH_TEST_02":
            assert (
                element.attrib["href"] == "../../../../_build/html/index.html#TEST_02"
            )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needs_external_needs_remote"}],
    indirect=True,
)
def test_external_needs_json_url(test_app):
    app = test_app

    # Mock API calls performed to get remote file
    remote_json = {
        "created": "2021-05-11T13:54:22.331741",
        "current_version": "1.0",
        "project": "needs test docs",
        "versions": {
            "1.0": {
                "created": "2021-05-11T13:54:22.331724",
                "filters": {},
                "filters_amount": 0,
                "needs": {
                    "TEST_101": {
                        "id": "TEST_101",
                        "description": "TEST_101 DESCRIPTION",
                        "docname": "index",
                        "external_css": "external_link",
                        "external_url": "http://my_company.com/docs/v1/index.html#TEST_01",
                        "title": "TEST_101 TITLE",
                        "type": "impl",
                        "tags": ["ext_test"],
                    }
                },
            }
        },
    }

    with responses.RequestsMock() as m:
        m.get("http://my_company.com/docs/v1/remote-needs.json", json=remote_json)
        app.build()

    # check base_url full path from conf.py
    base_url_full_path = app.config.needs_external_needs[0]["base_url"]
    assert base_url_full_path == "http://my_company.com/docs/v1"

    # check base_url relative path from conf.py
    json_url = app.config.needs_external_needs[0]["json_url"]
    assert json_url == "http://my_company.com/docs/v1/remote-needs.json"

    from lxml import html as html_parser

    # check usage in project root level
    html_path = str(Path(app.outdir, "index.html"))
    root_tree = html_parser.parse(html_path)

    # check needlist usage for base_url in root level
    root_list_hrefs = root_tree.xpath("//div/a")
    for ext_link in root_list_hrefs:
        if "class" in ext_link.attrib:
            assert ext_link.attrib["class"] == "external_link reference external"
    # check usage from remote URL
    assert (
        root_list_hrefs[0].attrib["href"]
        == "http://my_company.com/docs/v1/index.html#TEST_101"
    )
    assert root_list_hrefs[0].text == "EXT_REMOTE_TEST_101: TEST_101 TITLE"

    # check needtable usage for base_url in root level
    root_table_hrefs = root_tree.xpath("//table/tbody/tr/td/p/a")
    for external_link in root_table_hrefs:
        if "class" in external_link.attrib:
            assert external_link.attrib["class"] == "external_link reference external"
    # check for remote url
    assert (
        root_table_hrefs[0].attrib["href"]
        == "http://my_company.com/docs/v1/index.html#TEST_101"
    )
    assert root_table_hrefs[0].text == "EXT_REMOTE_TEST_101"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needs_external_needs_with_target_url",
        }
    ],
    indirect=True,
)
def test_external_needs_target_url(test_app):
    app = test_app
    app.build()

    external_needs = app.config.needs_external_needs
    assert external_needs
    assert len(external_needs) == 4

    html = Path(app.outdir, "index.html").read_text()

    assert external_needs[0]["target_url"] == "issue/{{need['id']}}"
    assert "EXT_NEED_ID_TEST_01" in html
    assert "http://my_company.com/docs/v1/issue/TEST_01" in html

    assert external_needs[1]["target_url"] == "issue/fixed_string"
    assert "EXT_STRING_TEST_01" in html
    assert "http://my_company.com/docs/v1/issue/fixed_string" in html

    assert external_needs[2]["target_url"] == "issue/{{need['type']|upper()}}"
    assert "EXT_NEED_TYPE_TEST_01" in html
    assert "http://my_company.com/docs/v1/issue/IMPL" in html

    assert "target_url" not in external_needs[3]
    assert "EXT_DEFAULT_TEST_01" in html
    assert "http://my_company.com/docs/v1/index.html#TEST_01" in html
