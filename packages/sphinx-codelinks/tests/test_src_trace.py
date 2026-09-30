# @Test suite for Sphinx extension source tracing functionality, TEST_EXT_1, test, [IMPL_LNK_1, IMPL_ONE_1, IMPL_MRST_1]
import os
import shutil
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path

import pytest
import sphinx
from sphinx.environment import CONFIG_OK
from sphinx.testing.util import SphinxTestApp

from sphinx_codelinks.analyse.projects import AnalyseProjects
from sphinx_codelinks.config import (
    SRC_TRACE_CACHE,
    CodeLinksConfig,
    check_configuration,
)
from sphinx_codelinks.sphinx_extension.source_tracing import set_config_to_sphinx
from sphinx_needs_testkit import assert_no_warnings, build_warnings


@pytest.mark.parametrize(
    ("codelinks_config", "result"),
    [
        (
            {
                "remote_url_field": 555,
                "local_url_field": 789,
                "set_local_url": "fdd",
                "set_remote_url": "TrueString",
                "projects": {
                    "dcdc": {
                        "remote_url_pattern": 44332,
                        "source_discover": {
                            "comment_type": "java",
                            "src_dir": ["../dcdc"],
                            "exclude": [123],
                            "include": [345],
                            "gitignore": "_true",
                        },
                        "analyse": {
                            "oneline_comment_style": {
                                "start_sequence": "[[",
                                "end_sequence": "]]",
                                "field_split_char": ",",
                                "needs_fields": [
                                    {
                                        "name": "title",
                                        "type": "list[]",
                                    },
                                    {
                                        "name": "type",
                                        "default": "impl",
                                        "type": "str",
                                    },
                                ],
                            },
                        },
                    }
                },
            },
            [
                "Project 'dcdc' has the following errors:",
                "Schema validation error in field 'exclude': 123 is not of type 'string'",
                "Schema validation error in field 'comment_type': 'java' is not one of ['bash', 'cpp', 'cs', 'go', 'jsonc', 'python', 'rust', 'yaml']",
                "Schema validation error in field 'gitignore': '_true' is not of type 'boolean'",
                "Schema validation error in field 'include': 345 is not of type 'string'",
                "Schema validation error in field 'src_dir': ['../dcdc'] is not of type 'string'",
                "Schema validation error in filed 'local_url_field': 789 is not of type 'string'",
                "Schema validation error in filed 'remote_url_field': 555 is not of type 'string'",
                "Schema validation error in filed 'set_local_url': 'fdd' is not of type 'boolean'",
                "Schema validation error in filed 'set_remote_url': 'TrueString' is not of type 'boolean'",
                "OneLineCommentStyle configuration errors:",
                "Schema validation error in need_fields 'title': 'list[]' is not one of ['str', 'list[str]']",
                "remote_url_pattern must be a string",
            ],
        ),
        (
            {
                "remote_url_field": "remote-url",
                "local_url_field": "local-url",
                "set_local_url": True,
                "set_remote_url": True,
                "projects": {
                    "dcdc": {
                        # intentionally not given "remote_url_pattern": "https://github.com/useblocks/sphinx-codelinks/blob/{commit}/{path}#L{line}",
                        "source_discover": {
                            "comment_type": "cpp",
                            "src_dir": "../dcdc",
                            "exclude": [],
                            "include": [],
                            "gitignore": True,
                        },
                        "analyse": {
                            "oneline_comment_style": {
                                "start_sequence": "[[",
                                "end_sequence": "]]",
                                "field_split_char": ",",
                                "needs_fields": [
                                    {
                                        "name": "title",
                                        "type": "str",
                                    },
                                    {
                                        "name": "type",
                                        "default": "impl",
                                        "type": "str",
                                    },
                                ],
                            },
                        },
                    }
                },
            },
            [
                "Project 'dcdc' has the following errors:",
                "remote_url_pattern must be given, as set_remote_url is enabled",
            ],
        ),
    ],
)
def test_src_tracing_config_negative(
    make_app: Callable[..., SphinxTestApp],
    codelinks_config,
    result,
):
    this_file_dir = Path(__file__).parent
    sphinx_project = Path("data") / "sphinx"
    app = make_app(srcdir=(this_file_dir / sphinx_project))
    set_config_to_sphinx(codelinks_config, app.env.config)
    codelinks_sphinx_config = CodeLinksConfig.from_sphinx(app.env.config)
    errors = check_configuration(codelinks_sphinx_config)
    assert sorted(errors) == sorted(result)


