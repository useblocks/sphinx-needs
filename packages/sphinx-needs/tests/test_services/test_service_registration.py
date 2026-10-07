"""Registering the services configured in ``needs_services`` (#2067).

A service is registered from its configuration when the entry has both ``class`` and
``class_init``. A ``class`` that is not callable -- the only thing a
``needs_from_toml`` file can give it is a string -- or has no ``options`` used to end the
build with ``'str' object has no attribute 'options'`` at ``env-before-read-docs``, and
a ``class_init`` that is not a mapping ended it in the keyword expansion. Such an entry is now
skipped with one ``needs.config`` warning, and the build goes on; anything that
registered before still does. Each test is a real build, because the registration
happens in ``prepare_env``.
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


def class_warning(name: str, problem: str) -> str:
    return (
        f"WARNING: needs_services entry {name!r} is not registered: {problem}. "
        "A service class derives from BaseService and is set in conf.py's "
        "needs_services or registered through the API; a needs_from_toml file can "
        "hold a service's options but not its class [needs.config]"
    )


def not_callable(type_name: str) -> str:
    return f"its 'class' is not callable (got a value of type {type_name!r})"


def no_options(class_name: str) -> str:
    return f"its 'class' {class_name!r} has no 'options', which a service class needs"


def class_init_warning(name: str, got: str) -> str:
    return (
        f"WARNING: needs_services entry {name!r} is not registered: its 'class_init' is "
        "not a mapping of keyword arguments for the service class "
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
    assert build_warnings(app) == [class_warning("foo", not_callable("str"))]
    assert registered(app) == BUILT_IN


@pytest.mark.parametrize(
    ("value", "problem"),
    [
        pytest.param('"x"', not_callable("str"), id="string"),
        pytest.param("None", not_callable("NoneType"), id="none"),
        # callable, but without the ``options`` the registration reads first
        pytest.param("a_function", no_options("a_function"), id="function"),
        # a type, but without the ``options`` the registration reads first
        pytest.param("dict", no_options("dict"), id="class-without-options"),
    ],
)
def test_a_class_in_conf_py_that_would_crash_the_registration_warns(
    build, value, problem
):
    """The same check covers a wrong value in ``conf.py``, with the same warning:
    everything that is not callable, and a callable without ``options``."""
    app = build(
        {
            "conf.py": f"""\
                extensions = ["sphinx_needs"]


                def a_function(app):
                    pass


                needs_services = {{"bad": {{"class": {value}, "class_init": {{}}}}}}
                # Sphinx's own warning that a class in the configuration is not
                # pickled, which is not what these tests are about
                suppress_warnings = ["config.cache"]
                """
        }
    )
    assert build_warnings(app) == [class_warning("bad", problem)]
    assert registered(app) == BUILT_IN


def test_a_duck_typed_service_class_registers_as_before(build):
    """A class with ``options`` that does not derive from ``BaseService`` registered
    before this check existed, and still does, without a warning: the check refuses
    only what used to end the build."""
    app = build(
        {
            "conf.py": """\
                extensions = ["sphinx_needs"]


                class Duck:
                    options = []

                    def __init__(self, app, name, config, **kwargs):
                        pass

                    def request(self, options):
                        return []


                needs_services = {"duck": {"class": Duck, "class_init": {}}}
                suppress_warnings = ["config.cache"]
                """
        }
    )
    assert_no_warnings(app)
    assert registered(app) == BUILT_IN | {"duck"}
    assert type(app._needs_services.services["duck"]).__name__ == "Duck"


def test_a_callable_factory_with_options_registers_as_before(build):
    """The registration reads ``options`` and then calls the ``class``: a factory
    function carrying ``options`` registered before this check existed, and still
    does, without a warning."""
    app = build(
        {
            "conf.py": """\
                extensions = ["sphinx_needs"]


                class Made:
                    def __init__(self, app, name, config, **kwargs):
                        pass

                    def request(self, options):
                        return []


                def factory(app, name, config, **kwargs):
                    return Made(app, name, config, **kwargs)


                factory.options = []
                needs_services = {"svc": {"class": factory, "class_init": {}}}
                suppress_warnings = ["config.cache"]
                """
        }
    )
    assert_no_warnings(app)
    assert registered(app) == BUILT_IN | {"svc"}
    assert type(app._needs_services.services["svc"]).__name__ == "Made"


@pytest.mark.parametrize(
    "class_init",
    [
        pytest.param(
            "types.MappingProxyType({'custom_init': True})", id="mappingproxy"
        ),
        pytest.param("collections.UserDict(custom_init=True)", id="userdict"),
    ],
)
def test_a_class_init_mapping_that_is_not_a_dict_registers_as_before(build, class_init):
    """``**`` takes any mapping, so a ``class_init`` that is a mapping but not a
    ``dict`` registered before this check existed, and still does, without a warning,
    and its items reach the class."""
    app = build(
        {
            "conf.py": f"""\
                import collections
                import types

                extensions = ["sphinx_needs"]


                class Svc:
                    options = []
                    kwargs = []

                    def __init__(self, app, name, config, **kwargs):
                        Svc.kwargs.append(kwargs)

                    def request(self, options):
                        return []


                needs_services = {{"svc": {{"class": Svc, "class_init": {class_init}}}}}
                suppress_warnings = ["config.cache"]
                """
        }
    )
    assert_no_warnings(app)
    assert registered(app) == BUILT_IN | {"svc"}
    assert type(app._needs_services.services["svc"]).kwargs == [{"custom_init": True}]


def test_a_class_and_a_class_init_both_wrong_give_one_warning(build):
    """One warning per service: the ``class`` one, which is checked first."""
    app = build(
        {
            "conf.py": TOML_CONF,
            "ubproject.toml": """\
                [needs.services.foo]
                class = "x"
                class_init = "y"
                """,
        }
    )
    assert build_warnings(app) == [class_warning("foo", not_callable("str"))]
    assert registered(app) == BUILT_IN


def test_a_class_init_that_is_not_a_mapping_warns_and_the_service_is_skipped(build):
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
    assert build_warnings(app) == [class_warning("foo", not_callable("str"))]


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
