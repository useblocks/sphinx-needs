"""
A parser for test results  in JSON files.

Must be configured via config, as there is no known standard for Test data in JSON files.

API must be in sync with the JUnit parser in ``junitparser.py``.
"""

import json
import operator
import os
from functools import reduce
from typing import Any

from ub_test_reports.errors import ReportReadError
from ub_test_reports.results import normalize_result

#: JSON's names for the types ``json.load`` returns, for a message about the file.
_JSON_KINDS = {
    dict: "an object",
    list: "an array",
    str: "a string",
    int: "a number",
    float: "a number",
    bool: "a boolean",
    type(None): "null",
}


def dict_get(root, items, default=None):
    """
    Access a nested object in root by item sequence.

    Usage::
       data = {"nested": {"a_list": [{"finally": "target_data"}]}}
       value = dict_get(data, ["nested", "a_list", 0, "finally"], "Not_found")

    """
    try:
        value = reduce(operator.getitem, items, root)
    except (KeyError, IndexError, TypeError):
        return default
    return value


class JsonParser:
    def __init__(self, json_path, *args, **kwargs):
        self.json_path = json_path

        if not os.path.exists(self.json_path):
            raise JsonFileMissing(f"The given file does not exist: {self.json_path}")

        self.json_data = []
        try:
            # UTF-8 with or without a byte-order mark, as `test-env` reads its file.
            with open(self.json_path, encoding="utf-8-sig") as jfile:
                self.json_data = json.load(jfile)
        except UnicodeDecodeError as error:
            raise ReportReadError(
                f"{self.json_path} is not valid UTF-8 "
                f"({error.reason} at byte {error.start})"
            ) from error
        except json.JSONDecodeError as error:
            raise ReportReadError(
                f"{self.json_path} (line {error.lineno}, column {error.colno}): "
                f"{error.msg}"
            ) from error

        self.json_mapping = kwargs.get("json_mapping", {})

    def validate(self):
        # For JSON we validate nothing here.
        # But to be compatible with the API, we need to return True
        return True

    def parse(self) -> list[dict[str, Any]]:
        """
        Creates a common python list of object, no matter what information are
        supported by the parsed json file for test results junit().

        :return: list of test suites as dictionaries
        """

        def parse_testcase(json_dict) -> dict[str, Any]:
            tc_mapping = self.json_mapping.get("testcase")
            tc_dict = {
                k: dict_get(json_dict, v[0], v[1]) for k, v in tc_mapping.items()
            }
            # A JSON report written against the JUnit dialect spells a failure
            # `failure`, after the element name. The API is documented as being
            # in sync with the JUnit parser's, so the same outcome has to
            # arrive under the same `result` here -- a value this package does
            # not know is left as the report wrote it.
            result = tc_dict.get("result")
            if isinstance(result, str):
                tc_dict["result"] = normalize_result(result)
            return tc_dict

        def parse_testsuite(json_dict) -> dict[str, Any]:
            ts_mapping = self.json_mapping.get("testsuite")
            ts_dict = {
                k: dict_get(json_dict, v[0], v[1])
                for k, v in ts_mapping.items()
                if k != "testcases"
            }
            ts_dict.update({"testcases": [], "testsuite_nested": []})

            testcases = dict_get(
                json_dict, ts_mapping["testcases"][0], ts_mapping["testcases"][1]
            )
            for tc in testcases:
                new_testcase = parse_testcase(tc)
                ts_dict["testcases"].append(new_testcase)

            return ts_dict

        # main flow starts here

        result_data = []

        # A list of suites, or nothing is: walking anything else reads every field as
        # its mapping's default.
        if not isinstance(self.json_data, list):
            kind = _JSON_KINDS.get(type(self.json_data), type(self.json_data).__name__)
            raise ReportReadError(
                f"{self.json_path}: the JSON report is not a list of test suites "
                f"(got {kind})"
            )

        for index, testsuite_data in enumerate(self.json_data):
            if not isinstance(testsuite_data, dict):
                kind = _JSON_KINDS.get(
                    type(testsuite_data), type(testsuite_data).__name__
                )
                raise ReportReadError(
                    f"{self.json_path}: test suite {index} is not an object (got {kind})"
                )
            complete_testsuite = parse_testsuite(testsuite_data)
            result_data.append(complete_testsuite)

        return result_data

    def docutils_table(self):
        pass


class JsonFileMissing(Exception):
    pass