def test_src_tracing_config_positive(make_app: Callable[..., SphinxTestApp], tmp_path):
    codelinks_config = {
        "remote_url_field": "remote-url",
        "local_url_field": "local-url",
        "set_local_url": True,
        "set_remote_url": True,
        "outdir": tmp_path,
        "projects": {
            "dcdc": {
                "source_discover": {
                    "comment_type": "cpp",
                    "src_dir": "../dcdc",
                    "exclude": ["**/*.hpp"],
                    "include": ["**/*.cpp"],
                    "gitignore": True,
                },
                "remote_url_pattern": "https://github.com/useblocks/sphinx-codelinks/blob/{commit}/{path}#L{line}",
                "analyse": {
                    "oneline_comment_style": {
                        "start_sequence": "[[",
                        "end_sequence": "]]",
                        "field_split_char": ",",
                        "needs_fields": [
                            {
                                "name": "title",
                                "type": "str",
                            },
                            {
                                "name": "type",
                                "default": "impl",
                                "type": "str",
                            },
                        ],
                    },
                },
            }
        },
    }
    this_file_dir = Path(__file__).parent
    sphinx_project = Path("data") / "sphinx"
    app = make_app(srcdir=(this_file_dir / sphinx_project))
    set_config_to_sphinx(codelinks_config, app.env.config)
    codelinks_sphinx_config = CodeLinksConfig.from_sphinx(app.env.config)
    errors = check_configuration(codelinks_sphinx_config)
    assert not errors


@pytest.mark.parametrize(
    ("sphinx_project", "source_code"),
    [
        (Path("data") / "sphinx", Path("data") / "dcdc"),
        (
            Path("doc_test") / "recursive_dirs",
            Path("doc_test") / "recursive_dirs" / "dummy_src_lv1",
        ),
        (
            Path("doc_test") / "minimum_config",
            Path("doc_test") / "minimum_config",
        ),
        (
            Path("doc_test") / "id_required",
            Path("doc_test") / "id_required",
        ),
        (
            Path("doc_test") / "cs_basic",
            Path("doc_test") / "cs_basic",
        ),
        (
            Path("doc_test") / "go_basic",
            Path("doc_test") / "go_basic",
        ),
    ],
)
def test_build_html(
    tmpdir: Path,
    make_app: Callable[..., SphinxTestApp],
    sphinx_project,
    source_code,
    snapshot_doctree,
):
    this_file_dir = Path(__file__).parent

    sphinx_src_dir = tmpdir / sphinx_project
    shutil.copytree(
        this_file_dir / sphinx_project,
        sphinx_src_dir,
        dirs_exist_ok=True,
    )
    shutil.copytree(
        this_file_dir / source_code,
        tmpdir / source_code,
        dirs_exist_ok=True,
    )

    app: SphinxTestApp = make_app(
        srcdir=Path(sphinx_src_dir),
        freshenv=True,
    )
    app.build()

    html = Path(app.outdir, "index.html").read_text()
    assert html

    warnings = AnalyseProjects.load_warnings(Path(app.outdir) / SRC_TRACE_CACHE)
    assert not warnings

    assert app.env.get_doctree("index") == snapshot_doctree


