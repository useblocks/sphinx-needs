"""Registering the services configured in ``needs_services`` (#2067).

A service is registered from its configuration when the entry has both ``class`` and
``class_init``. A ``class`` that is not a service class -- the only thing a
``needs_from_toml`` file can give it is a string -- used to end the build with
``'str' object has no attribute 'options'`` at ``env-before-read-docs``, and a
``class_init`` that is not a dict ended it in the keyword expansion. Such an entry is now
skipped with one ``needs.config`` warning, and the build goes on. Each test is a real
build, because the registration happens in ``prepare_env``.
"""

from __future__ import annotations

import textwrap

import pytest

from sphinx_needs.services.manager import NeedsServiceException
from sphinx_needs_testkit import assert_no_warnings, build_warnings

RST = "Title\n=====\n\nText.\n"

TOML_CONF = 'extensions = ["sphinx_needs"]\nneeds_from_toml = "ubproject.toml"\n'

#: the services sphinx-needs registers itself, in every build
BUILT_IN = {"github-commits", "github-issues", "github-prs"}


def class_warning(name: str, got: str) -> str:
    return (
        f"WARNING: needs_services entry {name!r} is not registered: its 'class' is not "
        f"a service class (got {got}). A service class is a Python type derived from "
        "BaseService, set in conf.py's needs_services or registered through the API; "
        "a needs_from_toml file can hold a service's options but not its class "
        "[needs.config]"
    )


def class_init_warning(name: str, got: str) -> str:
    return (
        f"WARNING: needs_services entry {name!r} is not registered: its 'class_init' is "
        "not a dict of keyword arguments for the service class "
        f"(got {got}) [needs.config]"
    )


@pytest.fixture
def build(make_app, tmp_path):
    """Write a project, build it, and return the application."""

    def _build(files: dict[str, str], *, run: bool = True, **kwargs):
        srcdir = tmp_path / "src"
        for name, content in {"index.rst": RST, **files}.items():
            path = srcdir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(content), encoding="utf-8")
        app = make_app(srcdir=srcdir, freshenv=True, **kwargs)
        if run:
            app.build()
        return app

    return _build


def registered(app) -> set[str]:
    """The names of the services the build registered."""
    return set(app._needs_services.services)


def test_a_string_class_in_the_toml_warns_and_the_service_is_skipped(build):
    """The reproduction of #2067: from a TOML file ``class`` can only be a string."""
    app = build(
        {
            "conf.py": TOML_CONF,
            "ubproject.toml": """\
                [needs.services.foo]
                class = "x"
                class_init = {}
                """,
        }
    )
    assert build_warnings(app) == [class_warning("foo", "a value of type 'str'")]
    assert app.statuscode == 0
    assert registered(app) == BUILT_IN


@pytest.mark.parametrize(
    ("value", "got"),
    [
        pytest.param('"x"', "a value of type 'str'", id="string"),
        pytest.param("None", "a value of type 'NoneType'", id="none"),
        pytest.param("dict", "the class 'dict'", id="not-a-service-class"),
    ],
)
def test_a_class_in_conf_py_that_is_not_a_service_class_warns(build, value, got):
    """The same check covers a wrong value in ``conf.py``, with the same warning."""
    app = build(
        {
            "conf.py": f"""\
                extensions = ["sphinx_needs"]
                needs_services = {{"bad": {{"class": {value}, "class_init": {{}}}}}}
                # Sphinx's own warning that a class in the configuration is not
                # pickled, which is not what these tests are about
                suppress_warnings = ["config.cache"]
                """
        }
    )
    assert build_warnings(app) == [class_warning("bad", got)]
    assert app.statuscode == 0
    assert registered(app) == BUILT_IN


def test_a_class_init_that_is_not_a_dict_warns_and_the_service_is_skipped(build):
    """A real service class with a ``class_init`` that cannot be keyword arguments."""
    app = build(
        {
            "conf.py": """\
                from tests.test_services.test_service_basics import NoDebugService

                extensions = ["sphinx_needs"]
                needs_services = {
                    "bad": {"class": NoDebugService, "class_init": "notadict"}
                }
                suppress_warnings = ["config.cache"]
                """
        }
    )
    assert build_warnings(app) == [class_init_warning("bad", "a value of type 'str'")]
    assert app.statuscode == 0
    assert registered(app) == BUILT_IN


