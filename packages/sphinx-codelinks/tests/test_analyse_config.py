# @Test suite for source analysis configuration validation, TEST_CONF_1, test, [IMPL_OLP_1, IMPL_MLN_1]
from pathlib import Path

import pytest

from sphinx_codelinks.config import (
    MultilineNeedsConfig,
    NeedIdRefsConfig,
    OneLineCommentStyle,
    SourceAnalyseConfig,
    convert_analyse_config,
    generate_project_configs,
)
from sphinx_needs_testkit import build_warnings

from .conftest import TEST_DIR
from .test_need_id_refs import _SHOWS_WARNING_TYPES, _build, _MakeApp, _project


@pytest.mark.parametrize(
    ("analyse_config", "result"),
    [
        (
            SourceAnalyseConfig(
                src_files=[
                    TEST_DIR / "data" / "dcdc" / "charge" / "demo_1.cpp",
                ],
                src_dir=TEST_DIR / "data" / "dcdc",
                comment_type=123,
            ),
            [
                "Schema validation error in field 'comment_type': 123 is not of type 'string'",
            ],
        ),
        (
            SourceAnalyseConfig(
                src_files=None,
                src_dir=TEST_DIR / "data" / "dcdc",
                comment_type=123,
            ),
            [
                "Schema validation error in field 'comment_type': 123 is not of type 'string'",
                "Schema validation error in field 'src_files': None is not of type 'array'",
            ],
        ),
    ],
)
def test_config_schema_validator_negative(analyse_config, result):
    errors = analyse_config.check_schema()
    assert sorted(errors) == sorted(result)


@pytest.mark.parametrize(
    "oneline_config, result",
    [
        (
            OneLineCommentStyle(
                start_sequence="[[",
                end_sequence="]]",
                field_split_char=",",
                needs_fields=[
                    {"name": "title"},
                    {"name": "id"},
                    {"name": "type", "default": "impl"},
                    {"name": "links", "type": "list[]", "default": []},  # wrong type
                ],
            ),
            [
                "Schema validation error in need_fields 'links': 'list[]' is not one of ['str', 'list[str]']"
            ],
        ),
        (
            OneLineCommentStyle(
                start_sequence="[[",
                end_sequence="]]",
                field_split_char=",",
                needs_fields=[
                    {"name": "title"},
                    {"name": "id"},
                    {"name": "type", "default": 123},  # int is invalid
                    {"name": "links", "type": "list[str]", "default": []},
                ],
            ),
            [
                "Schema validation error in need_fields 'type': 123 is not of type 'string'"
            ],
        ),
        (
            OneLineCommentStyle(
                start_sequence="[[",
                end_sequence="]]",
                field_split_char=",",
                needs_fields=[
                    {"name": "title", "qwe": "qwe"},  # invalid qwe filed
                    {"name": "id"},
                    {"name": "type", "default": "impl"},
                    {"name": "links", "type": "list[str]", "default": []},
                ],
            ),
            [
                "Schema validation error in need_fields 'title': Additional properties are not allowed ('qwe' was unexpected)"
            ],
        ),
        (
            OneLineCommentStyle(
                start_sequence="[[",
                end_sequence="]]",
                field_split_char=",",
                needs_fields=[
                    {"name": "title"},
                    {"name": "id"},
                    {
                        "name": "type",
                        "type: ": "list[str]",
                        "default": "impl",
                    },  # wring combination of type and default
                    {"name": "links", "type": "list[str]", "default": []},
                ],
            ),
            [
                "Schema validation error in need_fields 'type': Additional properties are not allowed ('type: ' was unexpected)"
            ],
        ),
        (
            OneLineCommentStyle(
                start_sequence="[[",
                end_sequence="]]",
                field_split_char=",",
                needs_fields=[
                    {"name": "id"}  # "title" and "type" are not given
                ],
            ),
            ["Missing required fields: ['title', 'type']"],
        ),
        (
            OneLineCommentStyle(
                start_sequence="[[",
                end_sequence="]]",
                field_split_char=",",
                needs_fields=[
                    {"name": "id"},
                    {"name": "id"},  # duplicate
                ],
            ),
            [
                "Missing required fields: ['title', 'type']",
                "Field 'id' is defined multiple times.",
            ],
        ),
        (
            OneLineCommentStyle(
                start_sequence=1234,  # wrong type
                end_sequence=5678,
                field_split_char=2222,
                needs_fields=[
                    {"name": "id"},
                ],
            ),
            [
                "Schema validation error in field 'field_split_char': 2222 is not of type 'string'",
                "Schema validation error in field 'end_sequence': 5678 is not of type 'string'",
                "Schema validation error in field 'start_sequence': 1234 is not of type 'string'",
                "Missing required fields: ['title', 'type']",
            ],
        ),
        (
            OneLineCommentStyle(
                start_sequence="@need",
                end_sequence="\n",
                field_split_char=",",
                needs_fields=[
                    {"name": "id"},
                    {"name": "implements", "type": "list[str]", "default": []},
                    {"name": "type", "default": "impl"},
                    {"name": "title"},  # required after optional
                ],
            ),
            [
                "Field 'title' without a default follows field 'implements' which has a default. "
                "Fields without defaults must be defined before fields with defaults.",
            ],
        ),
    ],
)
def test_oneline_schema_validator_negative(oneline_config, result):
    errors = oneline_config.check_fields_configuration()
    assert sorted(errors) == sorted(result)