def test_incremental_build_keeps_src_trace_projects_unchanged(
    tmpdir: Path,
    make_app: Callable[..., SphinxTestApp],
) -> None:
    """An incremental rebuild with no source changes must not invalidate the env.

    Regression test for the ``src-trace`` directive mutating the ``analyse_config``
    object stored inside the ``rebuild="env"`` ``src_trace_projects`` config value.
    The mutated object (populated ``src_dir``/``src_files``) was persisted into
    ``environment.pickle``, so every incremental build compared it against the
    freshly generated (empty) config and reported
    ``[config changed ('src_trace_projects')]``, forcing a full re-read.
    """
    this_file_dir = Path(__file__).parent
    sphinx_project = Path("data") / "sphinx"
    source_code = Path("data") / "dcdc"

    sphinx_src_dir = Path(tmpdir) / sphinx_project
    shutil.copytree(this_file_dir / sphinx_project, sphinx_src_dir, dirs_exist_ok=True)
    shutil.copytree(
        this_file_dir / source_code, Path(tmpdir) / source_code, dirs_exist_ok=True
    )

    # First build populates environment.pickle in the shared build dir.
    make_app(srcdir=sphinx_src_dir, freshenv=True).build()

    # Second build reuses the same build dir and loads the pickled environment.
    app = make_app(srcdir=sphinx_src_dir, freshenv=False)

    captured: dict[str, object] = {}

    def capture_config_status(_app, env, _added, _changed, _removed):
        # ``env-get-outdated`` fires during read() after the config comparison
        # but before config_status is reset to CONFIG_OK at the end of read().
        captured["status"] = env.config_status
        captured["extra"] = env.config_status_extra
        return []

    app.connect("env-get-outdated", capture_config_status)
    app.build()

    assert captured["status"] == CONFIG_OK, (
        f"incremental build wrongly invalidated the environment: "
        f"config changed{captured.get('extra')}"
    )


@pytest.fixture
def minimal_sphinx_project(tmp_path: Path) -> Path:
    """Minimal Sphinx project with no TOML config file next to conf.py."""
    (tmp_path / "conf.py").write_text(
        "extensions = ['sphinx_needs', 'sphinx_codelinks']\n"
        "exclude_patterns = ['_build']\n"
    )
    (tmp_path / "index.rst").write_text("Minimal project\n===============\n")
    return tmp_path


def test_config_from_toml_defaults_to_ubproject_toml() -> None:
    """The default config file is the shared ubproject.toml (ubcode-pub#75)."""
    config_field = next(
        field for field in fields(CodeLinksConfig) if field.name == "config_from_toml"
    )
    assert config_field.default == "ubproject.toml"


def test_default_ubproject_toml_is_loaded(
    minimal_sphinx_project: Path,
    make_app: Callable[..., SphinxTestApp],
) -> None:
    """An ubproject.toml next to conf.py is loaded without any conf.py entry."""
    (minimal_sphinx_project / "ubproject.toml").write_text(
        "[codelinks.projects.demo]\n"
        'remote_url_pattern = "https://example.com/{commit}/{path}#L{line}"\n'
        "\n"
        "[codelinks.projects.demo.source_discover]\n"
        'src_dir = "./"\n'
    )
    app = make_app(srcdir=minimal_sphinx_project, freshenv=True)
    app.build()

    assert "demo" in app.config.src_trace_projects
    assert_no_warnings(app)


def test_default_ubproject_toml_without_codelinks_section_is_silent(
    minimal_sphinx_project: Path,
    make_app: Callable[..., SphinxTestApp],
) -> None:
    """A default ubproject.toml used by other tools but without [codelinks] is
    silently ignored instead of warning."""
    (minimal_sphinx_project / "ubproject.toml").write_text(
        "[needs]\nid_required = true\n"
    )
    app = make_app(srcdir=minimal_sphinx_project, freshenv=True)
    app.build()

    assert app.config.src_trace_projects == {}
    assert_no_warnings(app)


def test_missing_default_ubproject_toml_is_silent(
    minimal_sphinx_project: Path,
    make_app: Callable[..., SphinxTestApp],
) -> None:
    """Without an ubproject.toml next to conf.py, the conf.py configuration is
    used and no warning is emitted."""
    app = make_app(srcdir=minimal_sphinx_project, freshenv=True)
    app.build()

    assert app.config.src_trace_projects == {}
    assert_no_warnings(app)


