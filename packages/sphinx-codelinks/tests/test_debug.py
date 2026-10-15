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


def _measured_function(x):
    return x


class _CallableInstance:
    def __call__(self, x):
        return x


def _source_less_function():
    """A function whose source inspect cannot read, as one from a removed file."""
    namespace: dict = {}
    exec("def gone(x):\n    return x\n", namespace)
    return namespace["gone"]


@pytest.mark.parametrize(
    ("func", "name", "file", "line"),
    [
        (
            _measured_function,
            "_measured_function",
            __file__,
            _measured_function.__code__.co_firstlineno,
        ),
        (functools.partial(str.strip), "partial(strip)", None, None),
        (_CallableInstance(), "_CallableInstance", None, None),
        (_source_less_function(), "gone", "<string>", None),
    ],
    ids=["function", "partial", "callable-instance", "function-without-source"],
)
def test_measure_time_func_names_and_places_a_callable(func, name, file, line):
    """What a measurement records for a callable, whatever kind it is.

    ``measure_time`` read ``func.__name__``, ``inspect.getfile`` and
    ``inspect.getsourcelines`` unguarded, so with measurement on a partial or a callable
    instance raised ``AttributeError`` and a function whose source is gone raised
    ``OSError``, ending the build. A plain function is recorded as before; the others
    are named after what they wrap or their type -- never a ``repr`` with an address --
    and their location is ``None`` where inspect cannot give it.
    """
    debug.EXECUTE_TIME_MEASUREMENTS = True
    measured = debug.measure_time_func(func, category="test_inspect")
    assert measured("1") == func("1")

    entry = debug.TIME_MEASUREMENTS[f"test_inspect_{name}"]
    assert (entry["name"], entry["file"], entry["line"], entry["amount"]) == (
        name,
        file,
        line,
        1,
    )
