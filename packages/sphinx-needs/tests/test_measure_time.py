import functools
from pathlib import Path

import pytest

from sphinx_needs import debug
from sphinx_needs_testkit import build_warnings


@pytest.fixture(autouse=True)
def _restore_time_measurement_globals():
    """Put ``sphinx_needs.debug``'s module-level switches back after this build.

    ``needs.py`` sets ``debug.EXECUTE_TIME_MEASUREMENTS`` to ``True`` for a project that
    asks for timings and never sets it back, so every later build in the same process runs
    the ``measure_time`` wrappers too. That is invisible until one of them measures a
    filter function loaded from a test project's own directory: the wrapper calls
    ``inspect.getsourcelines`` the first time it sees a function, the directory the
    function came from was removed with the test that created it, and the build dies with
    ``OSError: could not get source code``. Ordering decides whether that ever happens, so
    the suite was green in file order and red under ``--random-order-seed=1911``.

    The leak is production code's -- the reset belongs in ``debug.process_timing``, which
    is already connected to ``build-finished`` -- and closing it there is a change to
    ``src/``. This is the test-side half: the one test that flips the switch puts it back.
    """
    saved = (
        debug.EXECUTE_TIME_MEASUREMENTS,
        debug.START_TIME,
        dict(debug.TIME_MEASUREMENTS),
    )
    yield
    (
        debug.EXECUTE_TIME_MEASUREMENTS,
        debug.START_TIME,
    ) = saved[:2]
    debug.TIME_MEASUREMENTS.clear()
    debug.TIME_MEASUREMENTS.update(saved[2])


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_measure_time"}],
    indirect=True,
)
def test_measure_time(test_app):
    app = test_app
    app.build()
    warning_records = build_warnings(app)
    assert warning_records == [
        "<srcdir>/index.rst:49: WARNING: The 'export_id' option is deprecated, instead use the `needs_debug_filters` configuration. [needs.deprecated]"
    ]
    outdir = Path(str(app.outdir))
    assert outdir.joinpath("debug_measurement.json").exists()
    assert outdir.joinpath("debug_filters.jsonl").exists()


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