def test_explicit_toml_config_missing_warns(
    minimal_sphinx_project: Path,
    make_app: Callable[..., SphinxTestApp],
) -> None:
    """An explicitly configured TOML file that does not exist still warns."""
    conf_py = minimal_sphinx_project / "conf.py"
    conf_py.write_text(
        conf_py.read_text() + '\nsrc_trace_config_from_toml = "nonexistent.toml"\n'
    )
    app = make_app(srcdir=minimal_sphinx_project, freshenv=True)
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert "does not exist" in warnings[0]


# -- the TOML reader: what a -D value, a corrupt file and the typed warnings do ----------

#: Sphinx 8 renders a warning's ``[type.subtype]`` itself; 7.4 appends nothing, so on
#: 7.4 the reader's warnings are asserted by their phrase and count only
_SHOWS_WARNING_TYPES = sphinx.version_info >= (8,)

_LOAD_FAILED = "Failed to load source tracing configuration"


def _write_conf(project: Path, extra: str) -> None:
    conf_py = project / "conf.py"
    conf_py.write_text(conf_py.read_text(encoding="utf-8") + extra, encoding="utf-8")


def _assert_one_config_warning(app: SphinxTestApp, phrase: str) -> None:
    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert phrase in warnings[0]
    if _SHOWS_WARNING_TYPES:
        assert "[codelinks.config]" in warnings[0]


@pytest.mark.parametrize(
    ("key", "toml_value", "override"),
    [
        ("set_local_url", "true", False),
        ("set_remote_url", "true", False),
        ("local_url_field", '"toml-url"', "cli-url"),
        ("remote_url_field", '"toml-remote"', "cli-remote"),
        ("debug_measurement", "true", False),
        ("debug_filters", "true", False),
    ],
)
def test_command_line_override_beats_the_toml(
    minimal_sphinx_project: Path,
    make_app: Callable[..., SphinxTestApp],
    key: str,
    toml_value: str,
    override: object,
) -> None:
    """``-D src_trace_<key>`` wins over the same key in ``[codelinks]``.

    ``confoverrides`` is what ``-D`` becomes: Sphinx stores both in ``config.overrides``.
    """
    (minimal_sphinx_project / "ubproject.toml").write_text(
        f"[codelinks]\n{key} = {toml_value}\n", encoding="utf-8"
    )
    app = make_app(
        srcdir=minimal_sphinx_project,
        freshenv=True,
        confoverrides={f"src_trace_{key}": override},
    )

    assert app.config[f"src_trace_{key}"] == override


def test_refused_outdir_override_leaves_the_default(
    minimal_sphinx_project: Path,
    make_app: Callable[..., SphinxTestApp],
) -> None:
    """A PIN of the measured cell, not an endorsement: Sphinx refuses
    ``-D src_trace_outdir`` (its default is a ``Path``: "unsupported type") but keeps it
    in ``config.overrides``, so the TOML's ``outdir`` is skipped as well and the default
    stands. Inert for a build: the extension never reads ``src_trace_outdir`` (the CLI,
    which does, has no ``-D``)."""
    (minimal_sphinx_project / "ubproject.toml").write_text(
        '[codelinks]\noutdir = "toml-out"\n', encoding="utf-8"
    )
    app = make_app(
        srcdir=minimal_sphinx_project,
        freshenv=True,
        confoverrides={"src_trace_outdir": "cli-out"},
    )

    assert app.config.src_trace_outdir == Path("output")


def test_command_line_override_of_config_from_toml_beats_the_toml(
    minimal_sphinx_project: Path,
    make_app: Callable[..., SphinxTestApp],
) -> None:
    """The eighth key: a ``config_from_toml`` inside the file no longer rewrites the
    file name given with ``-D``."""
    (minimal_sphinx_project / "cl.toml").write_text(
        '[codelinks]\nconfig_from_toml = "deep/x.toml"\n', encoding="utf-8"
    )
    app = make_app(
        srcdir=minimal_sphinx_project,
        freshenv=True,
        confoverrides={"src_trace_config_from_toml": "cl.toml"},
    )

    assert app.config.src_trace_config_from_toml == "cl.toml"


