"""The ``[variants]`` reader and its ``[needs]`` fallback: :func:`ubproject.read_variants`.

The conformance corpus covers the same ground as data, for two readers at once; these tests
pin what the corpus does not compare -- ``location``, severities, message content, the
Python-side types -- and name each precedence state so that a regression reads as one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ubproject import (
    VARIANT_DATA_LEGACY_LOCATION,
    VARIANT_DATA_LOCATION,
    VARIANTS_UNKNOWN_KEY,
    Diagnostic,
    UbprojectError,
    load_toml,
    read_variants,
)


def _read(
    tmp_path: Path,
    toml: str,
    files: dict[str, object] | None = None,
    needs_table: str = "needs",
):
    for name, payload in (files or {}).items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    toml_path = tmp_path / "ubproject.toml"
    toml_path.write_text(toml, encoding="utf-8")
    return read_variants(load_toml(toml_path), toml_path, needs_table=needs_table)


def _codes(diagnostics: tuple[Diagnostic, ...]) -> list[tuple[str, str]]:
    return [(d.code, d.path) for d in diagnostics]


class TestPrecedence:
    """Whole-location: both keys come from one table, never one from each."""

    def test_neither_location(self, tmp_path: Path) -> None:
        result = _read(tmp_path, '[project]\nname = "demo"\n')
        assert result.data == {}
        assert result.data_file is None
        assert result.location is None
        assert result.diagnostics == ()

    def test_only_variants(self, tmp_path: Path) -> None:
        result = _read(
            tmp_path,
            '[variants]\ndata_file = "vd.json"\n[variants.data]\nedition = "pro"\n',
            {"vd.json": {"edition": "base", "cpu": "arm"}},
        )
        assert result.data == {"edition": "pro", "cpu": "arm"}
        assert result.data_file == tmp_path / "vd.json"
        assert result.location == "variants"
        assert result.diagnostics == ()

    def test_only_needs(self, tmp_path: Path) -> None:
        result = _read(
            tmp_path,
            '[needs]\nvariant_data_file = "vd.json"\n[needs.variant_data]\nedition = "pro"\n',
            {"vd.json": {"edition": "base", "cpu": "arm"}},
        )
        assert result.data == {"edition": "pro", "cpu": "arm"}
        assert result.data_file == tmp_path / "vd.json"
        assert result.location == "needs"

    def test_both_set_variants_wins_whole(self, tmp_path: Path) -> None:
        """The [needs] file is NOT merged under the [variants] inline table."""
        result = _read(
            tmp_path,
            '[variants.data]\nedition = "pro"\n'
            '[needs]\nvariant_data_file = "legacy.json"\n'
            '[needs.variant_data]\ncpu = "x86"\n',
            {"legacy.json": {"cpu": "arm", "extra": True}},
        )
        assert result.data == {"edition": "pro"}
        assert result.data_file is None
        assert result.location == "variants"

    def test_an_empty_variants_table_declares_nothing(self, tmp_path: Path) -> None:
        result = _read(tmp_path, '[variants]\n[needs.variant_data]\nedition = "pro"\n')
        assert result.location == "needs"
        assert result.data == {"edition": "pro"}

    def test_an_empty_inline_table_is_a_declaration(self, tmp_path: Path) -> None:
        result = _read(
            tmp_path, '[variants]\ndata = {}\n[needs.variant_data]\nedition = "pro"\n'
        )
        assert result.location == "variants"
        assert result.data == {}


class TestDiagnostics:
    def test_both_set_names_every_ignored_key(self, tmp_path: Path) -> None:
        result = _read(
            tmp_path,
            '[variants.data]\nedition = "pro"\n'
            '[needs]\nvariant_data_file = "legacy.json"\n'
            '[needs.variant_data]\ncpu = "x86"\n',
        )
        assert _codes(result.diagnostics) == [
            (VARIANT_DATA_LOCATION, "needs.variant_data"),
            (VARIANT_DATA_LOCATION, "needs.variant_data_file"),
        ]
        for diagnostic in result.diagnostics:
            assert diagnostic.severity == "warning"
            assert str(tmp_path / "ubproject.toml") in diagnostic.message
            assert "[variants]" in diagnostic.message
        assert "variant_data_file" in result.diagnostics[1].message

    def test_both_set_with_one_legacy_key(self, tmp_path: Path) -> None:
        result = _read(
            tmp_path,
            '[variants.data]\nedition = "pro"\n[needs.variant_data]\nedition = "base"\n',
        )
        assert _codes(result.diagnostics) == [
            (VARIANT_DATA_LOCATION, "needs.variant_data")
        ]

    def test_the_legacy_location_is_informational(self, tmp_path: Path) -> None:
        """The package takes no side: a consumer decides whether this is worth a warning."""
        result = _read(
            tmp_path,
            '[needs]\nvariant_data_file = "vd.json"\n[needs.variant_data]\nx = 1\n',
            {"vd.json": {}},
        )
        assert _codes(result.diagnostics) == [
            (VARIANT_DATA_LEGACY_LOCATION, "needs.variant_data"),
            (VARIANT_DATA_LEGACY_LOCATION, "needs.variant_data_file"),
        ]
        assert {d.severity for d in result.diagnostics} == {"info"}
        assert "[variants] data_file" in result.diagnostics[1].message

    def test_an_unknown_key_in_variants_is_reported_not_raised(
        self, tmp_path: Path
    ) -> None:
        result = _read(
            tmp_path,
            '[variants]\nsources = ["a"]\nzeta = 1\n[variants.data]\nedition = "pro"\n',
        )
        assert result.data == {"edition": "pro"}
        assert _codes(result.diagnostics) == [
            (VARIANTS_UNKNOWN_KEY, "variants.sources"),
            (VARIANTS_UNKNOWN_KEY, "variants.zeta"),
        ]
        assert {d.severity for d in result.diagnostics} == {"warning"}
        assert "'sources'" in result.diagnostics[0].message

    def test_unknown_keys_do_not_declare_variants(self, tmp_path: Path) -> None:
        result = _read(
            tmp_path, '[variants]\nfuture = 1\n[needs.variant_data]\nedition = "pro"\n'
        )
        assert result.location == "needs"
        assert _codes(result.diagnostics) == [
            (VARIANTS_UNKNOWN_KEY, "variants.future"),
            (VARIANT_DATA_LEGACY_LOCATION, "needs.variant_data"),
        ]

    def test_the_diagnostic_is_a_value(self) -> None:
        one = Diagnostic("c", "p", "m", "info")
        assert one == Diagnostic("c", "p", "m", "info")
        with pytest.raises(AttributeError):
            one.code = "other"  # type: ignore[misc]


class TestPrefix:
    def test_the_legacy_keys_under_a_dotted_prefix(self, tmp_path: Path) -> None:
        result = _read(
            tmp_path,
            "[tool.acme.needs.variant_data]\nedition = 'pro'\n",
            needs_table="tool.acme.needs",
        )
        assert result.location == "needs"
        assert result.data == {"edition": "pro"}
        assert _codes(result.diagnostics) == [
            (VARIANT_DATA_LEGACY_LOCATION, "tool.acme.needs.variant_data")
        ]

    def test_a_sequence_prefix(self, tmp_path: Path) -> None:
        toml_path = tmp_path / "ubproject.toml"
        data = {"tool": {"acme.docs": {"needs": {"variant_data": {"x": 1}}}}}
        result = read_variants(
            data, toml_path, needs_table=("tool", "acme.docs", "needs")
        )
        assert result.data == {"x": 1}
        assert _codes(result.diagnostics) == [
            (VARIANT_DATA_LEGACY_LOCATION, "tool.acme.docs.needs.variant_data")
        ]


class TestAnchoring:
    def test_a_relative_data_file_is_anchored_at_the_toml_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "vd.json").write_text('{"cpu": "arm"}', encoding="utf-8")
        toml_path = docs / "ubproject.toml"
        toml_path.write_text('[variants]\ndata_file = "vd.json"\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)  # the working directory must not matter
        result = read_variants(load_toml(toml_path), toml_path)
        assert result.data_file == docs / "vd.json"
        assert result.data == {"cpu": "arm"}

    def test_a_symlinked_toml_directory_is_not_resolved(self, tmp_path: Path) -> None:
        real = tmp_path / "real"
        real.mkdir()
        (real / "vd.json").write_text('{"cpu": "arm"}', encoding="utf-8")
        link = tmp_path / "link"
        try:
            link.symlink_to(real, target_is_directory=True)
        except OSError:  # pragma: no cover - Windows without the symlink privilege
            pytest.skip("creating a symlink needs a privilege this account lacks")
        toml_path = link / "ubproject.toml"
        toml_path.write_text('[variants]\ndata_file = "vd.json"\n', encoding="utf-8")
        result = read_variants(load_toml(toml_path), toml_path)
        assert result.data_file == link / "vd.json"
        assert result.data == {"cpu": "arm"}


class TestRefusals:
    @pytest.mark.parametrize(
        ("toml", "match"),
        [
            ('variants = ["pro"]\n', r"\[variants\] must be a table, got list"),
            ('[variants]\ndata = "x"\n', r"\[variants\] data must be a table, got str"),
            (
                '[variants]\ndata_file = ["a.json"]\n',
                r"\[variants\] data_file must be one non-empty path string, got list",
            ),
            (
                '[variants]\ndata_file = ""\n',
                r"\[variants\] data_file must be one non-empty path string, got ''",
            ),
            (
                '[needs]\nvariant_data = "x"\n',
                r"\[needs\] variant_data must be a table, got str",
            ),
            (
                "[needs]\nvariant_data_file = 3\n",
                r"\[needs\] variant_data_file must be one non-empty path string, got int",
            ),
            ('needs = "x"\n', r"\[needs\] must be a table, got str"),
            (
                "[variants.data]\nmixed = [1, 'a']\n",
                r"\[variants\]: var\.mixed\[1\]: an array must hold one type",
            ),
            (
                '[variants]\ndata_file = "absent.json"\n',
                r"\[variants\]: variant data file not found",
            ),
            (
                '[needs]\nvariant_data_file = "absent.json"\n',
                r"\[needs\]: variant data file not found",
            ),
        ],
        ids=[
            "variants-not-a-table",
            "data-not-a-table",
            "data-file-a-list",
            "data-file-empty",
            "legacy-data-not-a-table",
            "legacy-data-file-not-a-string",
            "needs-not-a-table",
            "invalid-inline-data",
            "missing-data-file",
            "missing-legacy-data-file",
        ],
    )
    def test_refusals_name_the_file_and_the_rule(
        self, tmp_path: Path, toml: str, match: str
    ) -> None:
        with pytest.raises(UbprojectError, match=match) as info:
            _read(tmp_path, toml)
        assert str(tmp_path / "ubproject.toml") in str(info.value)
