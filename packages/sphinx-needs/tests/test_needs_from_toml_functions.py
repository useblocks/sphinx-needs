"""A ``functions`` key in the ``needs_from_toml`` file, and ``needs_functions`` entries.

A dynamic function is a Python callable, and a TOML file can only hold data, so the
``functions`` key of ``[needs]`` cannot work. It used to end the build with
``'str' object has no attribute '__name__'``, when ``merge_default_configs`` registered
each entry as a function; the same crash came from ``conf.py`` itself for an entry that
is not callable. Each test is a real build, because both reads happen during
``config-inited`` and are only visible through the warnings and the configuration.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from sphinx_needs_testkit import assert_no_warnings, build_warnings

RST = "Title\n=====\n\nText.\n"

TOML_CONF = 'extensions = ["sphinx_needs"]\nneeds_from_toml = "ubproject.toml"\n'

TOML_FUNCTIONS_WARNING = (
    "WARNING: 'needs_from_toml' file sets 'functions', which is ignored: "
    "dynamic functions are Python callables, registered in conf.py as "
    "needs_functions or through the add_dynamic_function API [needs.config]"
)


#: A ``conf.py`` registering one real function, and a page that calls it.
ANSWER_CONF = """\
    extensions = ["sphinx_needs"]
    needs_from_toml = "ubproject.toml"
    # Sphinx's own warning that a function in the configuration is not pickled, which
    # is not what these tests are about
    suppress_warnings = ["config.cache"]


    def answer(app, need, needs):
        return "forty-two"


    needs_functions = [answer]
    """
ANSWER_RST = """\
    Title
    =====

    .. req:: One
       :id: R_ONE
       :status: [[answer()]]
    """


@pytest.fixture
def build(make_app, tmp_path):
    """Write a project, build it, and return the application."""

    def _build(files: dict[str, str], **kwargs):
        srcdir = tmp_path / "src"
        for name, content in {"index.rst": RST, **files}.items():
            path = srcdir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(content), encoding="utf-8")
        app = make_app(srcdir=srcdir, freshenv=True, **kwargs)
        app.build()
        return app

    return _build


def _need(app, need_id: str) -> dict:
    """Read one need from the build's ``needs.json``."""
    needs = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    return needs["versions"][""]["needs"][need_id]


@pytest.mark.parametrize(
    "toml",
    [
        pytest.param('[needs]\nfunctions = ["x"]\n', id="list"),
        # a string used to be iterated character by character
        pytest.param('[needs]\nfunctions = "x"\n', id="string"),
        # the shape a later release reserves for declarations; its keys used to be
        # iterated as if they were functions
        pytest.param(
            """\
            [needs.functions.linked_effort]
            description = "the summed effort of the linked needs"
            """,
            id="table",
        ),
        # empty, but still a key that is never read: Sphinx used to warn that its type
        # was not a list
        pytest.param('[needs]\nfunctions = ""\n', id="empty-string"),
        pytest.param("[needs.functions]\n", id="empty-table"),
    ],
)
def test_a_functions_key_in_the_toml_warns_and_is_ignored(build, toml):
    """Every non-empty shape of the key used to end the build with an
    ``AttributeError``; every shape is now one ``needs.config`` warning, the key is
    dropped, and the build completes."""
    app = build({"conf.py": TOML_CONF, "ubproject.toml": toml})
    assert build_warnings(app) == [TOML_FUNCTIONS_WARNING]
    assert app.config.needs_functions == []
    assert app.statuscode == 0


def test_an_empty_functions_key_in_the_toml_is_reported_and_ignored(build):
    """A key that is never read has no silent form: an empty list is reported like any
    other value, whatever ``conf.py`` holds."""
    app = build({"conf.py": TOML_CONF, "ubproject.toml": "[needs]\nfunctions = []\n"})
    assert build_warnings(app) == [TOML_FUNCTIONS_WARNING]
    assert app.config.needs_functions == []


