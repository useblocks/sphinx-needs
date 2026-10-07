"""A ``functions`` key in the ``needs_from_toml`` file, and ``needs_functions`` entries.

A dynamic function is a Python callable, and a TOML file can only hold data, so the
``functions`` key of ``[needs]`` cannot work. It used to end the build with
``'str' object has no attribute '__name__'``, when ``merge_default_configs`` registered
each entry as a function; the same crash came from ``conf.py`` itself for an entry that
is not callable. Each test is a real build, because both reads happen during
``config-inited`` and are only visible through the warnings and the configuration.

``conf.py`` could still end the build in two more ways (#2073): with a callable that has
no ``__name__`` (a ``functools.partial``, an instance with ``__call__``), because an entry
is registered by that name, and with a value that is not a list (``None``, a bare
function), which ``merge_default_configs`` iterated; a string was iterated character by
character. The API path, ``add_dynamic_function``, read the same ``__name__``.
"""

from __future__ import annotations

import functools
import json
import re
import textwrap
from pathlib import Path

import pytest

from sphinx_needs.api import add_dynamic_function
from sphinx_needs.config import NeedsSphinxConfig, _Config
from sphinx_needs.exceptions import NeedsApiConfigException
from sphinx_needs.functions import NEEDS_COMMON_FUNCTIONS
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


#: The names of the dynamic functions sphinx-needs registers itself.
BUILT_IN_FUNCTIONS = sorted(func.__name__ for func in NEEDS_COMMON_FUNCTIONS)


def _registered(app) -> list[str]:
    """The names of the dynamic functions the build registered."""
    return sorted(NeedsSphinxConfig(app.config).functions)


def _warnings(app) -> list[str]:
    """``build_warnings``, with the memory address in a repr replaced by ``0x...``."""
    return [re.sub(r" at 0x[0-9a-fA-F]+", " at 0x...", w) for w in build_warnings(app)]


def _echo_word(app, need, needs, word):
    """A dynamic function that takes one more argument, to be bound by a partial."""
    return word


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


#: A ``conf.py`` whose ``needs_functions`` is the value of ``{value}``, not a list.
NOT_A_LIST_CONF = """\
    extensions = ["sphinx_needs"]


    def answer(app, need, needs):
        return "forty-two"


    needs_functions = {value}
    """


@pytest.mark.parametrize(
    ("value", "type_name"),
    [
        pytest.param("None", "NoneType", id="none"),
        pytest.param("answer", "function", id="bare-function"),
        # not a crash: one "not callable" warning per character
        pytest.param('"answer"', "str", id="string"),
        # not a crash either: registered, beside Sphinx's own type warning
        pytest.param("{answer}", "set", id="set"),
    ],
)
def test_a_needs_functions_value_that_is_not_a_list_warns_once_and_is_ignored(
    build, value, type_name
):
    """``None`` and a bare function ended the build with ``TypeError: ... is not
    iterable``, when ``merge_default_configs`` iterated the value, a string was iterated
    character by character, and a set was registered beside Sphinx's own type warning.
    Each is now one ``needs.config`` warning naming the type, which Sphinx's own type
    check does not repeat; nothing is registered from the value, and the built-in
    functions still are."""
    app = build({"conf.py": NOT_A_LIST_CONF.format(value=value)})
    assert build_warnings(app) == [
        f"WARNING: needs_functions is of type {type_name!r}, not a list of callables, "
        "and is ignored [needs.config]"
    ]
    assert app.statuscode == 0
    assert app.config.needs_functions == []
    assert _registered(app) == BUILT_IN_FUNCTIONS


#: A ``conf.py`` whose ``needs_functions`` holds ``{entry}`` and then a function that
#: is registered, which a page calls.
NO_NAME_CONF = """\
    import functools

    extensions = ["sphinx_needs"]
    needs_build_json = True
    # Sphinx's own warning that a function in the configuration is not pickled, which
    # is not what these tests are about
    suppress_warnings = ["config.cache"]


    def answer(app, need, needs):
        return "forty-two"


    def echo_word(app, need, needs, word):
        return word


    class Answer:
        def __call__(self, app, need, needs):
            return "forty-two"


    needs_functions = [{entry}, answer]
    """


@pytest.mark.parametrize(
    ("entry", "entry_repr"),
    [
        pytest.param(
            'functools.partial(echo_word, word="forty-two")',
            "functools.partial(<function echo_word at 0x...>, word='forty-two')",
            id="partial",
        ),
        pytest.param("Answer()", "<Answer object at 0x...>", id="instance"),
    ],
)
def test_a_needs_functions_entry_without_a_name_warns_and_is_ignored(
    build, entry, entry_repr
):
    """A callable without a ``__name__`` ended the build with an ``AttributeError``,
    because an entry is registered by its ``__name__``. It is now skipped with a
    ``needs.config`` warning saying what an entry must be, and the rest of the list is
    still registered and called."""
    app = build(
        {
            "conf.py": NO_NAME_CONF.format(entry=entry),
            "index.rst": ANSWER_RST,
        }
    )
    assert _warnings(app) == [
        f"WARNING: needs_functions entry {entry_repr} has no __name__ and is ignored: "
        "an entry must be a callable with a __name__; use "
        "add_dynamic_function(app, func, name=...) for one without [needs.config]"
    ]
    assert app.statuscode == 0
    assert _registered(app) == sorted([*BUILT_IN_FUNCTIONS, "answer"])
    assert _need(app, "R_ONE")["status"] == "forty-two"


#: A ``conf.py`` whose ``needs_functions`` is a tuple, and a page that calls its function.
TUPLE_CONF = """\
    extensions = ["sphinx_needs"]
    needs_build_json = True
    # Sphinx's own warning that a function in the configuration is not pickled, which
    # is not what this test is about
    suppress_warnings = ["config.cache"]


    def answer(app, need, needs):
        return "forty-two"


    needs_functions = (answer,)
    """


def test_a_needs_functions_tuple_is_still_registered(build):
    """Guards the other side of the not-a-list check: a tuple was registered before,
    and still is, and its function is called. The one warning is Sphinx's own, for a
    value of a type the configuration does not declare; sphinx-needs adds none."""
    app = build({"conf.py": TUPLE_CONF, "index.rst": ANSWER_RST})
    assert build_warnings(app) == [
        "WARNING: The config value `needs_functions' has type `tuple'; expected `list'."
    ]
    assert app.statuscode == 0
    assert _registered(app) == sorted([*BUILT_IN_FUNCTIONS, "answer"])
    assert _need(app, "R_ONE")["status"] == "forty-two"


def test_add_dynamic_function_asks_for_a_name_for_a_callable_without_one(monkeypatch):
    """The API path read ``function.__name__`` as well, and raised a bare
    ``AttributeError`` for a callable without one. It now raises the API's configuration
    error, saying to pass ``name=``, and registers nothing; with ``name=`` the same
    callable is registered under that name."""
    registry = _Config()
    monkeypatch.setattr("sphinx_needs.api.configuration._NEEDS_CONFIG", registry)
    function = functools.partial(_echo_word, word="forty-two")
    # the application is not read by add_dynamic_function
    with pytest.raises(
        NeedsApiConfigException,
        match=r" has no __name__; pass the name to call it by with name=\.\.\.$",
    ):
        add_dynamic_function(None, function)
    assert dict(registry.functions) == {}

    add_dynamic_function(None, function, name="forty_two")
    assert dict(registry.functions) == {
        "forty_two": {"name": "forty_two", "function": function}
    }


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