def test_a_needservice_naming_a_skipped_service_reports_it_as_not_found(build):
    """The skipped service is simply absent: a ``needservice`` naming it takes the
    existing "could not be found" path, which this change leaves as it is -- after the
    configuration warning, which names the cause."""
    app = build(
        {
            "conf.py": TOML_CONF,
            "ubproject.toml": """\
                [needs.services.foo]
                class = "x"
                class_init = {}
                """,
            "index.rst": RST + "\n.. needservice:: foo\n",
        },
        run=False,
    )
    with pytest.raises(NeedsServiceException, match="Service foo could not be found"):
        app.build()
    assert build_warnings(app) == [class_warning("foo", "a value of type 'str'")]


@pytest.mark.parametrize(
    "toml",
    [
        # the options of a built-in service
        pytest.param(
            """\
            [needs.services.github-issues]
            url = "https://api.github.com/"
            max_content_lines = 20
            """,
            id="built-in-options",
        ),
        # the options of a service an extension registers
        pytest.param('[needs.services.foo]\nurl = "x"\n', id="options-only"),
        # no class: nothing to register from the configuration
        pytest.param(
            '[needs.services.foo]\nclass_init = {gh_type = "issue"}\n',
            id="class-init-without-class",
        ),
    ],
)
def test_a_toml_service_table_without_a_class_is_not_a_mistake(build, toml):
    """A table that holds options only configures a built-in service or one registered
    by an extension: no warning, and nothing is registered from it."""
    app = build({"conf.py": TOML_CONF, "ubproject.toml": toml})
    assert_no_warnings(app)
    assert app.statuscode == 0
    assert registered(app) == BUILT_IN


#: A service class an extension registers itself, here from ``conf.py``'s ``setup``;
#: every instance it creates records the configuration it was given.
API_CONF = """\
    from sphinx_needs.data import SphinxNeedsData
    from sphinx_needs.services.base import BaseService

    extensions = ["sphinx_needs"]
    needs_from_toml = "ubproject.toml"


    class Svc(BaseService):
        options = []
        configs = []

        def __init__(self, app, name, config, **kwargs):
            Svc.configs.append(dict(config))
            super().__init__()

        def request(self, options):
            return []


    def _register(app, env, docnames):
        SphinxNeedsData(env).get_or_create_services().register("svc", Svc)


    def setup(app):
        app.connect("env-before-read-docs", _register)
    """


def test_a_class_registered_by_an_extension_takes_its_options_from_the_toml(build):
    """The supported split: the class is Python, registered once through the API, and
    the TOML table holds its options -- which the service is given, with no warning."""
    app = build(
        {
            "conf.py": API_CONF,
            "ubproject.toml": '[needs.services.svc]\nurl = "https://example.org"\n',
        }
    )
    assert_no_warnings(app)
    assert registered(app) == BUILT_IN | {"svc"}
    service_class = type(app._needs_services.services["svc"])
    assert service_class.configs == [{"url": "https://example.org"}]


def test_a_toml_services_table_replaces_the_needs_services_of_conf_py(build):
    """Measured, and unchanged: like every ``[needs]`` key, the TOML file's ``services``
    replaces the whole ``needs_services`` of ``conf.py``, so a class set there for a
    service the TOML file also configures is not read -- and that is no mistake of the
    TOML table's, so there is no warning."""
    app = build(
        {
            "conf.py": """\
                from tests.test_services.test_service_basics import NoDebugService

                extensions = ["sphinx_needs"]
                needs_from_toml = "ubproject.toml"
                needs_services = {
                    "svc": {"class": NoDebugService, "class_init": {}, "a": 1}
                }
                """,
            "ubproject.toml": '[needs.services.svc]\nurl = "https://example.org"\n',
        }
    )
    assert_no_warnings(app)
    assert app.config.needs_services == {"svc": {"url": "https://example.org"}}
    assert registered(app) == BUILT_IN
