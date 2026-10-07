"""The file -> suite -> case parent links of an ``:auto_suites:`` / ``:auto_cases:`` expansion."""

import re

import pytest

import sphinx_test_reports.directives.test_case
import sphinx_test_reports.directives.test_suite
from sphinx_needs.data import SphinxNeedsData


def _record_links(monkeypatch) -> dict[str, str]:
    """Record the ``links`` STRING each suite and case hands to ``add_need``, by need id.

    sphinx-needs splits, sorts and de-duplicates that string when it reads it, so a
    duplicated id never reaches the built needs; only the string shows it.
    """
    handed: dict[str, str] = {}
    for module in (
        sphinx_test_reports.directives.test_suite,
        sphinx_test_reports.directives.test_case,
    ):
        real = module.add_need

        def recording(*args, _real=real, **kwargs):
            handed[kwargs["id"]] = kwargs["links"]
            return _real(*args, **kwargs)

        monkeypatch.setattr(module, "add_need", recording)
    return handed


def _elements(links: str) -> list[str]:
    # the delimiters sphinx-needs' link parser splits on
    return [x.strip() for x in re.split("[;|,]", links) if x.strip()]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/parent_links_prefix"}],
    indirect=True,
)
def test_a_link_containing_the_file_id_keeps_the_parent_links(test_app, monkeypatch):
    """``:links: TF_PRFX`` on the test-file ``TF_PRF`` (#2114).

    The "already linked" test was a SUBSTRING test on the authored string, and
    ``"TF_PRF" in "TF_PRFX"`` is true, so the file id was never appended: no suite
    linked its file, and no case linked it either. Any id that is a prefix of another
    linked id does it -- ``TF_1`` with ``TF_10`` -- so ordinary numbering triggers it.
    The control file, whose link shares no prefix with its id, must come out exactly as
    it always did, string for string.
    """
    handed = _record_links(monkeypatch)
    app = test_app
    app.build()
    needs = dict(SphinxNeedsData(app.env).get_needs_view())

    def family(file_id: str, type_: str) -> dict[str, list[str]]:
        return {
            id_: sorted(need["links"])
            for id_, need in needs.items()
            if id_.startswith(file_id + "_") and need["type"] == type_
        }

    for file_id, authored in (("TF_PRF", "TF_PRFX"), ("TF_CTL", "REQ_1")):
        suites = family(file_id, "testsuite")
        cases = family(file_id, "testcase")
        # gtest_data.xml: two suites, five cases -- so the loops below are not vacuous
        assert len(suites) == 2, suites
        assert len(cases) == 5, cases
        for suite_id, links in suites.items():
            assert links == sorted([authored, file_id]), suite_id
            assert handed[suite_id] == f"{authored};{file_id}"
        for case_id, links in cases.items():
            suite_id = case_id.rsplit("_", 1)[0]
            assert suite_id in suites, case_id
            assert links == sorted([authored, file_id, suite_id]), case_id
            assert handed[case_id] == f"{authored};{file_id};{suite_id}"

    # authored values that already hold the file id, with a separator and spaces: the
    # string is handed on AS WRITTEN (not re-joined, the id not appended again), and a
    # case adds only its suite id
    for file_id, authored in (
        ("TF_SPC", "REQ_1 , TF_SPC"),
        ("TF_PIPE", "REQ_1|TF_PIPE"),
    ):
        suites = family(file_id, "testsuite")
        cases = family(file_id, "testcase")
        assert len(suites) == 2, suites
        assert len(cases) == 5, cases
        for suite_id, links in suites.items():
            assert links == sorted(["REQ_1", file_id]), suite_id
            assert handed[suite_id] == authored
        for case_id, links in cases.items():
            suite_id = case_id.rsplit("_", 1)[0]
            assert links == sorted(["REQ_1", file_id, suite_id]), case_id
            assert handed[case_id] == f"{authored};{suite_id}"

    # no string handed to add_need names an id twice
    for id_, links in handed.items():
        assert len(_elements(links)) == len(set(_elements(links))), (id_, links)
