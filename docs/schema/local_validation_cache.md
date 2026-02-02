# Local Validation Caching System

This document explains the local validation caching system implemented in `sphinx_needs/schema/core.py` to optimize schema validation performance.

## Overview

The caching system avoids redundant JSON schema validation when the same need is validated against the same schema multiple times. This is common in network validation where linked needs are traversed repeatedly from different starting points.

## Problem Statement

In network validation, the same need can be validated multiple times:

```
Need REQ_002 links to REQ_001
Need REQ_003 links to REQ_001
                                         
         ┌────────┐     links     ┌────────┐
         │REQ_002 │──────────────►│REQ_001 │
         └────────┘               └────────┘
                                       ▲
         ┌────────┐     links          │
         │REQ_003 │────────────────────┘
         └────────┘

Validation order (without cache):
1. Validate REQ_002
   └── Network: validate REQ_001 (expensive!)
   
2. Validate REQ_003  
   └── Network: validate REQ_001 (same validation repeated!)
```

## Solution: Higher-Level Caching

Rather than restructuring the recursive algorithm (which would change warning attribution), we cache at a higher level: the raw validation results before context-dependent data is added.

## Data Structures

### CachedLocalResult

Stores the raw validation outcome without context-dependent data:

```python
@dataclass(slots=True)
class CachedLocalResult:
    reduced_need: dict[str, Any]     # The reduced need that was validated
    errors: tuple[ValidationError, ...]  # Validation errors (empty if passed)
    schema_error: str | None = None  # Schema compilation error, if any

    @property
    def success(self) -> bool:
        return not self.errors and self.schema_error is None
```

### LocalValidationCache

A cache keyed by `(need_id, schema_key)`:

```python
@dataclass(slots=True)
class LocalValidationCache:
    _cache: dict[tuple[str, tuple[str, ...]], CachedLocalResult]

    def get(self, need_id: str, schema_key: tuple[str, ...]) -> CachedLocalResult | None
    def store(self, need_id: str, schema_key: tuple[str, ...], result: CachedLocalResult) -> None
    def invalidate(self, need_id: str) -> None  # Remove all entries for a need
    def clear(self) -> None
```

## Cache Key Structure

```
schema_key = tuple of schema path components

Examples:
  ("requirement_schema", "local")
  ("requirement_schema", "validate", "network", "implements", "items", "local")
  ("specification_schema", "local")
  
Combined with need_id for full cache key:
  ("REQ_001", ("requirement_schema", "local"))
  ("REQ_001", ("requirement_schema", "validate", "network", ...))
```

## Validation Flow

### Without Cache

```
validate_type_schema(needs, schema)
        │
        ▼
  ┌───────────────┐
  │ For each need │
  └───────────────┘
        │
        ▼
recurse_validate_schemas(need, ...)
        │
        ├──► LOCAL: get_ontology_warnings()
        │         │
        │         ▼
        │    ┌─────────────────────────┐
        │    │ 1. reduce_need()        │  ◄── Expensive
        │    │ 2. validator.validate() │  ◄── Expensive  
        │    │ 3. Build warnings       │
        │    └─────────────────────────┘
        │
        └──► NETWORK: For each link_type
                    │
                    ▼
              For each target_need_id
                    │
                    ▼
              recurse_validate_schemas(target_need, ...)  ◄── Same need may be
                    │                                         validated multiple
                    ▼                                         times!
              (repeat LOCAL + NETWORK)
```

### With Cache

```
validate_type_schema(needs, schema)
        │
        ▼
  ┌─────────────────────────────┐
  │ Create LocalValidationCache │
  │ Create validator_cache      │
  └─────────────────────────────┘
        │
        ▼
  ┌───────────────┐
  │ For each need │
  └───────────────┘
        │
        ▼
recurse_validate_schemas(need, ..., local_cache)
        │
        ├──► LOCAL validation:
        │         │
        │         ▼
        │    ┌──────────────────────────────────┐
        │    │ cache_key = (schema_path, "local")│
        │    │ cached = local_cache.get(         │
        │    │            need_id, cache_key)    │
        │    └──────────────────────────────────┘
        │              │
        │       ┌──────┴──────┐
        │       │             │
        │       ▼             ▼
        │    CACHE HIT     CACHE MISS
        │       │             │
        │       ▼             ▼
        │    ┌────────┐   ┌─────────────────────┐
        │    │Rebuild │   │ 1. reduce_need()    │
        │    │warnings│   │ 2. validate()       │
        │    │from    │   │ 3. Cache result     │
        │    │cached  │   │ 4. Build warnings   │
        │    │result  │   └─────────────────────┘
        │    └────────┘
        │
        └──► NETWORK: (unchanged, passes local_cache down)
```