def test_bare_name_override_does_not_suppress_the_toml(
    minimal_sphinx_project: Path,
    make_app: Callable[..., SphinxTestApp],
) -> None:
    """``-D set_local_url=0`` names no confval -- Sphinx warns and ignores it -- so the
    TOML value stands; only ``src_trace_<key>`` counts as an override."""
    (minimal_sphinx_project / "ubproject.toml").write_text(
        "[codelinks]\nset_local_url = true\n", encoding="utf-8"
    )
    app = make_app(
        srcdir=minimal_sphinx_project,
        freshenv=True,
        confoverrides={"set_local_url": False},
    )

    assert app.config.src_trace_set_local_url is True


def test_refused_projects_override_keeps_the_toml_projects(
    minimal_sphinx_project: Path,
    make_app: Callable[..., SphinxTestApp],
) -> None:
    """``-D src_trace_projects=x`` is refused by Sphinx (a dict cannot be overridden
    whole) but stays in ``config.overrides``: the TOML's projects must still load."""
    (minimal_sphinx_project / "ubproject.toml").write_text(
        '[codelinks.projects.tomlproj.source_discover]\nsrc_dir = "./"\n',
        encoding="utf-8",
    )
    app = make_app(
        srcdir=minimal_sphinx_project,
        freshenv=True,
        confoverrides={"src_trace_projects": "x"},
    )

    assert list(app.config.src_trace_projects) == ["tomlproj"]


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        pytest.param({"src_trace_local_url_field": "cli-url"}, "cli-url", id="D-wins"),
        pytest.param({}, "toml-url", id="conf.py-vs-toml-unchanged"),
    ],
)
def test_command_line_then_toml_then_conf_py(
    minimal_sphinx_project: Path,
    make_app: Callable[..., SphinxTestApp],
    override: dict[str, str],
    expected: str,
) -> None:
    """One key set in all three places: ``-D`` > TOML > conf.py."""
    _write_conf(minimal_sphinx_project, 'src_trace_local_url_field = "conf-url"\n')
    (minimal_sphinx_project / "ubproject.toml").write_text(
        '[codelinks]\nlocal_url_field = "toml-url"\n', encoding="utf-8"
    )
    app = make_app(srcdir=minimal_sphinx_project, freshenv=True, confoverrides=override)

    assert app.config.src_trace_local_url_field == expected


def _syntax_error(path: Path) -> None:
    path.write_text("[codelinks\n", encoding="utf-8")


def _not_utf8(path: Path) -> None:
    path.write_bytes(b'[codelinks]\nlocal_url_field = "caf\xe9"\n')


def _a_directory(path: Path) -> None:
    path.mkdir()


def _not_a_table(path: Path) -> None:
    path.write_text('codelinks = "x"\n', encoding="utf-8")


_CORRUPT_FILES = [
    pytest.param(_syntax_error, id="syntax-error"),
    pytest.param(_not_utf8, id="not-utf8"),
    pytest.param(_a_directory, id="a-directory"),
    pytest.param(_not_a_table, id="codelinks-not-a-table"),
]


@pytest.mark.parametrize("corrupt", _CORRUPT_FILES)
def test_corrupt_default_ubproject_toml_warns(
    minimal_sphinx_project: Path,
    make_app: Callable[..., SphinxTestApp],
    corrupt: Callable[[Path], None],
) -> None:
    """A default ubproject.toml that exists but cannot be read or parsed warns, as any
    configured file did at 1.4.0 -- only a missing file or table is silent."""
    corrupt(minimal_sphinx_project / "ubproject.toml")
    app = make_app(srcdir=minimal_sphinx_project, freshenv=True)
    app.build()

    assert app.config.src_trace_projects == {}
    _assert_one_config_warning(app, _LOAD_FAILED)


def test_explicit_toml_without_codelinks_table_warns(
    minimal_sphinx_project: Path,
    make_app: Callable[..., SphinxTestApp],
) -> None:
    """An explicitly configured file without ``[codelinks]`` warns, and says so."""
    _write_conf(minimal_sphinx_project, 'src_trace_config_from_toml = "cl.toml"\n')
    (minimal_sphinx_project / "cl.toml").write_text(
        "[needs]\nid_required = true\n", encoding="utf-8"
    )
    app = make_app(srcdir=minimal_sphinx_project, freshenv=True)
    app.build()

    _assert_one_config_warning(app, "has no [codelinks] table")


