# @Test suite for Sphinx extension source tracing functionality, TEST_EXT_1, test, [IMPL_LNK_1, IMPL_ONE_1, IMPL_MRST_1]
from collections.abc import Callable
from pathlib import Path
import shutil

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_codelinks.analyse.projects import AnalyseProjects
from sphinx_codelinks.config import (
    SRC_TRACE_CACHE,
    CodeLinksConfig,
    check_configuration,
)
from sphinx_codelinks.sphinx_extension.source_tracing import set_config_to_sphinx


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
                "Schema validation error in field 'comment_type': 'java' is not one of ['cpp', 'cs', 'python', 'rust', 'yaml']",
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
