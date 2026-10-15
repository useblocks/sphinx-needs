import functools

import pytest

from sphinx_codelinks.sphinx_extension import debug


@pytest.fixture(autouse=True)
def _restore_time_measurement_globals():
    """Put the module-level measurement switches back after each test."""
    saved = (
        debug.EXECUTE_TIME_MEASUREMENTS,
        debug.START_TIME,
        dict(debug.TIME_MEASUREMENTS),
    )
    yield
    debug.EXECUTE_TIME_MEASUREMENTS, debug.START_TIME = saved[:2]
    debug.TIME_MEASUREMENTS.clear()
    debug.TIME_MEASUREMENTS.update(saved[2])


def _source_less_function():
    """A function whose source inspect cannot read, as one from a removed file."""
    namespace: dict = {}
    exec("def gone(x):\n    return x * 2\n", namespace)
    return namespace["gone"]


@pytest.mark.parametrize(
    ("func", "name"),
    [
        (functools.partial(int, base=2), "functools.partial"),
        (_source_less_function(), "gone"),
    ],
    ids=["partial-without-__name__", "function-without-source"],
)
def test_measure_time_func_on_a_callable_inspect_cannot_place(func, name):
    """The same guard as sphinx-needs' copy of ``measure_time``: no ``__name__``, or
    no readable source, no longer raises when measurement is on."""
    debug.EXECUTE_TIME_MEASUREMENTS = True
    measured = debug.measure_time_func(func, category="test_inspect")
    assert measured("11") == func("11")

    (entry,) = [
        value
        for key, value in debug.TIME_MEASUREMENTS.items()
        if key.startswith("test_inspect_")
    ]
    assert name in entry["name"]
    assert entry["amount"] == 1
    assert entry["file"] is None or name == "gone"
    assert entry["line"] is None
