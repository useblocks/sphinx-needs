"""Type schema validation with caching support.

This module provides a cache-friendly implementation of schema validation
that supports incremental validation based on a set of modified needs.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from sphinx_needs.schema.config import (
    MAP_RULE_DEFAULT_SEVERITY,
    MAX_NESTED_NETWORK_VALIDATION_LEVELS,
    MessageRuleEnum,
    NeedFieldsSchemaType,
    ResolvedLinkSchemaType,
    SchemasRootType,
    SeverityEnum,
    ValidateSchemaType,
    get_schema_name,
)
from sphinx_needs.schema.core import (
    NeedFieldProperties,
    SchemaValidator,
    any_not_of_rule,
    compile_validator,
    get_ontology_warnings,
    get_severity,
)
from sphinx_needs.schema.reporting import OntologyWarning, save_debug_files

if TYPE_CHECKING:
    from sphinx_needs.config import NeedsSphinxConfig
    from sphinx_needs.need_item import NeedItem
    from sphinx_needs.views import NeedsView


@dataclass(slots=True)
class LocalValidationResult:
    """Result of validating a need's local schema (no network traversal)."""

    success: bool
    warnings: list[OntologyWarning]


@dataclass(slots=True)
class NetworkValidationResult:
    """Result of validating a need's network links."""

    success: bool
    warnings: list[OntologyWarning]
    dependencies: frozenset[str] = field(default_factory=frozenset)
    """Need IDs this result depends on (for cache invalidation)."""


@dataclass(slots=True)
class NeedValidationResult:
    """Combined validation result for a need."""

    local: LocalValidationResult | None
    network: NetworkValidationResult | None

    @property
    def success(self) -> bool:
        """Check if both local and network validation succeeded."""
        local_ok = self.local is None or self.local.success
        network_ok = self.network is None or self.network.success
        return local_ok and network_ok

    @property
    def all_warnings(self) -> list[OntologyWarning]:
        """Get all warnings from both local and network validation."""
        warnings: list[OntologyWarning] = []
        if self.local:
            warnings.extend(self.local.warnings)
        if self.network:
            warnings.extend(self.network.warnings)
        return warnings

    @property
    def dependencies(self) -> frozenset[str]:
        """Get all need IDs this result depends on."""
        if self.network:
            return self.network.dependencies
        return frozenset()


class SchemaValidationCache:
    """Cache for schema validation results with dependency tracking.

    Supports incremental validation by tracking which needs depend on which
    other needs through network links.
    """

    __slots__ = ("_dependents", "_results", "schema_key")

    def __init__(self, schema_key: str) -> None:
        """Initialize the cache.

        :param schema_key: Unique identifier for this schema's cache.
        """
        self.schema_key = schema_key
        self._results: dict[str, NeedValidationResult] = {}
        """Mapping of need_id to validation result."""
        self._dependents: dict[str, set[str]] = {}
        """Reverse index: need_id -> set of need_ids whose validation depends on it."""

    def get(self, need_id: str) -> NeedValidationResult | None:
        """Get cached validation result for a need.

        :param need_id: The need ID to look up.
        :return: The cached result, or None if not cached.
        """
        return self._results.get(need_id)

    def store(self, need_id: str, result: NeedValidationResult) -> None:
        """Store a validation result in the cache.

        :param need_id: The need ID to cache.
        :param result: The validation result to store.
        """
        # Update reverse dependency index
        for dep_id in result.dependencies:
            if dep_id not in self._dependents:
                self._dependents[dep_id] = set()
            self._dependents[dep_id].add(need_id)
        self._results[need_id] = result

    def invalidate(self, modified_need_ids: Set[str]) -> set[str]:
        """Invalidate cache entries for modified needs and their dependents.

        :param modified_need_ids: IDs of needs that have been modified.
        :return: The set of all invalidated need IDs.
        """
        invalidated: set[str] = set()
        queue = list(modified_need_ids)

        while queue:
            need_id = queue.pop()
            if need_id in invalidated:
                continue
            invalidated.add(need_id)

            # Remove from cache
            if need_id in self._results:
                # Clean up reverse dependencies
                for dep_id in self._results[need_id].dependencies:
                    if dep_id in self._dependents:
                        self._dependents[dep_id].discard(need_id)
                del self._results[need_id]

            # Queue dependents for invalidation (needs that link TO this need)
            for dependent_id in self._dependents.get(need_id, set()):
                if dependent_id not in invalidated:
                    queue.append(dependent_id)

        return invalidated

    def clear(self) -> None:
        """Clear all cached results."""
        self._results.clear()
        self._dependents.clear()

    def __len__(self) -> int:
        """Return the number of cached results."""
        return len(self._results)


