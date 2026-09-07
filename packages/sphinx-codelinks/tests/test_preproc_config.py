from pathlib import Path

import pytest

from sphinx_codelinks.config import (
    PreprocessorConfig,
    SourceAnalyseConfig,
    convert_analyse_config,
)


def test_source_analyse_config_default_preprocessor_is_none():
    cfg = SourceAnalyseConfig()
    assert cfg.preprocessor is None


def test_convert_analyse_config_builds_preprocessor():
    cfg = convert_analyse_config(
        {
            "get_oneline_needs": True,
            "preprocessor": {
                "compile_commands": "build/compile_commands.json",
                "defines": ["VARIANT_A", "PLATFORM_LINUX=1"],
                "includes": ["include"],
                "std": "c++20",
            },
        }
    )
    assert isinstance(cfg.preprocessor, PreprocessorConfig)
    assert cfg.preprocessor.compile_commands == Path("build/compile_commands.json")
    assert cfg.preprocessor.defines == ["VARIANT_A", "PLATFORM_LINUX=1"]
    assert cfg.preprocessor.includes == [Path("include")]
    assert cfg.preprocessor.std == "c++20"


def test_convert_analyse_config_preprocessor_std_defaults_to_cpp17():
    cfg = convert_analyse_config(
        {"get_oneline_needs": True, "preprocessor": {"defines": []}}
    )
    assert cfg.preprocessor is not None
    assert cfg.preprocessor.std == "c++17"


def test_convert_analyse_config_no_preprocessor_block():
    cfg = convert_analyse_config({"get_oneline_needs": True})
    assert cfg.preprocessor is None


def test_preprocessor_bare_string_defines_is_rejected():
    """A mistyped scalar must error, not silently coerce to per-character flags.

    Without validation, ``defines = "cpp17"`` becomes ``list("cpp17")`` →
    ``["c", "p", "p", "1", "7"]`` → five bogus ``-D`` flags.
    """
    with pytest.raises(TypeError, match="defines must be a list of strings"):
        convert_analyse_config(
            {"get_oneline_needs": True, "preprocessor": {"defines": "cpp17"}}
        )


def test_preprocessor_non_string_list_entries_are_rejected():
    with pytest.raises(TypeError, match="defines must be a list of strings"):
        convert_analyse_config(
            {"get_oneline_needs": True, "preprocessor": {"defines": ["OK", 1]}}
        )


def test_preprocessor_bare_string_includes_is_rejected():
    with pytest.raises(TypeError, match="includes must be a list of strings"):
        convert_analyse_config(
            {"get_oneline_needs": True, "preprocessor": {"includes": "include"}}
        )


def test_preprocessor_non_string_std_is_rejected():
    with pytest.raises(TypeError, match="std must be a string"):
        convert_analyse_config({"get_oneline_needs": True, "preprocessor": {"std": 17}})


def test_preprocessor_config_passes_analyse_schema_validation():
    """A SourceAnalyseConfig carrying a preprocessor must validate cleanly.

    Regression: the ``preprocessor`` field previously carried a flat
    ``{"type": ["object", "null"]}`` json-schema, so ``check_schema`` validated
    the *constructed* ``PreprocessorConfig`` instance against JSON type
    ``object`` and raised at sphinx ``config-inited``::

        Schema validation error in field 'preprocessor':
        PreprocessorConfig(...) is not of type 'object', 'null'

    Nested dataclass config fields must not carry a flat schema (their siblings
    ``need_id_refs_config`` / ``oneline_comment_style`` do not).
    """
    cfg = convert_analyse_config(
        {
            "get_oneline_needs": True,
            "preprocessor": {"defines": ["FEATURE_A"]},
        }
    )
    assert cfg.preprocessor is not None
    schema_errors = cfg.check_schema()
    assert not any("preprocessor" in err for err in schema_errors), schema_errors


def test_anchor_preproc_paths_resolves_relative_against_base(tmp_path):
    """Relative compile_commands / include dirs resolve against the config dir
    (the ``base``), not the process CWD; absolute paths are left unchanged."""
    from pathlib import Path

    from sphinx_codelinks.config import PreprocessorConfig, anchor_preproc_paths

    base = tmp_path / "cfgdir"
    abs_inc = tmp_path / "abs_keep"
    preproc = PreprocessorConfig(
        compile_commands=Path("build/compile_commands.json"),
        includes=[Path("include"), abs_inc],
        defines=["X=1"],
    )
    out = anchor_preproc_paths(preproc, base)
    assert out.compile_commands == (base / "build/compile_commands.json").resolve()
    assert out.includes[0] == (base / "include").resolve()
    assert out.includes[1] == abs_inc.resolve()  # already absolute -> unchanged
    assert out.defines == ["X=1"]  # non-path fields untouched
