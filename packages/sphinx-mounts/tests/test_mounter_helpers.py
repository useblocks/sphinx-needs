"""Unit tests for small private helpers in sphinx_mounts.mounter."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sphinx.project import Project

from sphinx_mounts.config import MountConfig
from sphinx_mounts.extension import _wiring_signature
from sphinx_mounts.mounter import (
    _is_within,
    _is_within_any,
    _join_mount,
    _listed_roots,
    install_mount_aware_project,
)


class TestJoinMount:
    def test_with_prefix(self) -> None:
        assert _join_mount("_generated/api", "intro") == "_generated/api/intro"

    def test_with_nested_prefix(self) -> None:
        assert _join_mount("a/b/c", "sub/page") == "a/b/c/sub/page"

    def test_with_none_prefix_returns_tail(self) -> None:
        assert _join_mount(None, "tutorial") == "tutorial"

    def test_with_none_prefix_and_nested_tail(self) -> None:
        assert _join_mount(None, "guides/intro") == "guides/intro"


class TestIsWithin:
    """``_is_within`` backs the whole ``path_check`` feature, so it is tested
    directly rather than only through a build."""

    def test_direct_child_is_within(self) -> None:
        assert _is_within(Path("/bundle"), Path("/bundle/page.rst"))

    def test_nested_descendant_is_within(self) -> None:
        assert _is_within(Path("/bundle"), Path("/bundle/a/b/c.txt"))

    def test_the_root_itself_is_within(self) -> None:
        # A dependency recorded as the bundle root itself must not be an
        # escape; the previous implementation special-cased this and the
        # replacement has to keep it.
        assert _is_within(Path("/bundle"), Path("/bundle"))

    def test_sibling_is_not_within(self) -> None:
        assert not _is_within(Path("/bundle"), Path("/other/page.rst"))

    def test_parent_is_not_within(self) -> None:
        assert not _is_within(Path("/bundle"), Path("/page.rst"))

    def test_name_prefix_is_not_within(self) -> None:
        # A pure string ``startswith`` would wrongly accept this: the
        # comparison has to be per path component.
        assert not _is_within(Path("/bundle"), Path("/bundle-extra/page.rst"))

    def test_case_fold_is_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The containment comparison must go through ``os.path.normcase``.

        On Windows — case-insensitive but case-preserving — a bundle
        configured as ``C:/x/Bundle`` whose real directory is ``bundle``
        produces two paths that differ only in case, and ``Path.resolve()``
        does not fold case. Rejecting that as an escape would be a false
        positive on every Windows run, a platform CI covers but no test
        exercised.

        ``normcase`` is the identity function on POSIX — macOS included, so
        the fold is Windows-only and macOS keeps the case-sensitive
        comparison asserted by the next test. That is also why this
        monkeypatches ``normcase`` to a case-folding stand-in: without it the
        assertion is untestable on any POSIX runner, and a regression would
        only ever surface on Windows.
        """
        monkeypatch.setattr(os.path, "normcase", str.lower)
        assert _is_within(Path("/x/Bundle"), Path("/x/bundle/page.rst"))
        assert _is_within(Path("/x/bundle"), Path("/x/Bundle/SUB/page.rst"))
        # The fold must not make unrelated paths match.
        assert not _is_within(Path("/x/Bundle"), Path("/x/other/page.rst"))

    def test_case_difference_without_a_fold_is_an_escape(self) -> None:
        """On a case-sensitive filesystem (the Linux default) two paths that
        differ in case really are different directories, so the honest answer
        is "not within" — the fold must come from ``normcase``, not from an
        unconditional lowercase."""
        if os.path.normcase("A") != "A":  # pragma: no cover - non-POSIX runner
            pytest.skip("filesystem paths are case-folded on this platform")
        assert not _is_within(Path("/x/Bundle"), Path("/x/bundle/page.rst"))