@dataclass
class _NetworkTask:
    """A task for iterative network validation."""

    need: NeedItem
    schema: dict[str, ResolvedLinkSchemaType]
    schema_path: list[str]
    need_path: list[str]
    depth: int


class TypeSchemaValidator:
    """Validator for a specific type schema with caching support.

    This class encapsulates the validation logic for a single type schema
    and provides methods for both full and incremental validation.

    Usage::

        validator = TypeSchemaValidator(config, schema, field_properties)

        # Initial full validation
        results = validator.validate_all(needs)

        # After some needs are modified
        results = validator.validate_incremental(needs, modified_need_ids)
    """

    __slots__ = (
        "_cache",
        "_local_validator",
        "_network_schema",
        "_network_validator_cache",
        "_select_validator",
        "_user_message",
        "_user_severity",
        "config",
        "field_properties",
        "schema",
        "schema_name",
    )

    def __init__(
        self,
        config: NeedsSphinxConfig,
        schema: SchemasRootType,
        field_properties: Mapping[str, NeedFieldProperties],
    ) -> None:
        """Initialize the validator.

        :param config: The sphinx-needs configuration.
        :param schema: The type schema to validate against.
        :param field_properties: Properties of need fields for validation.
        """
        self.config = config
        self.schema = schema
        self.field_properties = field_properties
        self.schema_name = get_schema_name(schema)

        # Compile validators once
        self._select_validator: SchemaValidator | None = None
        if schema.get("select"):
            self._select_validator = compile_validator(
                cast(NeedFieldsSchemaType, schema["select"])
            )

        self._local_validator: SchemaValidator | None = None
        validate_schema = schema.get("validate", {})
        if "local" in validate_schema:
            self._local_validator = compile_validator(
                cast(NeedFieldsSchemaType, validate_schema["local"])
            )

        self._network_schema: dict[str, ResolvedLinkSchemaType] = validate_schema.get(
            "network", {}
        )
        self._user_severity: SeverityEnum | None = (
            SeverityEnum[schema["severity"]] if "severity" in schema else None
        )
        self._user_message: str | None = schema.get("message")

        # Cache for validation results
        self._cache = SchemaValidationCache(self.schema_name)

        # Cache for compiled network validators (keyed by schema path)
        self._network_validator_cache: dict[tuple[str, ...], SchemaValidator] = {}

    def validate_all(
        self,
        needs: NeedsView,
    ) -> dict[str, list[OntologyWarning]]:
        """Validate all needs from scratch.

        :param needs: All needs to validate.
        :return: Mapping of need IDs to their validation warnings.
        """
        self._cache.clear()
        return self._validate_needs(needs, set(needs.keys()))

    def validate_incremental(
        self,
        needs: NeedsView,
        modified_need_ids: Set[str],
    ) -> dict[str, list[OntologyWarning]]:
        """Incrementally validate only affected needs.

        :param needs: All needs (including unmodified ones for reference).
        :param modified_need_ids: IDs of needs that have been modified.
        :return: Warnings for all needs (cached + newly validated).
        """
        # Invalidate modified needs and their dependents
        needs_to_validate: set[str] = self._cache.invalidate(modified_need_ids)

        # Also need to validate any new needs not in cache
        for need_id in needs:
            if self._cache.get(need_id) is None:
                needs_to_validate.add(need_id)

        # Validate only the affected needs
        self._validate_needs(needs, needs_to_validate)

        # Return all warnings (from cache)
        return self._collect_all_warnings()

    def _validate_needs(
        self,
        needs: NeedsView,
        need_ids_to_validate: Set[str],
    ) -> dict[str, list[OntologyWarning]]:
        """Validate a set of needs and cache results.

        :param needs: All needs (for reference during network validation).
        :param need_ids_to_validate: IDs of needs to validate.
        :return: Mapping of need IDs to their validation warnings.
        """
        # Phase 1: Validate local schemas for all needs (independent, parallelizable)
        local_results: dict[str, LocalValidationResult] = {}
        for need_id in need_ids_to_validate:
            if need_id not in needs:
                continue  # Need was deleted
            need = needs[need_id]

            # Check selection filter first
            if not self._need_matches_select(need):
                continue

            local_results[need_id] = self._validate_local(need)

        # Phase 2: Validate network schemas (depends on linked needs)
        for need_id, local_result in local_results.items():
            need = needs[need_id]
            network_result = self._validate_network(
                need, needs, max_depth=MAX_NESTED_NETWORK_VALIDATION_LEVELS
            )

            self._cache.store(
                need_id,
                NeedValidationResult(local=local_result, network=network_result),
            )

        return self._collect_all_warnings()

    def _need_matches_select(self, need: NeedItem) -> bool:
        """Check if need matches the selection filter.

        :param need: The need to check.
        :return: True if the need matches (or no filter exists).
        """
        if self._select_validator is None:
            return True

        warnings = get_ontology_warnings(
            need,
            self.field_properties,
            self._select_validator,
            fail_rule=MessageRuleEnum.select_fail,
            success_rule=MessageRuleEnum.select_success,
            schema_path=[self.schema_name, "select"],
            need_path=[need["id"]],
        )
        save_debug_files(self.config, warnings)
        return not any_not_of_rule(warnings, MessageRuleEnum.select_success)

    def _validate_local(self, need: NeedItem) -> LocalValidationResult:
        """Validate a need's local schema only.

        :param need: The need to validate.
        :return: The local validation result.
        """
        if self._local_validator is None:
            return LocalValidationResult(success=True, warnings=[])

        warnings = get_ontology_warnings(
            need,
            self.field_properties,
            self._local_validator,
            fail_rule=MessageRuleEnum.local_fail,
            success_rule=MessageRuleEnum.local_success,
            schema_path=[self.schema_name, "local"],
            need_path=[need["id"]],
            user_message=self._user_message,
            user_severity=self._user_severity,
        )
        save_debug_files(self.config, warnings)

        success = not any_not_of_rule(warnings, MessageRuleEnum.local_success)
        return LocalValidationResult(success=success, warnings=warnings)

    def _validate_network(
        self,
        need: NeedItem,
        needs: NeedsView,
        max_depth: int,
    ) -> NetworkValidationResult:
        """Validate a need's network links using iterative BFS.

        :param need: The root need to validate.
        :param needs: All needs for link resolution.
        :param max_depth: Maximum recursion depth.
        :return: The network validation result with tracked dependencies.
        """
        if not self._network_schema:
            return NetworkValidationResult(
                success=True, warnings=[], dependencies=frozenset()
            )

        warnings: list[OntologyWarning] = []
        dependencies: set[str] = set()
        overall_success = True

        # Use a work queue instead of recursion
        task_queue: list[_NetworkTask] = [
            _NetworkTask(
                need=need,
                schema=self._network_schema,
                schema_path=[self.schema_name, "validate", "network"],
                need_path=[need["id"]],
                depth=0,
            )
        ]

        # Process tasks iteratively (BFS style)
        while task_queue:
            current_tasks = task_queue[:]
            task_queue.clear()

            for task in current_tasks:
                if task.depth > max_depth:
                    # Max depth exceeded
                    rule = MessageRuleEnum.network_max_nest_level
                    warning: OntologyWarning = {
                        "rule": rule,
                        "severity": MAP_RULE_DEFAULT_SEVERITY[rule],
                        "validation_message": (
                            f"Maximum network validation recursion level "
                            f"{max_depth} reached."
                        ),
                        "need": task.need,
                        "schema_path": task.schema_path,
                        "need_path": task.need_path,
                    }
                    if task.depth == 0 and self._user_message is not None:
                        warning["user_message"] = self._user_message
                    warnings.append(warning)
                    overall_success = False
                    continue

                # Process each link type in the network schema
                task_success, task_warnings, task_deps, new_tasks = (
                    self._process_network_task(task, needs, max_depth)
                )
                warnings.extend(task_warnings)
                dependencies.update(task_deps)
                task_queue.extend(new_tasks)
                if not task_success:
                    overall_success = False

        return NetworkValidationResult(
            success=overall_success,
            warnings=warnings,
            dependencies=frozenset(dependencies),
        )

    def _process_network_task(
        self,
        task: _NetworkTask,
        needs: NeedsView,
        max_depth: int,
    ) -> tuple[bool, list[OntologyWarning], set[str], list[_NetworkTask]]:
        """Process a single network validation task.

        :param task: The task to process.
        :param needs: All needs for link resolution.
        :param max_depth: Maximum recursion depth.
        :return: Tuple of (success, warnings, dependencies, new_tasks).
        """
        warnings: list[OntologyWarning] = []
        dependencies: set[str] = set()
        new_tasks: list[_NetworkTask] = []
        overall_success = True

        for link_type, link_schema in task.schema.items():
            items_results: list[tuple[str, bool, list[OntologyWarning]]] = []
            contains_results: list[tuple[str, bool, list[OntologyWarning]]] = []

            # Get link values from the need
            link_values = task.need.get(link_type, [])
            if not isinstance(link_values, list):
                link_values = []

            for target_need_id in link_values:
                dependencies.add(target_need_id)

                try:
                    target_need = needs[target_need_id]
                except KeyError:
                    # Broken link
                    rule = MessageRuleEnum.network_missing_target
                    warning: OntologyWarning = {
                        "rule": rule,
                        "severity": get_severity(rule, self._user_severity),
                        "validation_message": (
                            f"Broken link of type '{link_type}' to '{target_need_id}'"
                        ),
                        "need": task.need,
                        "schema_path": [*task.schema_path, link_type],
                        "need_path": [*task.need_path, link_type],
                    }
                    if task.depth == 0 and self._user_message is not None:
                        warning["user_message"] = self._user_message
                    warnings.append(warning)
                    continue

                need_path_link = [*task.need_path, link_type, target_need_id]

                # Validate target's local schema if specified in items/contains
                for val_type in ("items", "contains"):
                    if val_type not in link_schema:
                        continue

                    val_schema: ValidateSchemaType = link_schema[val_type]
                    target_warnings: list[OntologyWarning] = []
                    target_success = True

                    # Validate local if present
                    if "local" in val_schema:
                        schema_path_local = [
                            *task.schema_path,
                            link_type,
                            val_type,
                            "local",
                        ]
                        cache_key = tuple(schema_path_local)
                        if cache_key not in self._network_validator_cache:
                            self._network_validator_cache[cache_key] = (
                                compile_validator(
                                    cast(NeedFieldsSchemaType, val_schema["local"])
                                )
                            )
                        validator = self._network_validator_cache[cache_key]

                        local_warnings = get_ontology_warnings(
                            target_need,
                            self.field_properties,
                            validator,
                            fail_rule=MessageRuleEnum.network_local_fail,
                            success_rule=MessageRuleEnum.network_local_success,
                            schema_path=schema_path_local,
                            need_path=need_path_link,
                        )
                        save_debug_files(self.config, local_warnings)
                        target_warnings.extend(local_warnings)
                        if any_not_of_rule(
                            local_warnings, MessageRuleEnum.network_local_success
                        ):
                            target_success = False

                    # Queue nested network validation if present
                    if "network" in val_schema and task.depth < max_depth:
                        network_schema = val_schema["network"]
                        new_tasks.append(
                            _NetworkTask(
                                need=target_need,
                                schema=network_schema,
                                schema_path=[
                                    *task.schema_path,
                                    link_type,
                                    val_type,
                                    "validate",
                                    "network",
                                ],
                                need_path=need_path_link,
                                depth=task.depth + 1,
                            )
                        )

                    if val_type == "items":
                        items_results.append(
                            (target_need_id, target_success, target_warnings)
                        )
                    else:
                        contains_results.append(
                            (target_need_id, target_success, target_warnings)
                        )

            # Aggregate items results (all must pass)
            if link_schema.get("items"):
                failed = [(tid, tw) for tid, ts, tw in items_results if not ts]
                if failed:
                    overall_success = False
                    failed_ids = [tid for tid, _ in failed]
                    ok_ids = [tid for tid, ts, _ in items_results if ts]
                    rule = MessageRuleEnum.network_items_fail
                    msg = (
                        f"Items validation failed for links of type '{link_type}' "
                        f"to {', '.join(failed_ids)}"
                    )
                    if ok_ids:
                        msg += f" / ok: {', '.join(ok_ids)}"
                    if failed_ids:
                        msg += f" / nok: {', '.join(failed_ids)}"

                    items_nok_warnings: list[OntologyWarning] = [
                        w for _, tw in failed for w in tw
                    ]
                    items_warning: OntologyWarning = {
                        "rule": rule,
                        "severity": get_severity(rule, self._user_severity),
                        "validation_message": msg,
                        "need": task.need,
                        "schema_path": [*task.schema_path, link_type, "items"],
                        "need_path": [*task.need_path, link_type],
                        "children": items_nok_warnings,
                    }
                    if task.depth == 0 and self._user_message is not None:
                        items_warning["user_message"] = self._user_message
                    warnings.extend(items_nok_warnings)

            # Aggregate contains results (minContains/maxContains)
            if link_schema.get("contains"):
                ok_count = sum(1 for _, ts, _ in contains_results if ts)
                nok_count = sum(1 for _, ts, _ in contains_results if not ts)
                ok_ids = [tid for tid, ts, _ in contains_results if ts]
                nok_ids = [tid for tid, ts, _ in contains_results if not ts]

                min_contains = link_schema.get("minContains", 1)
                max_contains = link_schema.get("maxContains")

                if ok_count < min_contains:
                    overall_success = False
                    rule = MessageRuleEnum.network_contains_too_few
                    msg = (
                        f"Too few valid links of type '{link_type}' "
                        f"({ok_count} < {min_contains})"
                    )
                    if ok_count > 0:
                        msg += f" / ok: {', '.join(ok_ids)}"
                    if nok_count > 0:
                        msg += f" / nok: {', '.join(nok_ids)}"

                    contains_nok_warnings: list[OntologyWarning] = [
                        w for _, ts, tws in contains_results if not ts for w in tws
                    ]
                    contains_warning: OntologyWarning = {
                        "rule": rule,
                        "severity": get_severity(rule, self._user_severity),
                        "validation_message": msg,
                        "need": task.need,
                        "schema_path": [*task.schema_path, link_type, "contains"],
                        "need_path": [*task.need_path, link_type],
                        "children": contains_nok_warnings,
                    }
                    if task.depth == 0 and self._user_message is not None:
                        contains_warning["user_message"] = self._user_message
                    warnings.append(contains_warning)
                    warnings.extend(contains_nok_warnings)

                if max_contains is not None and ok_count > max_contains:
                    overall_success = False
                    rule = MessageRuleEnum.network_contains_too_many
                    msg = (
                        f"Too many valid links of type '{link_type}' "
                        f"({ok_count} > {max_contains})"
                    )
                    if ok_count > 0:
                        msg += f" / ok: {', '.join(ok_ids)}"
                    if nok_count > 0:
                        msg += f" / nok: {', '.join(nok_ids)}"
                    max_warning: OntologyWarning = {
                        "rule": rule,
                        "severity": get_severity(rule, self._user_severity),
                        "validation_message": msg,
                        "need": task.need,
                        "schema_path": [*task.schema_path, link_type, "contains"],
                        "need_path": [*task.need_path, link_type],
                    }
                    if task.depth == 0 and self._user_message is not None:
                        max_warning["user_message"] = self._user_message
                    warnings.append(max_warning)

        return overall_success, warnings, dependencies, new_tasks

    def _collect_all_warnings(self) -> dict[str, list[OntologyWarning]]:
        """Collect all warnings from cache.

        :return: Mapping of need IDs to their validation warnings.
        """
        result: dict[str, list[OntologyWarning]] = {}
        for need_id, validation_result in self._cache._results.items():
            warnings = validation_result.all_warnings
            if warnings:
                result[need_id] = warnings
        return result

    @property
    def cache_size(self) -> int:
        """Return the number of cached validation results."""
        return len(self._cache)


def validate_type_schema_cached(
    config: NeedsSphinxConfig,
    schema: SchemasRootType,
    needs: NeedsView,
    field_properties: Mapping[str, NeedFieldProperties],
    *,
    validator: TypeSchemaValidator | None = None,
    modified_need_ids: Set[str] | None = None,
) -> tuple[TypeSchemaValidator, dict[str, list[OntologyWarning]]]:
    """Validate needs against a type schema with optional caching.

    This is a convenience function that creates or reuses a TypeSchemaValidator.

    :param config: The sphinx-needs configuration.
    :param schema: The type schema to validate against.
    :param needs: All needs to validate.
    :param field_properties: Properties of need fields for validation.
    :param validator: Optional existing validator for incremental validation.
    :param modified_need_ids: IDs of modified needs for incremental validation.
    :return: Tuple of (validator, warnings_dict) for potential reuse.
    """
    if validator is None:
        validator = TypeSchemaValidator(config, schema, field_properties)
        warnings = validator.validate_all(needs)
    elif modified_need_ids is not None:
        warnings = validator.validate_incremental(needs, modified_need_ids)
    else:
        warnings = validator.validate_all(needs)

    return validator, warnings