@pytest.mark.parametrize(
    "state",
    [
        pytest.param(None, id="missing"),
        pytest.param(_syntax_error, id="syntax-error"),
        pytest.param(
            lambda path: path.write_text("[needs]\n", encoding="utf-8"),
            id="no-codelinks-table",
        ),
    ],
)
def test_reader_warnings_are_suppressible(
    minimal_sphinx_project: Path,
    make_app: Callable[..., SphinxTestApp],
    state: Callable[[Path], object] | None,
) -> None:
    """Every warning of the reader carries ``codelinks.config``."""
    _write_conf(
        minimal_sphinx_project,
        'src_trace_config_from_toml = "cl.toml"\n'
        'suppress_warnings = ["codelinks.config"]\n',
    )
    if state is not None:
        state(minimal_sphinx_project / "cl.toml")
    app = make_app(srcdir=minimal_sphinx_project, freshenv=True)
    app.build()

    assert_no_warnings(app)


_MARKER = "# @Found here {tag}, IMPL_{tag}, impl\n"


def _traced_project(root: Path, conf_extra: str, files: dict[str, str]) -> None:
    """A project whose index traces project ``p``; ``files`` maps a relative path to
    its content, and a ``LINK:<target>`` content makes that path a symlink."""
    (root / "conf.py").write_text(
        "extensions = ['sphinx_needs', 'sphinx_codelinks']\n"
        "exclude_patterns = ['_build']\n" + conf_extra,
        encoding="utf-8",
    )
    (root / "index.rst").write_text(
        "T\n=\n\n.. src-trace::\n   :project: p\n", encoding="utf-8"
    )
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if content.startswith("LINK:"):
            try:
                os.symlink(content[len("LINK:") :], path)
            except (OSError, NotImplementedError) as error:
                pytest.skip(f"cannot create a symlink here: {error}")
        else:
            path.write_text(content, encoding="utf-8")


_PROJECT_P = '[codelinks.projects.p.source_discover]\nsrc_dir = "./src"\ncomment_type = "python"\n'


def test_symlinked_toml_anchors_at_the_links_directory(
    tmp_path: Path,
    make_app: Callable[..., SphinxTestApp],
) -> None:
    """A relative path in a TOML reached through a symlink is anchored at the LINK's
    directory -- ``confdir / Path(config_from_toml).parent`` -- not the target's."""
    _traced_project(
        tmp_path,
        "src_trace_config_from_toml = 'cl.toml'\n",
        {
            "other/sub/real.toml": _PROJECT_P,
            "cl.toml": "LINK:" + str(Path("other", "sub", "real.toml")),
            "src/a.py": _MARKER.format(tag="LINKDIR"),
            "other/sub/src/a.py": _MARKER.format(tag="REALDIR"),
        },
    )
    app = make_app(srcdir=tmp_path, freshenv=True)
    app.build()

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "IMPL_LINKDIR" in html
    assert "IMPL_REALDIR" not in html


def test_config_from_toml_set_in_the_toml_moves_the_anchor(
    tmp_path: Path,
    make_app: Callable[..., SphinxTestApp],
) -> None:
    """A PIN of today's behaviour, not an endorsement: ``config_from_toml`` is a key the
    TOML may set, and when it does the use-site anchor moves to that name's directory
    (the named file is never read)."""
    _traced_project(
        tmp_path,
        "",
        {
            "ubproject.toml": _PROJECT_P
            + "[codelinks]\nconfig_from_toml = 'deep/x.toml'\n",
            "src/a.py": _MARKER.format(tag="CONFDIR"),
            "deep/src/a.py": _MARKER.format(tag="DEEPDIR"),
        },
    )
    app = make_app(srcdir=tmp_path, freshenv=True)
    app.build()

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "IMPL_DEEPDIR" in html
    assert "IMPL_CONFDIR" not in html