@pytest.mark.parametrize(
    "oneline_config",
    [
        OneLineCommentStyle(
            start_sequence="[[",
            end_sequence="]]",
            field_split_char=",",
            needs_fields=[
                {"name": "title"},
                {"name": "id"},
                {"name": "type", "default": "impl"},
                {"name": "links", "type": "list[str]", "default": []},
            ],
        ),
        OneLineCommentStyle(
            start_sequence="[[",
            end_sequence="]]",
            field_split_char=",",
            needs_fields=[
                {"name": "title"},  # minimum need_fields config
                {"name": "type"},
            ],
        ),
        OneLineCommentStyle(
            needs_fields=[  # minimum config
                {"name": "title"},
                {"name": "type"},
            ],
        ),
    ],
)
def test_oneline_schema_validator_positive(oneline_config):
    assert len(oneline_config.check_fields_configuration()) == 0


def test_multiline_needs_config_defaults_are_valid() -> None:
    config = MultilineNeedsConfig()

    assert (config.start_sequence, config.end_sequence) == ("@need", "@endneed")
    assert config.default_markup == "rst"
    assert config.markups == {"rst": ".rst", "md": ".md"}
    assert config.check_fields_configuration() == []


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        pytest.param(
            {"default_markup": "myst"},
            "default_markup 'myst' is not a key of markups ('md', 'rst').",
            id="default_markup_not_in_markups",
        ),
        pytest.param(
            {"start_sequence": "@block", "end_sequence": "@block"},
            "start_sequence and end_sequence cannot be the same.",
            id="same_sequences",
        ),
        pytest.param(
            {"start_sequence": ""},
            "Schema validation error in field 'start_sequence': ",
            id="empty_start",
        ),
        pytest.param(
            {"markups": {"rst": ".rst", "empty": ""}},
            "Schema validation error in field 'markups': '' should be non-empty",
            id="markup_suffix_empty",
        ),
        pytest.param(
            {"markups": {"rst": 1}},
            "Schema validation error in field 'markups': 1 is not of type 'string'",
            id="markup_suffix_not_a_string",
        ),
    ],
)
def test_multiline_needs_config_negative(kwargs: dict, error: str) -> None:
    errors = MultilineNeedsConfig(**kwargs).check_fields_configuration()

    assert any(message.startswith(error) for message in errors), errors


def test_multiline_needs_config_errors_reach_the_analyse_config() -> None:
    """Checked when the feature is on, under their own heading."""
    config = SourceAnalyseConfig(
        get_multiline_needs=True,
        multiline_needs_config=MultilineNeedsConfig(default_markup="txt"),
    )

    errors = config.check_fields_configuration()

    assert "MultilineNeeds configuration errors:" in errors
    assert "default_markup 'txt' is not a key of markups ('md', 'rst')." in errors
    assert (
        SourceAnalyseConfig(
            multiline_needs_config=MultilineNeedsConfig(default_markup="txt")
        ).check_fields_configuration()
        == []
    ), "not checked while the feature is off"


def test_multiline_markers_are_checked_only_when_the_feature_is_on() -> None:
    """A reference marker ``@need`` (valid before multi-line needs existed) is a clash
    only for a project that switches multi-line needs on."""
    refs = NeedIdRefsConfig(markers=["@need"])

    assert (
        SourceAnalyseConfig(need_id_refs_config=refs).check_markers_mutually_exclusive()
        == []
    )
    assert SourceAnalyseConfig(
        get_multiline_needs=True, need_id_refs_config=refs
    ).check_markers_mutually_exclusive() == ["Marker @need is defined multiple times"]


def test_multiline_markers_join_the_mutual_exclusion_check() -> None:
    """Equality only: the default one-line start ``@`` is a prefix of ``@need`` and that
    is not a clash; a multi-line marker equal to another marker is."""
    assert SourceAnalyseConfig().check_markers_mutually_exclusive() == []
    clash = SourceAnalyseConfig(
        get_multiline_needs=True,
        multiline_needs_config=MultilineNeedsConfig(start_sequence="@need-ids:"),
    )
    assert clash.check_markers_mutually_exclusive() == [
        "Marker @need-ids: is defined multiple times"
    ]


