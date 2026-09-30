"""Find, load, select and anchor: :mod:`ubproject.project`."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from ubproject import (
    DEFAULT_FILENAME,
    UbprojectError,
    anchor,
    find_project_config,
    load_toml,
    select_table,
    table_path,
)


def _write(directory: Path, text: str = "", name: str = DEFAULT_FILENAME) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


class TestFindProjectConfig:
    """The upward search, bounded by the repository root or, outside one, the distribution root.

    Moved from sphinx-test-reports' ``projectconfig.py`` as is; these cases are that
    module's, re-pointed at this package.
    """

    def test_finds_the_file_in_the_starting_directory(self, tmp_path: Path) -> None:
        config = _write(tmp_path)
        assert find_project_config(tmp_path) == config

    def test_walks_up_to_the_repository_root(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        config = _write(tmp_path)
        deep = tmp_path / "docs" / "source"
        deep.mkdir(parents=True)
        assert find_project_config(deep) == config

    def test_a_pyproject_toml_beside_conf_py_does_not_end_the_search(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        config = _write(tmp_path)
        docs = tmp_path / "docs"
        _write(docs, name="pyproject.toml")
        assert find_project_config(docs) == config

    def test_walks_past_a_workspace_member_pyproject_toml(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        config = _write(tmp_path)
        member = tmp_path / "packages" / "dist"
        docs = member / "docs"
        docs.mkdir(parents=True)
        _write(member, name="pyproject.toml")
        assert find_project_config(docs) == config

    def test_stops_at_a_nested_repository_without_the_file(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path)
        inner = tmp_path / "vendor" / "inner"
        docs = inner / "docs"
        docs.mkdir(parents=True)
        _write(inner, "gitdir: elsewhere\n", name=".git")
        assert find_project_config(docs) is None

    def test_stops_at_the_distribution_root_without_a_repository(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path)  # a stranger's, two levels up
        dist = tmp_path / "downloads" / "demo-1.0.0"
        docs = dist / "docs"
        docs.mkdir(parents=True)
        _write(dist, name="pyproject.toml")
        assert find_project_config(docs) is None

    def test_the_file_at_the_distribution_root_is_still_found(
        self, tmp_path: Path
    ) -> None:
        dist = tmp_path / "demo-1.0.0"
        docs = dist / "docs"
        docs.mkdir(parents=True)
        _write(dist, name="pyproject.toml")
        config = _write(dist)
        assert find_project_config(docs) == config

    def test_the_file_wins_over_the_marker_in_one_directory(
        self, tmp_path: Path
    ) -> None:
        config = _write(tmp_path)
        (tmp_path / ".git").mkdir()
        assert find_project_config(tmp_path) == config

    def test_missing_file_is_none(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        assert find_project_config(tmp_path) is None

    def test_a_fruitless_search_reports_where_it_ended(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        reported: list[str] = []
        assert find_project_config(docs, report=reported.append) is None
        assert len(reported) == 1
        assert str(docs) in reported[0]
        assert f"repository root {tmp_path}" in reported[0]
        assert ".git" in reported[0]

    def test_a_fruitless_search_reports_the_distribution_root(
        self, tmp_path: Path
    ) -> None:
        dist = tmp_path / "demo-1.0.0"
        docs = dist / "docs"
        docs.mkdir(parents=True)
        _write(dist, name="pyproject.toml")
        reported: list[str] = []
        assert find_project_config(docs, report=reported.append) is None
        assert len(reported) == 1
        assert f"distribution root {dist}" in reported[0]
        assert "pyproject.toml" in reported[0]

    def test_a_successful_search_reports_nothing(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        _write(tmp_path)
        reported: list[str] = []
        find_project_config(tmp_path / "docs", report=reported.append)
        assert reported == []

    def test_an_explicit_filename_is_searched_for(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        _write(tmp_path)  # the default name must not satisfy the search
        config = _write(tmp_path, name="other.toml")
        docs = tmp_path / "docs"
        docs.mkdir()
        assert find_project_config(docs, filename="other.toml") == config

    def test_an_explicit_filename_that_is_absent_is_reported(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        _write(tmp_path)
        reported: list[str] = []
        assert (
            find_project_config(tmp_path, filename="other.toml", report=reported.append)
            is None
        )
        assert reported
        assert "other.toml" in reported[0]

    def test_a_directory_named_like_the_file_is_not_the_file(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / "docs" / DEFAULT_FILENAME).mkdir(parents=True)
        config = _write(tmp_path)
        assert find_project_config(tmp_path / "docs") == config

    def test_a_relative_start_is_searched_from_the_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        config = _write(tmp_path)
        docs = tmp_path / "docs"
        docs.mkdir()
        monkeypatch.chdir(docs)
        assert find_project_config(Path()) == config


class TestLoadToml:
    def test_reads_a_document(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "[needs]\nid_required = true\n[variants.data]\nx = 1\n")
        assert load_toml(path) == {
            "needs": {"id_required": True},
            "variants": {"data": {"x": 1}},
        }

    def test_invalid_toml_names_the_file(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "[variants\n")
        with pytest.raises(UbprojectError, match="invalid TOML") as info:
            load_toml(path)
        assert str(path) in str(info.value)

    def test_a_missing_file_names_the_file(self, tmp_path: Path) -> None:
        path = tmp_path / DEFAULT_FILENAME
        with pytest.raises(UbprojectError, match="cannot be read") as info:
            load_toml(path)
        assert str(path) in str(info.value)

    def test_a_directory_is_not_readable_as_the_file(self, tmp_path: Path) -> None:
        path = tmp_path / DEFAULT_FILENAME
        path.mkdir()
        with pytest.raises(UbprojectError, match="cannot be read"):
            load_toml(path)

    @pytest.mark.skipif(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        reason="root reads unreadable files",
    )
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="os.chmod on Windows only sets the read-only attribute; the file stays readable",
    )
    def test_an_unreadable_file_names_the_file(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "[variants]\n")
        path.chmod(0o000)
        try:
            with pytest.raises(UbprojectError, match="cannot be read") as info:
                load_toml(path)
        finally:
            path.chmod(0o644)
        assert str(path) in str(info.value)


class TestSelectTable:
    DATA: dict[str, object] = {
        "needs": {"id_required": True},
        "tool": {"acme": {"needs": {"variant_data": {"x": 1}}}, "flat": "text"},
    }

    def test_a_present_table(self) -> None:
        assert select_table(self.DATA, "needs") == {"id_required": True}

    def test_a_dotted_path(self) -> None:
        assert select_table(self.DATA, "tool.acme.needs") == {"variant_data": {"x": 1}}

    def test_a_sequence_path_can_hold_a_dotted_key(self) -> None:
        data = {"tool": {"acme.docs": {"needs": {"a": 1}}}}
        assert select_table(data, ("tool", "acme.docs", "needs")) == {"a": 1}
        assert select_table(data, "tool.acme.docs.needs") is None

    @pytest.mark.parametrize(
        "path", ["absent", "tool.absent", "tool.acme.absent.deeper"]
    )
    def test_an_absent_table_is_none(self, path: str) -> None:
        assert select_table(self.DATA, path) is None

    def test_a_segment_that_is_not_a_table_is_an_error(self, tmp_path: Path) -> None:
        source = tmp_path / DEFAULT_FILENAME
        with pytest.raises(UbprojectError) as info:
            select_table(self.DATA, "tool.flat.needs", source=source)
        message = str(info.value)
        assert "[tool.flat] must be a table, got str" in message
        assert str(source) in message

    def test_the_last_segment_not_a_table_is_an_error(self) -> None:
        with pytest.raises(
            UbprojectError, match=r"\[needs\.id_required\] must be a table"
        ):
            select_table(self.DATA, "needs.id_required")

    def test_the_result_is_a_copy(self) -> None:
        selected = select_table(self.DATA, "needs")
        assert selected is not None
        selected["added"] = 1
        assert self.DATA["needs"] == {"id_required": True}

    @pytest.mark.parametrize("path", ["", "a..b", ".a", "a.", ()])
    def test_a_malformed_path_is_the_callers_mistake(
        self, path: str | tuple[str, ...]
    ) -> None:
        with pytest.raises(ValueError, match="invalid table path"):
            table_path(path)


class TestAnchor:
    """Joined, never resolved: the consumer decides what happens to symlinks and ``..``."""

    def test_a_relative_value_is_joined_onto_the_base(self, tmp_path: Path) -> None:
        assert anchor("vd.json", tmp_path) == tmp_path / "vd.json"
        assert anchor(Path("sub", "vd.json"), tmp_path) == tmp_path / "sub" / "vd.json"

    def test_an_absolute_value_is_untouched(self, tmp_path: Path) -> None:
        absolute = (tmp_path / "elsewhere" / "vd.json").absolute()
        base = tmp_path / "docs"
        assert anchor(str(absolute), base) == absolute
        assert anchor(absolute, base) == absolute

    def test_a_parent_segment_is_kept(self, tmp_path: Path) -> None:
        base = tmp_path / "docs"
        anchored = anchor(str(Path("..", "shared", "vd.json")), base)
        assert anchored == base / ".." / "shared" / "vd.json"
        assert ".." in anchored.parts

    def test_a_symlinked_base_is_not_resolved(self, tmp_path: Path) -> None:
        real = tmp_path / "real"
        real.mkdir()
        (real / "vd.json").write_text("{}", encoding="utf-8")
        link = tmp_path / "link"
        try:
            link.symlink_to(real, target_is_directory=True)
        except OSError:  # pragma: no cover - Windows without the symlink privilege
            pytest.skip("creating a symlink needs a privilege this account lacks")
        anchored = anchor("vd.json", link)
        assert anchored == link / "vd.json"
        assert anchored != anchored.resolve()
        assert anchored.resolve() == (real / "vd.json").resolve()
