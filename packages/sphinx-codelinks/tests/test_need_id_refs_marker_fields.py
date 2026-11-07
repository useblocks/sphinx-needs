"""A field per reference marker: a ``markers`` entry is a string or a table.

A string sends its references to the project's ``ref_url_field``; a table
``{"marker": ..., "field": ...}`` sends them to its own ``field`` (``""``: to no field).
The table's field is checked as ``ref_url_field`` is, by one helper, and a marker listed
twice, in any form, is an error.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_codelinks.config import (
    CodeLinksConfig,
    NeedIdRefsConfig,
    check_configuration,
    convert_need_id_refs_config,
    declared_link_types,
    generate_project_configs,
    need_id_refs_field_names,
    need_id_refs_fields,
    need_id_refs_marker_fields,
)
from sphinx_codelinks.sphinx_extension.source_tracing import (
    check_sphinx_configuration,
)

SATISFIES = "\\satisfies"
VERIFIES = "\\verifies"
TABLES = [
    "@need-ids:",
    {"marker": SATISFIES, "field": "impl_url"},
    {"marker": VERIFIES, "field": "test_url"},
]


def _config(
    markers: list[object],
    *,
    ref_url_field: object = None,
    extra_projects: dict[str, dict[str, object]] | None = None,
) -> CodeLinksConfig:
    project: dict[str, object] = {
        "remote_url_pattern": "https://example.com/{path}#L{line}",
        "source_discover": {"src_dir": "./src"},
        "analyse": {"need_id_refs": {"markers": markers}},
    }
    if ref_url_field is not None:
        project["ref_url_field"] = ref_url_field
    projects = {"p": project, **(extra_projects or {})}
    generate_project_configs(projects)  # ty: ignore[invalid-argument-type]
    return CodeLinksConfig(set_remote_url=True, projects=projects)  # ty: ignore[invalid-argument-type]


# the configuration's shape


def test_a_string_marker_is_unchanged() -> None:
    config = NeedIdRefsConfig(markers=["@need-ids:", "REFS:"])
    assert config.markers == ["@need-ids:", "REFS:"]
    assert config.fields == {}


def test_a_table_is_resolved_to_its_text_and_its_field() -> None:
    """The resolved ``markers`` stays a list of strings -- every extraction call site
    reads it as one -- and the tables' fields go to ``fields``."""
    config = NeedIdRefsConfig(markers=TABLES)  # ty: ignore[invalid-argument-type]
    assert config.markers == ["@need-ids:", SATISFIES, VERIFIES]
    assert config.fields == {SATISFIES: "impl_url", VERIFIES: "test_url"}
    assert config.check_schema() == []


def test_an_empty_field_is_kept() -> None:
    config = NeedIdRefsConfig(markers=[{"marker": SATISFIES, "field": ""}])  # ty: ignore[invalid-argument-type]
    assert config.fields == {SATISFIES: ""}


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        pytest.param(
            {"marker": SATISFIES, "field": "impl_url", "kind": "x"},
            "markers[0]: unknown key 'kind'; a marker table takes 'marker' and 'field'",
            id="unknown-key",
        ),
        pytest.param(
            {"marker": SATISFIES},
            "markers[0]: missing 'field'; a marker table takes 'marker' and 'field'",
            id="missing-field",
        ),
        pytest.param(
            {"field": "impl_url"},
            "markers[0]: missing 'marker'; a marker table takes 'marker' and 'field'",
            id="missing-marker",
        ),
        pytest.param(
            {"marker": "", "field": "impl_url"},
            "markers[0]: 'marker' must be a non-empty string",
            id="empty-marker",
        ),
        pytest.param(
            {"marker": 5, "field": "impl_url"},
            "markers[0]: 'marker' must be a non-empty string",
            id="marker-not-a-string",
        ),
        pytest.param(
            {"marker": SATISFIES, "field": ["impl_url"]},
            "markers[0]: 'field' must be a string",
            id="field-not-a-string",
        ),
    ],
)
def test_a_malformed_table_is_refused(entry: dict[str, object], message: str) -> None:
    """Through the channel an unknown ``[need_id_refs]`` key already takes."""
    with pytest.raises(TypeError) as excinfo:
        convert_need_id_refs_config({"markers": [entry]})  # ty: ignore[invalid-argument-type]
    assert str(excinfo.value) == f"Invalid need_id_refs configuration: {message}"


