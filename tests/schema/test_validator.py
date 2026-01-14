"""Tests for the schema validator with caching support."""

from __future__ import annotations

from sphinx_needs.schema.validator import (
    LocalValidationResult,
    NeedValidationResult,
    NetworkValidationResult,
    SchemaValidationCache,
)


class TestLocalValidationResult:
    """Tests for LocalValidationResult."""

    def test_success_true(self) -> None:
        result = LocalValidationResult(success=True, warnings=[])
        assert result.success is True
        assert result.warnings == []

    def test_success_false(self) -> None:
        result = LocalValidationResult(success=False, warnings=[])
        assert result.success is False


class TestNetworkValidationResult:
    """Tests for NetworkValidationResult."""

    def test_default_dependencies(self) -> None:
        result = NetworkValidationResult(success=True, warnings=[])
        assert result.dependencies == frozenset()

    def test_with_dependencies(self) -> None:
        deps = frozenset(["REQ_001", "REQ_002"])
        result = NetworkValidationResult(success=True, warnings=[], dependencies=deps)
        assert result.dependencies == deps


class TestNeedValidationResult:
    """Tests for NeedValidationResult."""

    def test_success_both_none(self) -> None:
        result = NeedValidationResult(local=None, network=None)
        assert result.success is True
        assert result.all_warnings == []
        assert result.dependencies == frozenset()

    def test_success_local_only_pass(self) -> None:
        local = LocalValidationResult(success=True, warnings=[])
        result = NeedValidationResult(local=local, network=None)
        assert result.success is True

    def test_success_local_only_fail(self) -> None:
        local = LocalValidationResult(success=False, warnings=[])
        result = NeedValidationResult(local=local, network=None)
        assert result.success is False

    def test_success_network_only_pass(self) -> None:
        network = NetworkValidationResult(
            success=True, warnings=[], dependencies=frozenset(["A"])
        )
        result = NeedValidationResult(local=None, network=network)
        assert result.success is True
        assert result.dependencies == frozenset(["A"])

    def test_success_network_only_fail(self) -> None:
        network = NetworkValidationResult(
            success=False, warnings=[], dependencies=frozenset()
        )
        result = NeedValidationResult(local=None, network=network)
        assert result.success is False

    def test_success_both_pass(self) -> None:
        local = LocalValidationResult(success=True, warnings=[])
        network = NetworkValidationResult(
            success=True, warnings=[], dependencies=frozenset()
        )
        result = NeedValidationResult(local=local, network=network)
        assert result.success is True

    def test_success_local_pass_network_fail(self) -> None:
        local = LocalValidationResult(success=True, warnings=[])
        network = NetworkValidationResult(
            success=False, warnings=[], dependencies=frozenset()
        )
        result = NeedValidationResult(local=local, network=network)
        assert result.success is False

    def test_success_local_fail_network_pass(self) -> None:
        local = LocalValidationResult(success=False, warnings=[])
        network = NetworkValidationResult(
            success=True, warnings=[], dependencies=frozenset()
        )
        result = NeedValidationResult(local=local, network=network)
        assert result.success is False