## What Gets Cached vs. Rebuilt

### Cached (Context-Independent)

| Field | Description |
|-------|-------------|
| `reduced_need` | The need dict after field reduction |
| `errors` | Tuple of `ValidationError` objects |
| `schema_error` | Schema compilation error message |

### Rebuilt (Context-Dependent)

| Field | Description |
|-------|-------------|
| `need_path` | Path like `["REQ_002", "implements", "REQ_001"]` |
| `schema_path` | Path like `["my_schema", "local", "properties"]` |
| `user_message` | Only at `recurse_level == 0` |
| `user_severity` | Only at `recurse_level == 0` |
| `rule` | `local_fail` vs `network_local_fail` |

This separation is key: the expensive validation is cached, but warnings are rebuilt with the correct context for each call site.

## Invalidation for Incremental Updates

When a need is modified, its cached entries can be invalidated:

```
Before modification:
┌─────────────────────────────────────────┐
│ Cache entries:                          │
│   (REQ_001, schema_A) → result1         │
│   (REQ_001, schema_B) → result2         │
│   (REQ_002, schema_A) → result3         │
│   (REQ_003, schema_A) → result4         │
└─────────────────────────────────────────┘

After local_cache.invalidate("REQ_001"):
┌─────────────────────────────────────────┐
│ Cache entries:                          │
│   (REQ_002, schema_A) → result3    ✓    │
│   (REQ_003, schema_A) → result4    ✓    │
└─────────────────────────────────────────┘
```

## Code Changes

### Modified Files

#### `sphinx_needs/schema/core.py`

1. **Added imports:**
   ```python
   from dataclasses import dataclass, field as dataclass_field
   ```

2. **Added `CachedLocalResult` dataclass** (after line 35):
   - Stores validation results without context
   - Has `success` property

3. **Added `LocalValidationCache` dataclass:**
   - `get()` - Retrieve cached result
   - `store()` - Store a validation result  
   - `invalidate()` - Remove all entries for a need
   - `clear()` - Clear entire cache
   - `__len__()` - Return cache size

4. **Modified `validate_type_schema()`:**
   - Creates `LocalValidationCache` instance
   - Passes `local_cache` to `recurse_validate_schemas()`

5. **Modified `recurse_validate_schemas()`:**
   - Added `local_cache: LocalValidationCache` parameter
   - Checks cache before validating
   - Uses `_construct_warnings_from_cache()` on cache hit
   - Passes `local_cache` and `cache_key` to `get_ontology_warnings()` on cache miss

6. **Added `_construct_warnings_from_cache()` function:**
   - Rebuilds `OntologyWarning` objects from cached results
   - Applies current context (need_path, schema_path, user_message, user_severity)

7. **Modified `get_ontology_warnings()`:**
   - Added optional `local_cache` and `cache_key` parameters
   - Stores results in cache when parameters are provided

### New Test Files

#### `tests/schema/test_core_cache.py`

Unit tests for the caching classes:

- `TestCachedLocalResult` - Tests for the result dataclass
- `TestLocalValidationCache` - Tests for cache operations including:
  - Basic get/store
  - Different schema keys for same need
  - Different needs with same schema
  - Invalidation
  - Clear
  - Overwrite

## Usage Example

```python
from sphinx_needs.schema.core import LocalValidationCache, validate_type_schema

# The cache is created and used automatically within validate_type_schema
# No changes needed to calling code

# For incremental updates (future use):
cache = LocalValidationCache()
# ... validation happens ...

# When a need is modified:
cache.invalidate("REQ_001")  # Clear cached results for this need

# Re-validate only affected needs
```

## Performance Impact

The caching is most effective when:

1. **Many needs link to the same targets** - Each target is validated once instead of N times
2. **Deep network validation** - Reduces exponential re-validation
3. **Multiple schemas validate the same needs** - Each (need, schema) pair is cached separately

The cache has minimal overhead:
- Cache lookup is O(1) dict access
- Stored data is already computed (no copies needed)
- Memory usage scales with unique (need_id, schema_key) pairs