def test_the_schema_describes_a_string_or_a_table() -> None:
    schema = NeedIdRefsConfig.get_schema("markers")
    assert schema is not None
    assert schema["items"]["anyOf"][0] == {"type": "string"}
    table = schema["items"]["anyOf"][1]
    assert table["required"] == ["marker", "field"]
    assert table["additionalProperties"] is False


def test_a_non_string_entry_is_still_a_schema_error() -> None:
    errors = NeedIdRefsConfig(markers=[5]).check_schema()  # ty: ignore[invalid-argument-type]
    assert len(errors) == 1
    assert errors[0].startswith("Schema validation error in field 'markers'")


# the gate: each marker's field


def test_strings_go_to_ref_url_field_and_tables_to_their_field() -> None:
    config = _config(TABLES, ref_url_field="code_url")
    assert need_id_refs_marker_fields(config, config.projects["p"]) == {
        "@need-ids:": "code_url",
        SATISFIES: "impl_url",
        VERIFIES: "test_url",
    }


def test_an_empty_table_field_attaches_that_marker_nowhere() -> None:
    config = _config(["@need-ids:", {"marker": SATISFIES, "field": ""}])
    assert need_id_refs_marker_fields(config, config.projects["p"]) == {
        "@need-ids:": "code_url"
    }


def test_a_table_field_survives_an_empty_ref_url_field() -> None:
    """``ref_url_field = ""`` turns the strings off, not the tables."""
    config = _config(TABLES, ref_url_field="")
    assert need_id_refs_marker_fields(config, config.projects["p"]) == {
        SATISFIES: "impl_url",
        VERIFIES: "test_url",
    }


def test_ref_url_field_is_not_registered_when_every_marker_is_a_table() -> None:
    config = _config(TABLES[1:])
    assert need_id_refs_field_names(config) == {"impl_url", "test_url"}


def test_every_field_of_every_project_is_registered() -> None:
    config = _config(
        TABLES,
        extra_projects={
            "q": {
                "remote_url_pattern": "https://example.com/{path}#L{line}",
                "ref_url_field": "other_url",
                "source_discover": {"src_dir": "./src"},
            }
        },
    )
    assert need_id_refs_fields(config) == {
        "p": {"@need-ids:": "code_url", SATISFIES: "impl_url", VERIFIES: "test_url"},
        "q": {"@need-ids:": "other_url"},
    }
    assert need_id_refs_field_names(config) == {
        "code_url",
        "impl_url",
        "test_url",
        "other_url",
    }


def test_a_project_whose_markers_all_attach_nowhere_is_not_gated() -> None:
    config = _config([{"marker": SATISFIES, "field": ""}])
    assert need_id_refs_fields(config) == {}


# validation


def _errors(config: CodeLinksConfig, link_types: tuple[str, ...] = ()) -> list[str]:
    return check_configuration(config, link_types)


def test_tables_and_strings_together_are_valid() -> None:
    assert _errors(_config(TABLES)) == []


@pytest.mark.parametrize(
    "markers",
    [
        pytest.param([SATISFIES, SATISFIES], id="string-twice"),
        pytest.param(
            [
                {"marker": SATISFIES, "field": "impl_url"},
                {"marker": SATISFIES, "field": "test_url"},
            ],
            id="table-twice",
        ),
        pytest.param(
            [SATISFIES, {"marker": SATISFIES, "field": "impl_url"}],
            id="string-and-table",
        ),
    ],
)
def test_a_marker_listed_twice_is_an_error(markers: list[object]) -> None:
    errors = _errors(_config(markers))
    assert f"Marker {SATISFIES} is defined multiple times" in errors