class TestListedRoots:
    """The confinement root SET of a file-list mount.

    Fixture paths are anchored under a resolved ``tmp_path`` (the ``base``
    fixture) rather than fabricated absolute literals: the helper resolves
    each parent, and a fabricated path resolves differently per platform —
    on macOS ``/var`` is a symlink into ``/private``, and on Windows a
    drive-less ``/pkg`` lands on the current drive (``D:/pkg`` on CI) — so
    literal expectations fail on exactly the platforms CI adds. An
    already-canonical prefix makes the resolve a no-op everywhere.
    """

    @pytest.fixture()
    def base(self, tmp_path: Path) -> Path:
        """Canonical absolute prefix for fabricated paths (see class docstring)."""
        return tmp_path.resolve()

    def test_single_file_root_is_its_parent(self, base: Path) -> None:
        assert _listed_roots([base / "rn/index.rst"]) == (base / "rn",)

    def test_files_at_different_depths_contribute_both_parents(
        self, base: Path
    ) -> None:
        """The deeper file's own directory AND the shallower one are roots, so
        a reference from the deeper document up into the shallower directory is
        in-bundle. That is the asymmetry the union rule exists to fix."""
        assert _listed_roots(
            [base / "rn/index.rst", base / "rn/notes/2026-q1.rst"]
        ) == (base / "rn", base / "rn/notes")

    def test_sibling_directories_do_not_promote_their_shared_parent(
        self, base: Path
    ) -> None:
        """The bound that matters: listing `pkg/a/one.rst` and `pkg/b/two.rst`
        makes `pkg/a` and `pkg/b` roots — NOT `pkg`.

        The common ancestor would be `pkg`, which the user never named, and
        everything else under it would silently become in-bundle. With two
        entries on unrelated filesystem branches the ancestor would be the
        filesystem root, turning even ``path_check = "error"`` into a no-op.
        """
        roots = _listed_roots([base / "pkg/a/one.rst", base / "pkg/b/two.rst"])
        assert roots == (base / "pkg/a", base / "pkg/b")
        assert base / "pkg" not in roots

    def test_identical_parents_collapse_to_one_root(self, base: Path) -> None:
        assert _listed_roots([base / "pkg/one.rst", base / "pkg/two.rst"]) == (
            base / "pkg",
        )

    def test_order_follows_the_files_list(self, base: Path) -> None:
        """Roots are reported in ``files`` order so diagnostics are stable."""
        assert _listed_roots([base / "z/one.rst", base / "a/two.rst"]) == (
            base / "z",
            base / "a",
        )

    def test_disjoint_branches_stay_disjoint(self, base: Path) -> None:
        """Branches that share nothing below the anchor contribute exactly
        themselves. No ancestor is computed, so there is no ``ValueError``
        case and no fallback to report — the previous implementation needed
        both."""
        assert _listed_roots([base / "opt/a/one.rst", base / "usr/b/two.rst"]) == (
            base / "opt/a",
            base / "usr/b",
        )


class TestIsWithinAny:
    """One containment check against a whole mount's root set."""

    def test_matches_the_first_root(self) -> None:
        assert _is_within_any([Path("/a"), Path("/b")], Path("/a/page.rst"))

    def test_matches_a_later_root(self) -> None:
        assert _is_within_any([Path("/a"), Path("/b")], Path("/b/deep/page.rst"))

    def test_root_itself_is_within(self) -> None:
        assert _is_within_any([Path("/a"), Path("/b")], Path("/b"))

    def test_outside_every_root_is_not_within(self) -> None:
        assert not _is_within_any([Path("/a"), Path("/b")], Path("/c/page.rst"))

    def test_the_shared_parent_of_the_roots_is_not_within(self) -> None:
        """The union must not admit the roots' common ancestor."""
        assert not _is_within_any(
            [Path("/pkg/a"), Path("/pkg/b")], Path("/pkg/secret.txt")
        )

    def test_empty_root_set_admits_nothing(self) -> None:
        assert not _is_within_any([], Path("/a/page.rst"))


