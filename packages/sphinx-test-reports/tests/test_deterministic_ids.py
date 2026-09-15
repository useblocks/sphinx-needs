"""Sphinx-level tests for the opt-in deterministic test-case IDs (TR-G).

Both ID-producing paths must honour the scheme: the ``test-case`` directive's
own fallback ID, and the parent-scoped ID that ``:auto_cases:`` generates.
Expected values come from tests/test_identity.py, which pins them against
S-CORE's implementation.
"""

import hashlib
from pathlib import Path

import pytest

EXPECTED_IDS = [
    "testcase__MathTest__Addition_hcuyy",
    "testcase__MathTest__Subtraction_srmht",
    "testcase__MathTest__DISABLED_Division_jnyzp",
    "testcase__ParamTest_0__Works_0_ugfea",
    "testcase__ParamTest_0__Legacy_owuvz",
]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/deterministic_ids"}],
    indirect=True,
)
class TestDeterministicIdsEnabled:
    def test_build_succeeds(self, test_app):
        app = test_app
        app.build()
        assert app.statuscode == 0

    @pytest.mark.parametrize("need_id", EXPECTED_IDS)
    def test_auto_cases_use_the_deterministic_id(self, test_app, need_id):
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        assert need_id in html

    def test_the_parent_scoped_case_id_is_replaced_not_added(self, test_app):
        """The old scheme hashed sha1(classname + name) under the suite ID.

        Suite IDs stay parent-scoped -- TR-G is about *case* identity -- so this
        asserts on the case fragment specifically.
        """
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        old_case_fragment = (
            hashlib.sha1(b"MathTest" + b"Addition").hexdigest().upper()[:5]
        )
        assert f"_{old_case_fragment}" not in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/source_location"}],
    indirect=True,
)
class TestDeterministicIdsDisabledByDefault:
    def test_ids_are_unchanged_without_the_option(self, test_app):
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        assert "testcase__MathTest__Addition_hcuyy" not in html
