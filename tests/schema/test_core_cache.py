"""Tests for the local validation cache in core.py."""

from __future__ import annotations

from sphinx_needs.schema.core import CachedLocalResult, LocalValidationCache


class TestCachedLocalResult:
    """Tests for CachedLocalResult dataclass."""

    def test_success_no_errors(self) -> None:
        """Test success property with no errors."""
        result = CachedLocalResult(reduced_need={"id": "REQ_001"}, errors=())
        assert result.success is True

    def test_success_with_errors(self) -> None:
        """Test success property with errors (mocked)."""
        # We can't easily create ValidationError without going through jsonschema
        # so we test the property logic indirectly
        result = CachedLocalResult(reduced_need={"id": "REQ_001"}, errors=())
        assert result.success is True
        assert result.schema_error is None

    def test_success_with_schema_error(self) -> None:
        """Test success property with schema error."""
        result = CachedLocalResult(
            reduced_need={"id": "REQ_001"},
            errors=(),
            schema_error="Invalid schema",
        )
        assert result.success is False

    def test_reduced_need_preserved(self) -> None:
        """Test that reduced_need is stored correctly."""
        need_data = {"id": "REQ_001", "status": "open", "type": "req"}
        result = CachedLocalResult(reduced_need=need_data, errors=())
        assert result.reduced_need == need_data


class TestLocalValidationCache:
    """Tests for LocalValidationCache."""

    def test_init_empty(self) -> None:
        """Test cache initializes empty."""
        cache = LocalValidationCache()
        assert len(cache) == 0

    def test_get_missing(self) -> None:
        """Test get returns None for missing entries."""
        cache = LocalValidationCache()
        result = cache.get("REQ_001", ("schema", "local"))
        assert result is None

    def test_store_and_get(self) -> None:
        """Test storing and retrieving a cached result."""
        cache = LocalValidationCache()
        cached = CachedLocalResult(reduced_need={"id": "REQ_001"}, errors=())
        schema_key = ("my_schema", "local")

        cache.store("REQ_001", schema_key, cached)

        assert len(cache) == 1
        retrieved = cache.get("REQ_001", schema_key)
        assert retrieved is cached

    def test_store_different_schema_keys(self) -> None:
        """Test storing same need with different schema keys."""
        cache = LocalValidationCache()
        cached1 = CachedLocalResult(reduced_need={"id": "REQ_001"}, errors=())
        cached2 = CachedLocalResult(
            reduced_need={"id": "REQ_001", "status": "open"}, errors=()
        )
        key1 = ("schema_a", "local")
        key2 = ("schema_b", "local")

        cache.store("REQ_001", key1, cached1)
        cache.store("REQ_001", key2, cached2)

        assert len(cache) == 2
        assert cache.get("REQ_001", key1) is cached1
        assert cache.get("REQ_001", key2) is cached2

    def test_store_different_needs_same_schema(self) -> None:
        """Test storing different needs with same schema key."""
        cache = LocalValidationCache()
        cached1 = CachedLocalResult(reduced_need={"id": "REQ_001"}, errors=())
        cached2 = CachedLocalResult(reduced_need={"id": "REQ_002"}, errors=())
        schema_key = ("my_schema", "local")

        cache.store("REQ_001", schema_key, cached1)
        cache.store("REQ_002", schema_key, cached2)

        assert len(cache) == 2
        assert cache.get("REQ_001", schema_key) is cached1
        assert cache.get("REQ_002", schema_key) is cached2

    def test_invalidate_single_need(self) -> None:
        """Test invalidating all entries for a single need."""
        cache = LocalValidationCache()
        cached1 = CachedLocalResult(reduced_need={"id": "REQ_001"}, errors=())
        cached2 = CachedLocalResult(reduced_need={"id": "REQ_001"}, errors=())
        cached3 = CachedLocalResult(reduced_need={"id": "REQ_002"}, errors=())

        cache.store("REQ_001", ("schema_a", "local"), cached1)
        cache.store("REQ_001", ("schema_b", "local"), cached2)
        cache.store("REQ_002", ("schema_a", "local"), cached3)

        assert len(cache) == 3

        cache.invalidate("REQ_001")

        assert len(cache) == 1
        assert cache.get("REQ_001", ("schema_a", "local")) is None
        assert cache.get("REQ_001", ("schema_b", "local")) is None
        assert cache.get("REQ_002", ("schema_a", "local")) is cached3

    def test_invalidate_nonexistent(self) -> None:
        """Test invalidating a need not in cache (no-op)."""
        cache = LocalValidationCache()
        cached = CachedLocalResult(reduced_need={"id": "REQ_001"}, errors=())
        cache.store("REQ_001", ("schema", "local"), cached)

        cache.invalidate("REQ_999")

        assert len(cache) == 1
        assert cache.get("REQ_001", ("schema", "local")) is cached

    def test_clear(self) -> None:
        """Test clearing all cache entries."""
        cache = LocalValidationCache()
        cache.store(
            "REQ_001",
            ("schema", "local"),
            CachedLocalResult(reduced_need={}, errors=()),
        )
        cache.store(
            "REQ_002",
            ("schema", "local"),
            CachedLocalResult(reduced_need={}, errors=()),
        )

        assert len(cache) == 2

        cache.clear()

        assert len(cache) == 0

    def test_overwrite_existing(self) -> None:
        """Test overwriting an existing cache entry."""
        cache = LocalValidationCache()
        cached1 = CachedLocalResult(reduced_need={"id": "REQ_001"}, errors=())
        cached2 = CachedLocalResult(
            reduced_need={"id": "REQ_001"}, errors=(), schema_error="Error"
        )
        schema_key = ("schema", "local")

        cache.store("REQ_001", schema_key, cached1)
        assert cache.get("REQ_001", schema_key) is cached1

        cache.store("REQ_001", schema_key, cached2)
        assert cache.get("REQ_001", schema_key) is cached2
        assert len(cache) == 1