def test_an_empty_functions_key_in_the_toml_keeps_the_functions_of_conf_py(build):
    """An empty list in the TOML used to replace, silently, the functions ``conf.py``
    registers, so a ``[[answer()]]`` became an unknown function. The key is not read
    any more: the function still runs, and the key is reported."""
    app = build(
        {
            "conf.py": ANSWER_CONF,
            "ubproject.toml": "[needs]\nbuild_json = true\nfunctions = []\n",
            "index.rst": ANSWER_RST,
        }
    )
    assert build_warnings(app) == [TOML_FUNCTIONS_WARNING]
    assert _need(app, "R_ONE")["status"] == "forty-two"


def test_a_needs_functions_entry_that_is_not_callable_warns_and_is_ignored(build):
    """The root cause, without any TOML: ``conf.py`` itself crashed the same way for an
    entry that is not callable. The entry is now skipped with a ``needs.config``
    warning."""
    app = build({"conf.py": 'extensions = ["sphinx_needs"]\nneeds_functions = ["x"]\n'})
    assert build_warnings(app) == [
        "WARNING: needs_functions entry 'x' is not callable and is ignored "
        "[needs.config]"
    ]
    assert app.statuscode == 0


def test_an_override_of_needs_functions_wins_over_the_toml_silently(build):
    """An override (``confoverrides``) is never replaced by the TOML file, and the key
    it overrides is not reported either: the TOML value is not used, whatever it
    holds."""
    app = build(
        {"conf.py": TOML_CONF, "ubproject.toml": '[needs]\nfunctions = ["x"]\n'},
        confoverrides={"needs_functions": []},
    )
    assert_no_warnings(app)
    assert app.config.needs_functions == []


def test_a_function_from_conf_py_is_still_registered_beside_a_toml_file(build):
    """Guards against dropping too much: a callable in ``conf.py``'s ``needs_functions``
    is registered and called, and the TOML file's other keys are read, with no warning.
    """
    app = build(
        {
            "conf.py": ANSWER_CONF,
            "ubproject.toml": "[needs]\nbuild_json = true\nid_required = true\n",
            "index.rst": ANSWER_RST,
        }
    )
    assert_no_warnings(app)
    assert app.config.needs_id_required is True
    assert _need(app, "R_ONE")["status"] == "forty-two"


def test_needs_functions_entry_without_name_warns_and_is_ignored(build):
    """A callable without a __name__ (e.g. functools.partial) in needs_functions warns
    and is ignored rather than raising AttributeError."""
    conf = """\
        extensions = ["sphinx_needs"]
        suppress_warnings = ["config.cache"]
        import functools

        needs_functions = [functools.partial(min, 1)]
    """
    app = build({"conf.py": conf})
    warnings = build_warnings(app)
    assert len(warnings) == 1
    assert "has no __name__ and is ignored" in warnings[0]
    assert "[needs.config]" in warnings[0]
    assert app.statuscode == 0


def test_needs_functions_none_value_does_not_crash(build):
    """Setting needs_functions = None does not crash with TypeError."""
    app = build({"conf.py": 'extensions = ["sphinx_needs"]\nneeds_functions = None\n'})
    assert app.statuscode == 0


def test_needs_functions_bare_callable_value_does_not_crash(build):
    """Setting needs_functions = func (a bare function instead of a list) does not crash."""
    conf = """\
        extensions = ["sphinx_needs"]
        suppress_warnings = ["config.cache"]

        def dummy():
            pass

        needs_functions = dummy
    """
    app = build({"conf.py": conf})
    assert app.statuscode == 0


def test_add_dynamic_function_allows_callables_without_name(build):
    """add_dynamic_function allows registering a callable without __name__ when a name is given."""
    conf = """\
        extensions = ["sphinx_needs"]
        needs_build_json = True
        suppress_warnings = ["config.cache"]
        import functools
        from sphinx_needs.api import add_dynamic_function

        def raw_answer(app, need, needs, extra):
            return f"answer-{extra}"

        def setup(app):
            add_dynamic_function(app, functools.partial(raw_answer, extra="partial"), name="partial_func")
    """
    rst = """\
        Title
        =====

        .. req:: One
           :id: R_ONE
           :status: [[partial_func()]]
    """
    app = build({"conf.py": conf, "index.rst": rst})
    assert_no_warnings(app)
    assert _need(app, "R_ONE")["status"] == "answer-partial"