def test_convert_analyse_config_reads_the_multiline_needs_table() -> None:
    config = convert_analyse_config(
        {
            "get_multiline_needs": True,
            "multiline_needs": {
                "start_sequence": "@spec",
                "end_sequence": "@endspec",
                "default_markup": "myst",
                "markups": {"myst": ".md"},
            },
        }
    )

    assert config.get_multiline_needs is True
    assert config.multiline_needs_config == MultilineNeedsConfig(
        start_sequence="@spec",
        end_sequence="@endspec",
        default_markup="myst",
        markups={"myst": ".md"},
    )


def test_multiline_needs_are_not_forced_on() -> None:
    """Unlike ``get_oneline_needs`` (#1889), nothing switches the extraction on."""
    projects: dict = {"p": {"source_discover": {"src_dir": "."}, "analyse": {}}}

    generate_project_configs(projects)

    assert projects["p"]["analyse_config"].get_multiline_needs is False


def test_convert_multiline_needs_config_rejects_an_unknown_key() -> None:
    with pytest.raises(TypeError, match="Invalid multiline_needs configuration"):
        convert_analyse_config({"multiline_needs": {"open": "@need"}})


@pytest.mark.parametrize(
    ("section", "named"),
    [
        ({"get_rst": True}, "'get_rst' is no longer supported"),
        ({"marked_rst": {}}, "'[analyse.marked_rst]' is no longer supported"),
    ],
)
def test_convert_analyse_config_names_the_replacement_of_a_removed_key(
    section: dict, named: str
) -> None:
    """A TypeError, as every other bad key of the section raises, but naming the cure."""
    with pytest.raises(TypeError) as excinfo:
        convert_analyse_config(section)

    assert named in str(excinfo.value)
    assert "multi-line needs" in str(excinfo.value)


GET_RST_IGNORED = (
    "analyse: 'get_rst' is no longer read: the marked-rst blocks were replaced by "
    "multi-line needs (the @need and @endneed markers); get_rst = false asks for "
    "nothing and can be removed"
)


def test_convert_analyse_config_tolerates_get_rst_false_silently(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``get_rst = false`` asks for nothing the removed blocks did, and configuration
    scaffolds wrote it into shared ``ubproject.toml`` files: the converter, called on
    every configuration read, drops it without a word; the build and the CLI warn once
    per project (``test_get_rst_false_warns_once_per_project_per_build``)."""
    with caplog.at_level("WARNING"):
        config = convert_analyse_config({"get_rst": False})

    assert caplog.records == []
    assert config.get_multiline_needs is False


def test_get_rst_false_warns_once_per_project_per_build(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """The scaffold's shape -- two projects with ``get_rst = false``, a directive each:
    one warning per project, at configuration time, on a fresh build and on an
    incremental one alike."""
    _project(
        tmp_path,
        files={
            "src/refs.cpp": "// no markers\n",
            "tests/t.cpp": "// no markers\n",
            "docs/page_t.rst": "T\n=\n\n.. src-trace::\n   :project: tests\n",
        },
        toml_extra="""
[codelinks.projects.src.analyse]
get_rst = false

[codelinks.projects.tests]
remote_url_pattern = "https://github.com/example/demo/blob/{commit}/{path}#L{line}"

[codelinks.projects.tests.source_discover]
src_dir = "../tests"
comment_type = "cpp"

[codelinks.projects.tests.analyse]
get_rst = false
""",
    )
    suffix = " [codelinks.config]" if _SHOWS_WARNING_TYPES else ""
    # one per project, each naming it: the two lines differ by the name alone
    expected = [
        f"WARNING: Project {name!r}: {GET_RST_IGNORED}{suffix}"
        for name in ("src", "tests")
    ]

    fresh = _build(tmp_path, make_app)
    assert [w for w in build_warnings(fresh) if "get_rst" in w] == expected

    (tmp_path / "docs" / "page_t.rst").write_text(
        "T\n=\n\nEdited.\n\n.. src-trace::\n   :project: tests\n", encoding="utf-8"
    )
    incremental = _build(tmp_path, make_app, freshenv=False)
    assert [w for w in build_warnings(incremental) if "get_rst" in w] == expected


@pytest.mark.parametrize(
    "section",
    [{"get_rst": True}, {"get_rst": False, "marked_rst": {}}, {"get_rst": 0}],
    ids=["get_rst_true", "get_rst_false_and_marked_rst", "get_rst_zero"],
)
def test_convert_analyse_config_still_refuses_get_rst_true_or_marked_rst(
    section: dict,
) -> None:
    """Only ``get_rst = false`` with nothing else removed is tolerated."""
    with pytest.raises(TypeError, match="no longer supported"):
        convert_analyse_config(section)


def test_an_unknown_analyse_key_still_fails_in_the_constructor() -> None:
    """The unknown-key policy for every other key is unchanged."""
    with pytest.raises(TypeError, match="unexpected keyword argument 'foo'"):
        convert_analyse_config({"foo": 1})
