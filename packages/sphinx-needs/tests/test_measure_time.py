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