@pytest.mark.parametrize("field_name", ["remote-url", "local-url"])
def test_a_table_field_naming_a_url_field_is_an_error(field_name: str) -> None:
    config = _config([{"marker": SATISFIES, "field": field_name}])
    config.set_local_url = True
    assert _errors(config) == [
        "Project 'p' has the following errors:",
        f"need_id_refs marker {SATISFIES!r}: field {field_name!r} must differ from "
        "local_url_field and remote_url_field",
    ]


def test_a_table_field_naming_a_link_type_is_an_error() -> None:
    config = _config([{"marker": SATISFIES, "field": "satisfies"}])
    assert _errors(config, ("links", "satisfies")) == [
        "Project 'p' has the following errors:",
        f"need_id_refs marker {SATISFIES!r}: field 'satisfies' names a need link "
        "type, which cannot hold URLs",
    ]


def test_ref_url_field_naming_a_link_type_is_an_error() -> None:
    config = _config(["@need-ids:"], ref_url_field="links")
    assert _errors(config, ("links",)) == [
        "Project 'p' has the following errors:",
        "ref_url_field 'links' names a need link type, which cannot hold URLs",
    ]


def test_an_empty_field_names_no_link_type() -> None:
    config = _config([{"marker": SATISFIES, "field": ""}], ref_url_field="")
    assert _errors(config, ("",)) == []


def test_declared_link_types_reads_both_link_options() -> None:
    class _Conf:
        needs_links = {"satisfies": {}}
        needs_extra_links = [{"option": "verifies"}, "not-a-dict"]

    assert declared_link_types(_Conf()) == {  # ty: ignore[invalid-argument-type]
        "links",
        "parent_needs",
        "satisfies",
        "verifies",
    }


# through a Sphinx build


def _project(root: Path, toml: str, conf_extra: str = "") -> None:
    (root / "conf.py").write_text(
        "extensions = ['sphinx_needs', 'sphinx_codelinks']\n"
        "exclude_patterns = ['_build']\n" + conf_extra,
        encoding="utf-8",
    )
    (root / "index.rst").write_text("T\n=\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "ubproject.toml").write_text(toml, encoding="utf-8")


_TOML = (
    "[codelinks]\nset_remote_url = true\n\n"
    "[codelinks.projects.p]\n"
    'remote_url_pattern = "https://example.com/{path}#L{line}"\n'
    "[codelinks.projects.p.source_discover]\n"
    'src_dir = "./src"\n'
    "[codelinks.projects.p.analyse.need_id_refs]\n"
)


def test_toml_tables_register_their_fields(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    _project(
        tmp_path,
        _TOML + 'markers = ["@need-ids:", { marker = "\\\\satisfies", field = '
        '"impl_url" }]\n',
    )
    app = make_app(srcdir=tmp_path, freshenv=True)
    projects = app.config.src_trace_projects
    refs_config = projects["p"]["analyse_config"].need_id_refs_config
    assert refs_config.markers == ["@need-ids:", SATISFIES]
    assert refs_config.fields == {SATISFIES: "impl_url"}
    assert {"code_url", "impl_url"} <= set(app.config.needs_string_links)


def test_the_build_checks_the_fields_against_its_link_types(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """``check_sphinx_configuration`` reads the build's declared link types. Called
    again on a built app, not by a build that fails in ``config-inited``: such a build
    leaves Sphinx's logging bound to an app with no environment, which breaks every
    later test of the worker that logs."""
    _project(
        tmp_path,
        _TOML + 'markers = [{ marker = "\\\\satisfies", field = "satisfies" }]\n',
    )
    app = make_app(srcdir=tmp_path, freshenv=True)
    check_sphinx_configuration(app, app.config)  # no link type of that name: valid

    app.config.needs_links = {"satisfies": {}}
    with pytest.raises(Exception, match="names a need link type") as excinfo:
        check_sphinx_configuration(app, app.config)
    assert f"need_id_refs marker {SATISFIES!r}: field 'satisfies'" in str(
        excinfo.value
    )
