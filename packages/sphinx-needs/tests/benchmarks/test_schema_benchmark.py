"""Benchmark processing of schemas."""

import pytest

from sphinx_needs.schema.process import process_schemas


@pytest.mark.parametrize("schema_benchmark_app", [10, 100, 1000, 10_000], indirect=True)
def test_schema_benchmark(schema_benchmark_app, benchmark):
    """Benchmark processing of schemas."""
    schema_benchmark_app.build()
    assert schema_benchmark_app.statuscode == 0
    benchmark.pedantic(
        lambda: process_schemas(schema_benchmark_app, schema_benchmark_app.builder),
        iterations=5,
        rounds=3,
    )