class TestInstallMountAwareProject:
    """The swap-in copy-constructor over a class this extension does not own."""

    @staticmethod
    def _stock(tmp_path: Path) -> Project:
        project = Project(tmp_path, (".rst",))
        project.docnames.add("index")
        project._docname_to_path["index"] = Path("index.rst")
        project._path_to_docname[Path("index.rst")] = "index"
        return project

    def test_known_state_travels(self, tmp_path: Path) -> None:
        stock = self._stock(tmp_path)
        new = install_mount_aware_project(stock, ())
        assert new.docnames == {"index"}
        assert new._docname_to_path == {"index": Path("index.rst")}
        assert new._path_to_docname == {Path("index.rst"): "index"}
        assert new.source_suffix == (".rst",)

    def test_unknown_attributes_travel_too(self, tmp_path: Path) -> None:
        """A field a future Sphinx adds to ``Project`` must not be dropped.

        This is a hand-rolled copy-constructor over an upstream class, so
        enumerating fields by name means a new one disappears silently — the
        worst failure mode available, because the resulting project looks
        complete and is simply missing something. Copying wholesale makes
        unknown state travel by default.
        """
        stock = self._stock(tmp_path)
        stock.a_field_from_a_future_sphinx = "carry me"  # type: ignore[attr-defined]
        new = install_mount_aware_project(stock, ())
        assert new.a_field_from_a_future_sphinx == "carry me"

    def test_docname_containers_are_not_shared_with_the_old_project(
        self, tmp_path: Path
    ) -> None:
        """The copy must not alias the old project's mutable containers.

        ``discover()`` clears and repopulates all three on the new project;
        aliasing would reach back into the object being replaced.
        """
        stock = self._stock(tmp_path)
        new = install_mount_aware_project(stock, ())
        new.docnames.add("extra")
        new._docname_to_path["extra"] = Path("extra.rst")
        new._path_to_docname[Path("extra.rst")] = "extra"
        assert stock.docnames == {"index"}
        assert "extra" not in stock._docname_to_path
        assert Path("extra.rst") not in stock._path_to_docname

    def test_mount_state_is_not_taken_from_the_old_project(
        self, tmp_path: Path
    ) -> None:
        """Fields this subclass owns come from the constructor, never from the
        project being replaced — even if that project happens to carry
        same-named attributes (a second ``builder-inited``, say)."""
        stock = self._stock(tmp_path)
        stock._mounts = ("stale",)  # type: ignore[attr-defined]
        stock._doc_roots = {"stale": "stale"}  # type: ignore[attr-defined]
        stock._mount_entry_docnames = {0: ["stale"]}  # type: ignore[attr-defined]

        mount = MountConfig(dir=tmp_path, mount_at="_g/m")
        new = install_mount_aware_project(stock, (mount,))

        assert new._mounts == (mount,)
        assert new._doc_roots == {}
        assert new._mount_entry_docnames == {}


class TestWiringSignature:
    """The single filter that decides which mounts can force a host re-read.

    ``_on_env_get_outdated`` walks this mapping rather than the mount list, so
    a mount that is absent from it cannot cause a re-read. That makes these
    assertions the only thing standing between a refactor and a handler that
    over-triggers, which is why they are made directly rather than only
    through a build.
    """

    @staticmethod
    def _mount(**kwargs: object) -> MountConfig:
        return MountConfig(dir=Path("/b"), **kwargs)  # type: ignore[arg-type]

    def test_mounts_without_attach_to_are_omitted(self) -> None:
        """A mount that wires nothing must not appear at all.

        If it does, its entry doc appearing or disappearing moves the
        signature, and the handler announces a re-read of a document that
        mount has no relationship with.
        """
        parsed = (
            self._mount(mount_at="_g/a", attach_to="index"),
            self._mount(mount_at="_g/b"),  # no attach_to
        )
        docnames = {0: ["_g/a/index"], 1: ["_g/b/index"]}
        signature = _wiring_signature(parsed, docnames)
        assert set(signature) == {0}, signature

    def test_value_carries_the_attach_to_target(self) -> None:
        """Re-pointing a mount at a different host doc is itself a change."""
        docnames = {0: ["_g/a/index"]}
        first = _wiring_signature(
            (self._mount(mount_at="_g/a", attach_to="index"),), docnames
        )
        second = _wiring_signature(
            (self._mount(mount_at="_g/a", attach_to="other"),), docnames
        )
        assert first != second
        assert first[0] == ("index", ("_g/a/index",))

    def test_entries_are_gated_on_what_the_mount_produced(self) -> None:
        """A mount whose entry doc does not exist wires nothing, so its
        signature entry is empty rather than optimistic."""
        parsed = (self._mount(mount_at="_g/a", attach_to="index"),)
        assert _wiring_signature(parsed, {0: []}) == {0: ("index", ())}
        assert _wiring_signature(parsed, {0: ["_g/a/other"]}) == {0: ("index", ())}

    def test_entry_doc_appearing_changes_the_signature(self) -> None:
        parsed = (self._mount(mount_at="_g/a", attach_to="index"),)
        before = _wiring_signature(parsed, {0: []})
        after = _wiring_signature(parsed, {0: ["_g/a/index"]})
        assert before != after

    def test_no_mounts_gives_an_empty_signature(self) -> None:
        assert _wiring_signature((), {}) == {}

    def test_values_are_hashable_and_comparable(self) -> None:
        """The signature is persisted on the env and compared with ``==``
        between builds, so its values must be plain immutable data — a list
        would compare fine but a mutable value invites aliasing bugs."""
        signature = _wiring_signature(
            (self._mount(mount_at="_g/a", attach_to="index"),), {0: ["_g/a/index"]}
        )
        assert hash(signature[0])