class TestSchemaValidationCache:
    """Tests for SchemaValidationCache."""

    def test_init(self) -> None:
        cache = SchemaValidationCache("test_schema")
        assert cache.schema_key == "test_schema"
        assert len(cache) == 0

    def test_get_missing(self) -> None:
        cache = SchemaValidationCache("test")
        assert cache.get("missing") is None

    def test_set_and_get(self) -> None:
        cache = SchemaValidationCache("test")
        result = NeedValidationResult(local=None, network=None)
        cache.store("REQ_001", result)
        assert cache.get("REQ_001") is result
        assert len(cache) == 1

    def test_set_with_dependencies(self) -> None:
        cache = SchemaValidationCache("test")
        network = NetworkValidationResult(
            success=True,
            warnings=[],
            dependencies=frozenset(["REQ_002", "REQ_003"]),
        )
        result = NeedValidationResult(local=None, network=network)
        cache.store("REQ_001", result)

        # Check reverse dependency index
        assert "REQ_001" in cache._dependents.get("REQ_002", set())
        assert "REQ_001" in cache._dependents.get("REQ_003", set())

    def test_clear(self) -> None:
        cache = SchemaValidationCache("test")
        result = NeedValidationResult(local=None, network=None)
        cache.store("REQ_001", result)
        assert len(cache) == 1
        cache.clear()
        assert len(cache) == 0

    def test_invalidate_single(self) -> None:
        cache = SchemaValidationCache("test")
        result = NeedValidationResult(local=None, network=None)
        cache.store("REQ_001", result)
        cache.store("REQ_002", result)

        invalidated = cache.invalidate({"REQ_001"})

        assert "REQ_001" in invalidated
        assert cache.get("REQ_001") is None
        assert cache.get("REQ_002") is result  # unaffected

    def test_invalidate_with_dependents(self) -> None:
        """Test that invalidating a need also invalidates needs that depend on it."""
        cache = SchemaValidationCache("test")

        # REQ_001 has no dependencies
        result1 = NeedValidationResult(local=None, network=None)
        cache.store("REQ_001", result1)

        # REQ_002 depends on REQ_001
        network2 = NetworkValidationResult(
            success=True,
            warnings=[],
            dependencies=frozenset(["REQ_001"]),
        )
        result2 = NeedValidationResult(local=None, network=network2)
        cache.store("REQ_002", result2)

        # REQ_003 depends on REQ_002
        network3 = NetworkValidationResult(
            success=True,
            warnings=[],
            dependencies=frozenset(["REQ_002"]),
        )
        result3 = NeedValidationResult(local=None, network=network3)
        cache.store("REQ_003", result3)

        # Invalidating REQ_001 should cascade to REQ_002 and REQ_003
        invalidated = cache.invalidate({"REQ_001"})

        assert "REQ_001" in invalidated
        assert "REQ_002" in invalidated
        assert "REQ_003" in invalidated
        assert len(cache) == 0

    def test_invalidate_independent_needs(self) -> None:
        """Test that invalidation doesn't affect independent needs."""
        cache = SchemaValidationCache("test")

        # Two independent needs
        result1 = NeedValidationResult(local=None, network=None)
        result2 = NeedValidationResult(local=None, network=None)
        cache.store("REQ_001", result1)
        cache.store("REQ_002", result2)

        # Invalidate only REQ_001
        invalidated = cache.invalidate({"REQ_001"})

        assert invalidated == {"REQ_001"}
        assert cache.get("REQ_001") is None
        assert cache.get("REQ_002") is result2

    def test_invalidate_already_removed(self) -> None:
        """Test invalidating a need that's not in the cache."""
        cache = SchemaValidationCache("test")
        result = NeedValidationResult(local=None, network=None)
        cache.store("REQ_001", result)

        invalidated = cache.invalidate({"REQ_999"})

        assert "REQ_999" in invalidated
        assert cache.get("REQ_001") is result  # unaffected

    def test_invalidate_diamond_dependency(self) -> None:
        """Test invalidation with diamond dependency pattern.

        REQ_001
         /    \\
        v      v
    REQ_002  REQ_003
         \\    /
          v  v
        REQ_004
        """
        cache = SchemaValidationCache("test")

        # REQ_001 has no dependencies
        result1 = NeedValidationResult(local=None, network=None)
        cache.store("REQ_001", result1)

        # REQ_002 and REQ_003 both depend on REQ_001
        network2 = NetworkValidationResult(
            success=True,
            warnings=[],
            dependencies=frozenset(["REQ_001"]),
        )
        result2 = NeedValidationResult(local=None, network=network2)
        cache.store("REQ_002", result2)

        network3 = NetworkValidationResult(
            success=True,
            warnings=[],
            dependencies=frozenset(["REQ_001"]),
        )
        result3 = NeedValidationResult(local=None, network=network3)
        cache.store("REQ_003", result3)

        # REQ_004 depends on both REQ_002 and REQ_003
        network4 = NetworkValidationResult(
            success=True,
            warnings=[],
            dependencies=frozenset(["REQ_002", "REQ_003"]),
        )
        result4 = NeedValidationResult(local=None, network=network4)
        cache.store("REQ_004", result4)

        # Invalidating REQ_001 should cascade to all
        invalidated = cache.invalidate({"REQ_001"})

        assert invalidated == {"REQ_001", "REQ_002", "REQ_003", "REQ_004"}
        assert len(cache) == 0
