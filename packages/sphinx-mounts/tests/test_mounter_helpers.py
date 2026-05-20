"""Unit tests for small private helpers in sphinx_mounts.mounter."""

from __future__ import annotations

from sphinx_mounts.mounter import _join_mount


class TestJoinMount:
    def test_with_prefix(self) -> None:
        assert _join_mount("_generated/api", "intro") == "_generated/api/intro"

    def test_with_nested_prefix(self) -> None:
        assert _join_mount("a/b/c", "sub/page") == "a/b/c/sub/page"

    def test_with_none_prefix_returns_tail(self) -> None:
        assert _join_mount(None, "tutorial") == "tutorial"

    def test_with_none_prefix_and_nested_tail(self) -> None:
        assert _join_mount(None, "guides/intro") == "guides/intro"
