"""Tests for sphinx_mounts.config."""

from __future__ import annotations

from pathlib import Path

import pytest
from sphinx.errors import ExtensionError

from sphinx_mounts.config import (
    MountConfig,
    MountConfigError,
    TomlConfigError,
    load_mounts_from_toml,
    parse_mounts,
)


class TestErrorTaxonomy:
    """Config validation failures are hard, non-suppressible Sphinx errors.

    They subclass :class:`sphinx.errors.ExtensionError` (a ``SphinxError``),
    so Sphinx aborts the build with a concise ``Extension error`` message.
    Users cannot suppress them via ``suppress_warnings`` — an unreadable
    config means sphinx-mounts cannot proceed at all. This is the counter-
    part to the soft ``mounts.*`` warnings used for mount-specific problems.
    """

    def test_mount_config_error_is_extension_error(self) -> None:
        assert issubclass(MountConfigError, ExtensionError)

    def test_toml_config_error_is_extension_error(self) -> None:
        assert issubclass(TomlConfigError, ExtensionError)


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

    @pytest.mark.parametrize("field", ["mount_at", "attach_to", "entry_doc"])
    @pytest.mark.parametrize(
        ("value", "match"),
        [
            pytest.param(
                "a//b", "empty or '.' path segment", id="interior-double-slash"
            ),
            pytest.param(
                "a///b", "empty or '.' path segment", id="interior-triple-slash"
            ),
            pytest.param(" a/b", "leading or trailing whitespace", id="leading-space"),
            pytest.param("a/b ", "leading or trailing whitespace", id="trailing-space"),
            pytest.param("a/ b", "whitespace around a path segment", id="inner-lead"),
            pytest.param("a /b", "whitespace around a path segment", id="inner-trail"),
            pytest.param("a/./b", "empty or '.' path segment", id="interior-dot"),
            pytest.param("./a", "empty or '.' path segment", id="leading-dot"),
            pytest.param("a/.", "empty or '.' path segment", id="trailing-dot"),
            pytest.param(".", "empty or '.' path segment", id="bare-dot"),
        ],
    )
    def test_malformed_docname_shapes_rejected(
        self, tmp_path: Path, field: str, value: str, match: str
    ) -> None:
        """Empty segments, ``.`` segments and stray whitespace are hard errors.

        All of these used to be accepted verbatim, because ``.strip("/")``
        only trims the ends and nothing looked inside the segments. A docname
        is matched **literally**, not resolved as a filesystem path, so each
        shape produced something no host document can ever be — the mount was
        accepted and then silently unreferenceable, the worst of the three
        possible outcomes (accept-and-work, reject, accept-and-never-work).

        The bare ``.`` is worse still and has its own test below.

        Config errors are hard and non-suppressible by this extension's own
        doctrine, and being strict keeps the accepted shape describable in a
        few lines for a second implementation.
        """
        with pytest.raises(MountConfigError, match=match):
            MountConfig(dir=tmp_path, **{field: value})

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            pytest.param("a/b", "a/b", id="plain"),
            pytest.param("a/b/", "a/b", id="one-trailing-slash"),
            pytest.param("a/b//", "a/b", id="two-trailing-slashes"),
            pytest.param("a-b_c/d.e", "a-b_c/d.e", id="punctuation-is-fine"),
        ],
    )
    def test_accepted_mount_at_shapes(
        self, tmp_path: Path, value: str, expected: str
    ) -> None:
        """The complement of the rejection list, so the boundary is pinned from
        both sides. Trailing slashes are normalised, not rejected: a prefix
        written with a separator means exactly one thing."""
        assert MountConfig(dir=tmp_path, mount_at=value).mount_at == expected

    @pytest.mark.parametrize("field", ["mount_at", "attach_to", "entry_doc"])
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            pytest.param("a/b/", "a/b", id="one-trailing-slash"),
            pytest.param("a/b//", "a/b", id="two-trailing-slashes"),
            pytest.param("index/", "index", id="single-segment"),
        ],
    )
    def test_trailing_slashes_normalised_on_every_docname_field(
        self, tmp_path: Path, field: str, value: str, expected: str
    ) -> None:
        """All three docname fields normalise trailing slashes identically.

        ``entry_doc`` did not, while the contract and the changelog both said
        the three fields are validated identically and that trailing slashes
        are stripped. The consequence was silent: the wired docname became
        ``"<mount_at>/index/"``, which is not among the docnames the mount
        produced, so the entry-doc gate dropped it and the mount was
        mounted-but-never-wired — reported only as a ``toc.not_included``
        against the bundle file, nowhere near the setting that caused it.
        """
        assert getattr(MountConfig(dir=tmp_path, **{field: value}), field) == expected

    def test_bare_dot_mount_at_is_rejected(self, tmp_path: Path) -> None:
        """``mount_at = "."`` is the one shape whose old behaviour was worse
        than unreferenceable.

        Written to mean "the project root", it produced the docname
        ``./index`` alongside the host project's own ``index``: two distinct
        docnames resolving to one output file, so the mounted page was
        overwritten with no diagnostic at all. Omitting ``mount_at`` is how a
        root mount is expressed, and the error message says so.
        """
        with pytest.raises(MountConfigError) as excinfo:
            MountConfig(dir=tmp_path, mount_at=".")
        message = str(excinfo.value)
        assert "'.' path segment" in message, message
        assert "omit mount_at" in message, message

    def test_leading_double_slash_is_rejected_as_absolute(self, tmp_path: Path) -> None:
        """``//a/b`` is caught by the leading-slash rule, not the empty-segment
        one. Worth pinning because the contract states the leading-slash rule
        first and a second reader must apply it in that order — stripping
        surrounding slashes first would accept it."""
        with pytest.raises(MountConfigError, match="must not start with '/'"):
            MountConfig(dir=tmp_path, mount_at="//a/b")

    def test_extra_keys_are_reported_and_ignored(self, tmp_path: Path) -> None:
        """An unknown key is reported and the rest of the mount is honoured.

        This changed from a hard error deliberately. A ``ubproject.toml`` is
        shared with tools on independent release cadences, so a key this
        reader does not model is routine — and aborting takes down every build
        of the project on every older sphinx-mounts, including builds of
        variants the key would not have changed.

        It also has to ship no later than the release that makes
        ``[[source.mounts]]`` readable, because that is the release which would
        otherwise open the window a future gating key falls into: a reader that
        mounts a bundle while ignoring a key saying *not to* publishes content
        the author gated. Tolerance in the same release closes the window
        before it opens.
        """
        mount = MountConfig.from_dict(
            {
                "dir": tmp_path,
                "mount_at": "ok",
                "unknown_key": True,
            }
        )
        assert mount.mount_at == "ok"
        assert mount.dir == tmp_path

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

    def test_attach_each_defaults_to_false(self, tmp_path: Path) -> None:
        m = MountConfig(files=(tmp_path / "a.rst",), mount_at="x")
        assert m.attach_each is False

    def test_attach_each_valid_for_file_list(self, tmp_path: Path) -> None:
        m = MountConfig.from_dict(
            {
                "files": [str(tmp_path / "a.rst")],
                "mount_at": "x",
                "attach_to": "index",
                "attach_each": True,
            }
        )
        assert m.attach_each is True

    def test_attach_each_non_bool_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="attach_each must be a boolean"):
            MountConfig(
                files=(tmp_path / "a.rst",),
                mount_at="x",
                attach_to="index",
                attach_each="yes",  # type: ignore[arg-type]
            )

    def test_attach_each_requires_file_list_mode(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="only valid in file-list mode"):
            MountConfig(dir=tmp_path, mount_at="x", attach_to="index", attach_each=True)

    def test_attach_each_requires_attach_to(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="attach_each requires attach_to"):
            MountConfig(files=(tmp_path / "a.rst",), mount_at="x", attach_each=True)

    def test_attach_each_conflicts_with_entry_doc(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="entry_doc"):
            MountConfig(
                files=(tmp_path / "a.rst",),
                mount_at="x",
                attach_to="index",
                attach_each=True,
                entry_doc="intro",
            )

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

    def test_path_check_defaults_to_warn(self, tmp_path: Path) -> None:
        """The default is the extension's own doctrine: a typed warning that
        ``sphinx-build -W`` escalates.

        It was ``"error"``. That fought the doctrine
        (``sphinx_mounts.logging``: every mount-specific problem is a
        suppressible warning that ``-W`` turns into a failure) and could not
        deliver what it promised anyway, since the check is skipped entirely
        on a build that reads no document.
        """
        assert MountConfig(dir=tmp_path, mount_at="x").path_check == "warn"
        # ...and via the TOML/dict path, which has its own default literal.
        assert (
            MountConfig.from_dict({"dir": str(tmp_path), "mount_at": "x"}).path_check
            == "warn"
        )

    def test_path_check_accepts_warn_and_off(self, tmp_path: Path) -> None:
        assert (
            MountConfig.from_dict(
                {"dir": tmp_path, "mount_at": "x", "path_check": "warn"}
            ).path_check
            == "warn"
        )
        assert (
            MountConfig.from_dict(
                {"dir": tmp_path, "mount_at": "x", "path_check": "off"}
            ).path_check
            == "off"
        )

    def test_path_check_invalid_value_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match=r"path_check must be one of"):
            MountConfig(dir=tmp_path, mount_at="x", path_check="boom")

    def test_path_check_non_string_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="path_check must be a string"):
            MountConfig(dir=tmp_path, mount_at="x", path_check=True)  # type: ignore[arg-type]


