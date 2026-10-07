# @Test suite for the ref_url_field configuration, TEST_NEED_ID_REFS_CONFIG_1, test, [IMPL_LNK_1]
"""``ref_url_field``: ubCode's per-project key, accepted by both readers, and its gate."""

from collections.abc import Callable
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_codelinks.config import (
    CodeLinksConfig,
    check_configuration,
    generate_project_configs,
    need_id_refs_field,
)
from sphinx_needs_testkit import assert_no_warnings

_TOML_HEAD = "[codelinks]\nset_remote_url = true\n\n"
_PROJECT = (
    "[codelinks.projects.p]\n"
    'remote_url_pattern = "https://example.com/{commit}/{path}#L{line}"\n'
    "EXTRA"
    "[codelinks.projects.p.source_discover]\n"
    'src_dir = "./src"\n'
)


def _project(root: Path, *, toml: str | None = None, conf_extra: str = "") -> Path:
    (root / "conf.py").write_text(
        "extensions = ['sphinx_needs', 'sphinx_codelinks']\n"
        "exclude_patterns = ['_build']\n" + conf_extra,
        encoding="utf-8",
    )
    (root / "index.rst").write_text("T\n=\n", encoding="utf-8")
    (root / "src").mkdir()
    if toml is not None:
        (root / "ubproject.toml").write_text(toml, encoding="utf-8")
    return root


def test_toml_accepts_ref_url_field(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """ubCode's ``ref_url_field`` in a shared ``ubproject.toml`` is no longer a hard
    error (``Additional properties are not allowed ('ref_url_field' was unexpected)``)."""
    _project(
        tmp_path,
        toml=_TOML_HEAD + _PROJECT.replace("EXTRA", 'ref_url_field = "impl_url"\n'),
    )
    app = make_app(srcdir=tmp_path, freshenv=True)
    app.build()

    assert_no_warnings(app)
    assert app.config.src_trace_projects["p"]["ref_url_field"] == "impl_url"
    assert "impl_url" in app.config.needs_string_links


def test_conf_py_accepts_ref_url_field(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    _project(
        tmp_path,
        conf_extra=(
            "src_trace_config_from_toml = None\n"
            "src_trace_set_remote_url = True\n"
            "src_trace_projects = {'p': {\n"
            "    'remote_url_pattern': 'https://example.com/{commit}/{path}#L{line}',\n"
            "    'ref_url_field': 'impl_url',\n"
            "    'source_discover': {'src_dir': './src'},\n"
            "}}\n"
        ),
    )
    app = make_app(srcdir=tmp_path, freshenv=True)
    app.build()

    assert_no_warnings(app)
    assert "impl_url" in app.config.needs_string_links


@pytest.mark.parametrize(
    ("value", "error"),
    [
        pytest.param(5, "ref_url_field must be a string", id="not-a-string"),
        pytest.param(
            "remote-url",
            "ref_url_field 'remote-url' must differ from local_url_field and "
            "remote_url_field",
            id="the-remote-url-field",
        ),
    ],
)
def test_invalid_ref_url_field_is_a_configuration_error(
    value: object, error: str
) -> None:
    projects = {
        "p": {
            "remote_url_pattern": "https://example.com/{path}",
            "ref_url_field": value,
            "source_discover": {"src_dir": "./src"},
        }
    }
    generate_project_configs(projects)  # ty: ignore[invalid-argument-type]
    config = CodeLinksConfig(set_remote_url=True, projects=projects)  # ty: ignore[invalid-argument-type]

    errors = check_configuration(config)
    assert errors == ["Project 'p' has the following errors:", error]


def _gate(
    *,
    set_remote_url: bool = True,
    set_local_url: bool = False,
    project: dict[str, object] | None = None,
) -> str | None:
    project_config: dict[str, object] = {
        "remote_url_pattern": "https://example.com/{path}",
        "source_discover": {"src_dir": "./src"},
        **(project or {}),
    }
    projects = {"p": project_config}
    generate_project_configs(projects)  # ty: ignore[invalid-argument-type]
    config = CodeLinksConfig(
        set_remote_url=set_remote_url,
        set_local_url=set_local_url,
        projects=projects,  # ty: ignore[invalid-argument-type]
    )
    return need_id_refs_field(config, config.projects["p"])


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        pytest.param({}, "code_url", id="default-field"),
        pytest.param(
            {"set_remote_url": False, "set_local_url": True},
            "code_url",
            id="local-urls-only",
        ),
        pytest.param({"set_remote_url": False}, None, id="no-urls"),
        pytest.param({"project": {"ref_url_field": ""}}, None, id="empty-field"),
        pytest.param(
            {"project": {"ref_url_field": "test_url"}}, "test_url", id="named-field"
        ),
        pytest.param(
            {"project": {"analyse": {"get_need_id_refs": False}}},
            None,
            id="refs-not-extracted",
        ),
        pytest.param(
            {"project": {"analyse": {"need_id_refs": {"markers": []}}}},
            None,
            id="no-markers",
        ),
    ],
)
def test_attach_gate(kwargs: dict[str, object], expected: str | None) -> None:
    """ubCode's gate: URLs on, references extracted, a marker, and a non-empty field."""
    assert _gate(**kwargs) == expected  # ty: ignore[invalid-argument-type]
