"""Tests for sphinx_mounts.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from sphinx_mounts.config import (
    MountConfig,
    MountConfigError,
    TomlConfigError,
    load_mounts_from_toml,
    parse_mounts,
)


class TestMountConfig:
    def test_minimal_valid(self, tmp_path: Path) -> None:
        m = MountConfig(dir=tmp_path, mount_at="_generated/foo")
        assert m.mount_at == "_generated/foo"
        assert m.exclude == ()

    def test_mount_at_strips_trailing_slash(self, tmp_path: Path) -> None:
        m = MountConfig(dir=tmp_path, mount_at="_generated/foo/")
        assert m.mount_at == "_generated/foo"

    def test_mount_at_empty_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="non-empty"):
            MountConfig(dir=tmp_path, mount_at="")

    def test_mount_at_absolute_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="must not start with '/'"):
            MountConfig(dir=tmp_path, mount_at="/abs/foo")

    def test_mount_at_with_dotdot_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="must not contain"):
            MountConfig(dir=tmp_path, mount_at="_generated/../escape")

    def test_extra_keys_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="Unknown mount keys"):
            MountConfig.from_dict(
                {
                    "dir": tmp_path,
                    "mount_at": "ok",
                    "unknown_key": True,
                }
            )

    def test_missing_required_key_rejected(self) -> None:
        # Neither `dir` nor `files` present.
        with pytest.raises(MountConfigError, match=r"either 'dir'.*or 'files'"):
            MountConfig.from_dict({"mount_at": "ok"})

    def test_mount_at_defaults_to_none(self, tmp_path: Path) -> None:
        m = MountConfig(dir=tmp_path)
        assert m.mount_at is None

    def test_mount_at_omitted_in_from_dict_yields_none(self, tmp_path: Path) -> None:
        m = MountConfig.from_dict({"dir": str(tmp_path)})
        assert m.mount_at is None
        assert m.dir == tmp_path

    def test_dir_and_files_mutually_exclusive(self, tmp_path: Path) -> None:
        f = tmp_path / "f.rst"
        f.write_text("x", encoding="utf-8")
        # Both modes set via dataclass constructor.
        with pytest.raises(MountConfigError, match="not both"):
            MountConfig(mount_at="x", dir=tmp_path, files=(f,))
        # Both modes set via from_dict.
        with pytest.raises(MountConfigError, match=r"'dir'.*'files'.*not both"):
            MountConfig.from_dict(
                {"mount_at": "x", "dir": str(tmp_path), "files": [str(f)]}
            )

    def test_neither_dir_nor_files_rejected(self) -> None:
        with pytest.raises(MountConfigError, match=r"either `dir`.*or `files`"):
            MountConfig(mount_at="x")

    def test_files_mode_accepts_single_file(self, tmp_path: Path) -> None:
        f = tmp_path / "f.rst"
        m = MountConfig(mount_at="x", files=(f,))
        assert m.files == (f,)
        assert m.dir is None

    def test_files_mode_accepts_multiple_files(self, tmp_path: Path) -> None:
        a, b = tmp_path / "a.rst", tmp_path / "b.rst"
        m = MountConfig(mount_at="x", files=(a, b))
        assert m.files == (a, b)

    def test_files_must_be_non_empty(self) -> None:
        with pytest.raises(MountConfigError, match="at least one"):
            MountConfig(mount_at="x", files=())

    def test_files_must_be_tuple(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="must be a tuple"):
            MountConfig(mount_at="x", files=[tmp_path / "f.rst"])  # type: ignore[arg-type]

    def test_from_dict_files_coerces_strings_to_paths(self, tmp_path: Path) -> None:
        f = tmp_path / "f.rst"
        m = MountConfig.from_dict({"mount_at": "x", "files": [str(f)]})
        assert m.files == (f,)
        assert m.dir is None

    def test_from_dict_files_rejects_non_list(self) -> None:
        with pytest.raises(MountConfigError, match="files must be a list"):
            MountConfig.from_dict({"mount_at": "x", "files": "f.rst"})

    def test_from_dict_files_rejects_empty(self) -> None:
        with pytest.raises(MountConfigError, match="at least one"):
            MountConfig.from_dict({"mount_at": "x", "files": []})

    def test_dir_coerced_from_string(self, tmp_path: Path) -> None:
        m = MountConfig.from_dict({"dir": str(tmp_path), "mount_at": "x"})
        assert m.dir == tmp_path

    def test_exclude_coerced_to_tuple(self, tmp_path: Path) -> None:
        m = MountConfig.from_dict(
            {
                "dir": tmp_path,
                "mount_at": "x",
                "exclude": ["a.rst", "b.rst"],
            }
        )
        assert m.exclude == ("a.rst", "b.rst")

    def test_exclude_wrong_type_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="exclude must"):
            MountConfig.from_dict(
                {
                    "dir": tmp_path,
                    "mount_at": "x",
                    "exclude": "not-a-list",
                }
            )

    def test_include_coerced_to_tuple(self, tmp_path: Path) -> None:
        m = MountConfig.from_dict(
            {
                "dir": tmp_path,
                "mount_at": "x",
                "include": ["**/*.rst"],
            }
        )
        assert m.include == ("**/*.rst",)

    def test_include_wrong_type_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="include must"):
            MountConfig.from_dict(
                {
                    "dir": tmp_path,
                    "mount_at": "x",
                    "include": "single-string-not-a-list",
                }
            )

    def test_gitignore_defaults_to_true(self, tmp_path: Path) -> None:
        m = MountConfig(dir=tmp_path, mount_at="x")
        assert m.gitignore is True

    def test_gitignore_can_be_disabled(self, tmp_path: Path) -> None:
        m = MountConfig.from_dict(
            {"dir": tmp_path, "mount_at": "x", "gitignore": False}
        )
        assert m.gitignore is False

    def test_gitignore_non_bool_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="gitignore must be a boolean"):
            MountConfig(dir=tmp_path, mount_at="x", gitignore="yes")  # type: ignore[arg-type]

    def test_frozen(self, tmp_path: Path) -> None:
        m = MountConfig(dir=tmp_path, mount_at="x")
        with pytest.raises(Exception, match="cannot assign"):  # FrozenInstanceError
            m.mount_at = "y"  # type: ignore[misc]

    def test_attach_to_defaults_to_none(self, tmp_path: Path) -> None:
        m = MountConfig(dir=tmp_path, mount_at="x")
        assert m.attach_to is None
        assert m.toctree_index == 0
        assert m.entry_doc == "index"

    def test_attach_to_valid(self, tmp_path: Path) -> None:
        m = MountConfig(dir=tmp_path, mount_at="x", attach_to="index")
        assert m.attach_to == "index"

    def test_attach_to_empty_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="attach_to must be a non-empty"):
            MountConfig(dir=tmp_path, mount_at="x", attach_to="")

    def test_attach_to_absolute_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="attach_to must not start with"):
            MountConfig(dir=tmp_path, mount_at="x", attach_to="/abs")

    def test_attach_to_dotdot_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="attach_to must not contain"):
            MountConfig(dir=tmp_path, mount_at="x", attach_to="../escape")

    def test_toctree_index_negative_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="non-negative"):
            MountConfig(dir=tmp_path, mount_at="x", toctree_index=-1)

    def test_toctree_index_bool_rejected(self, tmp_path: Path) -> None:
        # bool is a subclass of int — reject it explicitly.
        with pytest.raises(MountConfigError, match="non-negative integer"):
            MountConfig(dir=tmp_path, mount_at="x", toctree_index=True)  # type: ignore[arg-type]

    def test_entry_doc_default(self, tmp_path: Path) -> None:
        m = MountConfig(dir=tmp_path, mount_at="x")
        assert m.entry_doc == "index"

    def test_entry_doc_custom(self, tmp_path: Path) -> None:
        m = MountConfig(dir=tmp_path, mount_at="x", entry_doc="tutorial")
        assert m.entry_doc == "tutorial"

    def test_entry_doc_empty_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="entry_doc must be a non-empty"):
            MountConfig(dir=tmp_path, mount_at="x", entry_doc="")

    def test_entry_doc_absolute_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="entry_doc must not start with"):
            MountConfig(dir=tmp_path, mount_at="x", entry_doc="/abs")

    def test_strict_mount_at_defaults_to_false(self, tmp_path: Path) -> None:
        m = MountConfig(dir=tmp_path, mount_at="x")
        assert m.strict_mount_at is False

    def test_strict_mount_at_can_be_enabled(self, tmp_path: Path) -> None:
        m = MountConfig.from_dict(
            {"dir": tmp_path, "mount_at": "x", "strict_mount_at": True}
        )
        assert m.strict_mount_at is True

    def test_strict_mount_at_non_bool_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="strict_mount_at must be a boolean"):
            MountConfig(dir=tmp_path, mount_at="x", strict_mount_at="yes")  # type: ignore[arg-type]

    def test_strict_mount_at_requires_mount_at(self, tmp_path: Path) -> None:
        # Root-mounted bundles cannot meaningfully assert "no host dir at
        # mount_at" because the host srcdir always exists.
        with pytest.raises(MountConfigError, match=r"strict_mount_at.*mount_at"):
            MountConfig(dir=tmp_path, strict_mount_at=True)


class TestParseMounts:
    def test_empty_list(self, tmp_path: Path) -> None:
        assert parse_mounts([], tmp_path) == ()

    def test_none(self, tmp_path: Path) -> None:
        assert parse_mounts(None, tmp_path) == ()

    def test_resolves_relative_dir(self, tmp_path: Path) -> None:
        (tmp_path / "bundle").mkdir()
        mounts = parse_mounts([{"dir": "bundle", "mount_at": "_g/x"}], tmp_path)
        assert len(mounts) == 1
        assert mounts[0].dir == (tmp_path / "bundle").resolve()

    def test_keeps_absolute_dir(self, tmp_path: Path) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        mounts = parse_mounts([{"dir": str(bundle), "mount_at": "_g/x"}], tmp_path)
        assert mounts[0].dir == bundle.resolve()

    def test_missing_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            parse_mounts(
                [{"dir": "does_not_exist", "mount_at": "_g/x"}],
                tmp_path,
            )

    def test_non_list_raises(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError, match="must be a list"):
            parse_mounts({"a": 1}, tmp_path)

    def test_non_dict_entry_raises(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError, match="must be a mapping"):
            parse_mounts(["not_a_dict"], tmp_path)

    def test_accepts_mountconfig_instance(self, tmp_path: Path) -> None:
        (tmp_path / "bundle").mkdir()
        raw = MountConfig(dir=tmp_path / "bundle", mount_at="_g/x")
        mounts = parse_mounts([raw], tmp_path)
        assert mounts[0].mount_at == "_g/x"


class TestLoadMountsFromToml:
    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert load_mounts_from_toml(tmp_path / "nope.toml") is None

    def test_file_without_mounts_section_returns_none(self, tmp_path: Path) -> None:
        toml = tmp_path / "ubproject.toml"
        toml.write_text("[other_tool]\nfoo = 1\n", encoding="utf-8")
        assert load_mounts_from_toml(toml) is None

    def test_loads_valid_mounts(self, tmp_path: Path) -> None:
        toml = tmp_path / "ubproject.toml"
        toml.write_text(
            "[[mounts]]\n"
            'dir = "bundle_a"\n'
            'mount_at = "_generated/api-a"\n'
            "\n"
            "[[mounts]]\n"
            'dir = "bundle_b"\n'
            'mount_at = "_generated/api-b"\n'
            'exclude = ["*.tmp", "internal/*"]\n',
            encoding="utf-8",
        )
        raw = load_mounts_from_toml(toml)
        assert raw is not None
        assert len(raw) == 2
        # Relative paths are resolved to absolute, anchored to the TOML's
        # own directory (here, ``tmp_path``).
        assert raw[0]["dir"] == str(tmp_path / "bundle_a")
        assert raw[0]["mount_at"] == "_generated/api-a"
        assert raw[1]["dir"] == str(tmp_path / "bundle_b")
        assert raw[1]["exclude"] == ["*.tmp", "internal/*"]

    def test_paths_anchor_to_toml_directory_not_cwd(self, tmp_path: Path) -> None:
        """A TOML in a subdir of confdir anchors its relative paths to
        the TOML's own directory, not to confdir or to the working
        directory of the build."""
        subdir = tmp_path / "configs"
        subdir.mkdir()
        toml = subdir / "ubproject.toml"
        toml.write_text(
            "[[mounts]]\n"
            # `../shared` is *relative to the TOML*, i.e. tmp_path/shared
            'dir = "../shared"\n'
            'mount_at = "_g/shared"\n'
            "\n"
            "[[mounts]]\n"
            # File-list paths are anchored the same way.
            'files = ["../files/one.rst", "../files/two.rst"]\n'
            'mount_at = "_g/picked"\n',
            encoding="utf-8",
        )
        raw = load_mounts_from_toml(toml)
        assert raw is not None
        assert raw[0]["dir"] == str((tmp_path / "shared").resolve())
        assert raw[1]["files"] == [
            str((tmp_path / "files" / "one.rst").resolve()),
            str((tmp_path / "files" / "two.rst").resolve()),
        ]

    def test_absolute_paths_pass_through_unchanged(self, tmp_path: Path) -> None:
        abs_dir = tmp_path / "abs"
        toml = tmp_path / "ubproject.toml"
        # Use a TOML *literal* string (single quotes) so that a Windows
        # absolute path like ``C:\Users\...`` is not interpreted as TOML
        # escape sequences (``\U`` would otherwise be parsed as a
        # \Uxxxxxxxx Unicode escape and fail to parse).
        toml.write_text(
            f"[[mounts]]\ndir = '{abs_dir}'\nmount_at = '_g/abs'\n",
            encoding="utf-8",
        )
        raw = load_mounts_from_toml(toml)
        assert raw is not None
        # Absolute paths are not touched — no symlink resolution or
        # case-folding surprise.
        assert raw[0]["dir"] == str(abs_dir)

    def test_malformed_toml_raises(self, tmp_path: Path) -> None:
        toml = tmp_path / "ubproject.toml"
        toml.write_text("not = valid = toml\n", encoding="utf-8")
        with pytest.raises(TomlConfigError, match="failed to parse"):
            load_mounts_from_toml(toml)

    def test_mounts_not_a_list_raises(self, tmp_path: Path) -> None:
        toml = tmp_path / "ubproject.toml"
        # Top-level `[mounts]` table — a table, not an array of tables.
        toml.write_text("[mounts]\nfoo = 1\n", encoding="utf-8")
        with pytest.raises(TomlConfigError, match="must be an array of tables"):
            load_mounts_from_toml(toml)

    def test_pipeline_loads_and_validates(self, tmp_path: Path) -> None:
        """Round-trip: TOML → load_mounts_from_toml → parse_mounts."""
        (tmp_path / "bundle").mkdir()
        toml = tmp_path / "ubproject.toml"
        toml.write_text(
            '[[mounts]]\ndir = "bundle"\nmount_at = "_g/x"\n',
            encoding="utf-8",
        )
        raw = load_mounts_from_toml(toml)
        assert raw is not None
        parsed = parse_mounts(raw, tmp_path)
        assert len(parsed) == 1
        assert parsed[0].dir == (tmp_path / "bundle").resolve()
        assert parsed[0].mount_at == "_g/x"