class TestMountGateKey:
    """``if`` on a mount entry, as :class:`MountConfig` sees it.

    The reader at ``config-inited`` priority 450 owns the decision (see
    ``tests/test_variant_sources.py``); what is pinned here is the contract
    between that reader and the parser at 500, plus the fail-closed reading
    of the one route the reader never sees.
    """

    def test_absent_condition_leaves_the_mount_live(self, tmp_path: Path) -> None:
        """The state a gated-ON mount reaches the parser in: no ``if`` at all.

        The reader strips the key when the condition holds, which is what
        keeps a correctly-gated project free of ``mounts.unknown_key`` — the
        key is a Python keyword, so no dataclass field could ever model it.
        """
        assert MountConfig.from_dict({"dir": tmp_path}).gated_by is None

    def test_surviving_condition_gates_the_mount_off(self, tmp_path: Path) -> None:
        """A surviving ``if`` is the gate marker, carrying its own text."""
        mount = MountConfig.from_dict({"dir": tmp_path, "if": "var.edition == 'pro'"})
        assert mount.gated_by == "var.edition == 'pro'"

    def test_the_condition_is_not_an_unknown_key(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``if`` is taken off the entry *before* the unknown-key check.

        Reporting it would be the trap this key has to avoid: the warning is
        a warning, so ``sphinx-build -W`` would fail a project whose only sin
        is using the key as documented.
        """
        with caplog.at_level("WARNING"):
            MountConfig.from_dict({"dir": tmp_path, "if": "var.edition == 'pro'"})
        assert "unknown mount key" not in caplog.text

    def test_gated_by_is_not_a_user_key(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Writing the internal field name in TOML must not gate a mount.

        ``from_dict`` derives its allowed set from the dataclass fields, so
        without the explicit subtraction ``gated_by`` would become an
        accepted mount key — a switch that silently removes a whole bundle
        and that no documentation mentions.
        """
        with caplog.at_level("WARNING"):
            mount = MountConfig.from_dict({"dir": tmp_path, "gated_by": "anything"})
        assert mount.gated_by is None
        assert "unknown mount key" in caplog.text

    @pytest.mark.parametrize(
        ("written", "expected"),
        [(3, "3"), ("", "''"), ("   ", "'   '"), (True, "True")],
    )
    def test_an_unusable_condition_still_gates_off(
        self, tmp_path: Path, written: object, expected: str
    ) -> None:
        """Fail closed: a condition this parser cannot read keeps content out.

        Unreachable from a project the reader saw — it refuses the whole
        configuration over a non-string ``if`` — so this covers the route it
        never sees, where publishing the bundle would be the one outcome a
        gating key must not have.
        """
        mount = MountConfig.from_dict({"dir": tmp_path, "if": written})
        assert mount.gated_by == expected

    def test_non_string_gate_is_rejected_on_the_dataclass(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="gated_by must be a string"):
            MountConfig(dir=tmp_path, gated_by=3)  # type: ignore[arg-type]

    def test_the_unknown_key_message_advertises_the_condition_key(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A user who typed ``iff`` must find ``if`` in the list they are sent to.

        The advertised list is derived from the dataclass fields, and ``if``
        can never be one — it is a Python keyword. So the message told a user
        to check their spelling against a list missing the very key they meant,
        which is worse than saying nothing.
        """
        with caplog.at_level("WARNING"):
            MountConfig.from_dict({"dir": tmp_path, "iff": "var.edition == 'pro'"})
        assert "unknown mount key" in caplog.text
        assert "'if'" in caplog.text, caplog.text

    def test_from_dict_does_not_mutate_its_argument(self, tmp_path: Path) -> None:
        """The caller's table is not the parser's scratch space.

        ``_on_load_variants`` hands the parser the same tables it left on
        ``config["mounts"]``, and Sphinx compares that value against the
        previous build's to decide whether to re-read every document.
        Popping ``if`` out of the caller's dict would erase the gate from the
        config value and take the convergence with it.
        """
        entry: dict[str, object] = {"dir": tmp_path, "if": "var.edition == 'pro'"}
        MountConfig.from_dict(entry)
        assert entry["if"] == "var.edition == 'pro'"


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

    def test_missing_dir_resolves_without_raising(self, tmp_path: Path) -> None:
        """A missing directory is *not* a config error: it resolves to an
        absolute path and is reported as a ``mounts.missing_path`` warning
        at mount time, so a build whose upstream bundle is absent (e.g. CI
        that has not run the Bazel build yet) can still proceed."""
        mounts = parse_mounts(
            [{"dir": "does_not_exist", "mount_at": "_g/x"}],
            tmp_path,
        )
        assert len(mounts) == 1
        assert mounts[0].dir == (tmp_path / "does_not_exist").resolve()

    def test_non_list_raises(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="must be a list"):
            parse_mounts({"a": 1}, tmp_path)

    def test_non_dict_entry_raises(self, tmp_path: Path) -> None:
        with pytest.raises(MountConfigError, match="must be a mapping"):
            parse_mounts(["not_a_dict"], tmp_path)

    def test_accepts_mountconfig_instance(self, tmp_path: Path) -> None:
        (tmp_path / "bundle").mkdir()
        raw = MountConfig(dir=tmp_path / "bundle", mount_at="_g/x")
        mounts = parse_mounts([raw], tmp_path)
        assert mounts[0].mount_at == "_g/x"

    def test_preserves_path_check(self, tmp_path: Path) -> None:
        (tmp_path / "bundle").mkdir()
        mounts = parse_mounts(
            [{"dir": "bundle", "mount_at": "_g/x", "path_check": "warn"}],
            tmp_path,
        )
        assert mounts[0].path_check == "warn"

    def test_preserves_the_gate(self, tmp_path: Path) -> None:
        """The gate has to survive the re-construction ``parse_mounts`` does.

        It rebuilds every :class:`MountConfig` field by field to absolutise
        the paths, so a field it forgets is dropped silently — and dropping
        *this* one un-gates the mount, publishing the bundle the author
        gated. Nothing else in the pipeline would notice.
        """
        (tmp_path / "bundle").mkdir()
        mounts = parse_mounts(
            [{"dir": "bundle", "if": "var.edition == 'pro'"}],
            tmp_path,
        )
        assert mounts[0].gated_by == "var.edition == 'pro'"


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


class TestNamespacedMountsTable:
    """``[[source.mounts]]`` is accepted alongside the top-level ``[[mounts]]``.

    ``[source]`` is the table that owns source discovery in the
    ``ubproject.toml`` vocabulary shared with sibling tooling, so it is the
    natural home for a mount and the spelling the docs now recommend. The
    original top-level spelling stays supported, and the two must be
    indistinguishable in every respect except where they are written.
    """

    def test_namespaced_table_is_loaded(self, tmp_path: Path) -> None:
        toml = tmp_path / "ubproject.toml"
        toml.write_text(
            '[[source.mounts]]\ndir = "bundle_a"\nmount_at = "_generated/api-a"\n',
            encoding="utf-8",
        )
        raw = load_mounts_from_toml(toml)
        assert raw is not None
        assert len(raw) == 1
        assert raw[0]["mount_at"] == "_generated/api-a"

    def test_namespaced_table_anchors_paths_identically(self, tmp_path: Path) -> None:
        """Path anchoring is a property of the file, not of the table it is
        written in, so both spellings must produce the same absolute paths."""
        subdir = tmp_path / "configs"
        subdir.mkdir()
        top = subdir / "top.toml"
        top.write_text('[[mounts]]\ndir = "../shared"\n', encoding="utf-8")
        namespaced = subdir / "namespaced.toml"
        namespaced.write_text(
            '[[source.mounts]]\ndir = "../shared"\n', encoding="utf-8"
        )

        assert load_mounts_from_toml(top) == load_mounts_from_toml(namespaced)
        loaded = load_mounts_from_toml(namespaced)
        assert loaded is not None
        assert loaded[0]["dir"] == str((tmp_path / "shared").resolve())

    def test_namespaced_table_coexists_with_other_source_keys(
        self, tmp_path: Path
    ) -> None:
        """A ``[source]`` table carrying keys owned by other tools must not
        disturb the mounts array nested inside it."""
        toml = tmp_path / "ubproject.toml"
        toml.write_text(
            "[source]\n"
            "respect_gitignore = true\n"
            'include = ["*.rst"]\n'
            "\n"
            "[[source.mounts]]\n"
            'dir = "bundle"\n'
            'mount_at = "_g/x"\n',
            encoding="utf-8",
        )
        raw = load_mounts_from_toml(toml)
        assert raw is not None
        assert len(raw) == 1
        assert raw[0]["mount_at"] == "_g/x"

    def test_declaring_both_spellings_raises(self, tmp_path: Path) -> None:
        """Two declarations in one file is a hard error, not a precedence
        puzzle: which one wins is not something a reader of the file could
        know, and silently merging them would be worse."""
        toml = tmp_path / "ubproject.toml"
        toml.write_text(
            '[[mounts]]\ndir = "a"\n\n[[source.mounts]]\ndir = "b"\n',
            encoding="utf-8",
        )
        with pytest.raises(TomlConfigError) as excinfo:
            load_mounts_from_toml(toml)
        message = str(excinfo.value)
        # BOTH locations are named, so the user knows what to delete.
        assert "[[source.mounts]]" in message
        assert "[[mounts]]" in message
        assert str(toml) in message

    def test_source_table_without_mounts_is_not_a_declaration(
        self, tmp_path: Path
    ) -> None:
        """A ``[source]`` table that declares no ``mounts`` key returns
        ``None``, so a legacy ``mounts`` in ``conf.py`` still applies.

        This is the namespaced half of the "declares mounts" rule: a TOML file
        present for *other* tools must not silently switch mounts off.
        """
        toml = tmp_path / "ubproject.toml"
        toml.write_text("[source]\nrespect_gitignore = true\n", encoding="utf-8")
        assert load_mounts_from_toml(toml) is None

    def test_empty_namespaced_array_is_an_explicit_override(
        self, tmp_path: Path
    ) -> None:
        """An explicitly empty array is a declaration of "no mounts" and must
        be distinguishable from an absent key, in the namespaced form exactly
        as in the top-level one."""
        toml = tmp_path / "ubproject.toml"
        toml.write_text("[source]\nmounts = []\n", encoding="utf-8")
        assert load_mounts_from_toml(toml) == []

    def test_empty_top_level_array_is_an_explicit_override(
        self, tmp_path: Path
    ) -> None:
        toml = tmp_path / "ubproject.toml"
        toml.write_text("mounts = []\n", encoding="utf-8")
        assert load_mounts_from_toml(toml) == []

    def test_namespaced_mounts_not_a_list_raises(self, tmp_path: Path) -> None:
        toml = tmp_path / "ubproject.toml"
        toml.write_text("[source.mounts]\nfoo = 1\n", encoding="utf-8")
        with pytest.raises(TomlConfigError, match="must be an array of tables"):
            load_mounts_from_toml(toml)

    def test_namespaced_shape_error_names_the_namespaced_location(
        self, tmp_path: Path
    ) -> None:
        """The shape error must name the table the user actually wrote, not
        always the top-level one."""
        toml = tmp_path / "ubproject.toml"
        toml.write_text("[source]\nmounts = [1]\n", encoding="utf-8")
        with pytest.raises(TomlConfigError) as excinfo:
            load_mounts_from_toml(toml)
        assert "[[source.mounts]]" in str(excinfo.value)

    def test_source_that_is_not_a_table_is_ignored(self, tmp_path: Path) -> None:
        """``source`` owned by another tool as a scalar must not crash the
        lookup; the top-level array still applies."""
        toml = tmp_path / "ubproject.toml"
        toml.write_text(
            'source = "somewhere"\n[[mounts]]\ndir = "a"\n', encoding="utf-8"
        )
        raw = load_mounts_from_toml(toml)
        assert raw is not None
        assert len(raw) == 1

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
