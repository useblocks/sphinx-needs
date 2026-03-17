# PR: Parse link conditions from imported and external needs

## Summary

`NeedLink.from_string` now parses condition syntax (e.g. `"REQ_001[status==\"open\"]"`) from link strings, so that needs loaded via `needimport` or `needs_external_needs` can carry conditional links — previously only directive option parsing supported this.

## Changes

### Core: `NeedLink` (`sphinx_needs/need_item.py`)

- **`from_string`** — now delegates to `from_string_with_warnings`, which performs bracket-depth condition parsing (matching the logic previously only in `_parse_link_with_condition`).
- **`from_string_with_warnings`** — new static method returning `tuple[NeedLink, list[str]]`. Infallible best-effort parse with structured warnings for unclosed brackets or trailing text.
- **`_parse_address`** — extracted helper for splitting `ID.part` addresses.
- **`to_link_string`** — serializes a `NeedLink` back to string *including* the condition. Computes bracket depth as one more than the longest consecutive `]` run in the condition, ensuring safe round-tripping for any condition content.
- **`to_filter_string`** — unchanged (no condition, used for filter expressions and JSON output).

### Schema: `_split_link_list` (`sphinx_needs/needs_schema.py`)

- **`_parse_link_with_condition`** removed — its 3-line body (delegate to `NeedLink.from_string_with_warnings`) is now inlined into `_flush_current()` inside `_split_link_list`.

### Import prefix fix (`sphinx_needs/utils.py`)

- **`import_prefix_link_edit`** — previously compared raw link strings with `id == link`, which broke with conditioned links. Now parses each link via `NeedLink.from_string`, compares `.id`, and reconstructs with `to_link_string()` to preserve conditions through the prefixing process.

### Documentation

- **`docs/directives/need.rst`** — note in the "conditional links" section about JSON support via import/external.
- **`docs/directives/needimport.rst`** — note cross-referencing `need_conditional_links`.
- **`docs/configuration.rst`** — note in the `needs_external_needs` section.

### Tests

- **`tests/test_need_item_api.py`** — 23 unit tests across `TestNeedLinkFromString` (11) and `TestNeedLinkToLinkString` (12), covering plain IDs, parts, conditions, bracket escaping, malformed input, and round-trip serialization.
- **`tests/test_link_conditions.py`** — integration test extended to verify warnings from imported needs (`needimport` with `needs_test_conditions.json`) and external needs (`needs_external_needs` with `needs_test_external.json`).
- **New fixtures**: `needs_test_conditions.json`, `needs_test_external.json` — JSON files with conditioned links for import/external testing.

## Test results

824 passed, 11 skipped. mypy and ruff clean.
