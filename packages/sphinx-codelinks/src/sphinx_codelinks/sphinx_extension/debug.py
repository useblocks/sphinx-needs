"""
Contains debug features to track down
runtime and other problems with Src-Trace
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from functools import wraps
import inspect
import json
from pathlib import Path
from timeit import default_timer as timer  # Used for timing measurements
from typing import Any, TypeVar

from jinja2 import Environment, PackageLoader, select_autoescape
from sphinx.application import Sphinx

# Stores the timing results
TIME_MEASUREMENTS: dict[str, Any] = {}  # type: ignore[explicit-any]
EXECUTE_TIME_MEASUREMENTS = (
    False  # Will be used to de/activate measurements. Set during a Sphinx Event
)

START_TIME = 0.0

T = TypeVar("T", bound=Callable[..., Any])  # type: ignore[explicit-any]


def measure_time(  # type: ignore[explicit-any]
    category: str | None = None, source: str = "internal", name: str | None = None
) -> Callable[[T], T]:
    """
    Decorator for measuring the needed execution time of a specific function.

    It measures:

    * Amount of executions
    * Overall time consumed
    * Average time of an execution as `avg`
    * Minimum time of an execution as `min`
    * Maximum time of an execution as `max`

    For `max` also the used function parameters are stored as string values, to make
    it easier to reproduce the maximum case.

    Usage as decorator::

        from sphinx_needs.utils import measure_time

        @measure_time('my_category')
        def my_cool_function(a, b,c ):
            # does something

    :param category: Name of a category, which helps to cluster the measured functions.
    :param source: Should be "internal" or "user". Used to easily structure function written by user.
    :param name: Name to use for the measured. If not given, the function name is used.
    """

    def inner(func: T) -> T:  # type: ignore[explicit-any]
        @wraps(func)
        def wrapper(*args: list[object], **kwargs: dict[object, object]) -> Any:  # type: ignore[explicit-any]
            """
            Wrapper function around a given/decorated function, which cares about measurement and storing the result

            :param args: Arguments for the original function
            :param kwargs: Keyword arguments for the original function
            """
            if not EXECUTE_TIME_MEASUREMENTS:
                return func(*args, **kwargs)

            start = timer()
            # Execute original function
            result = func(*args, **kwargs)
            end = timer()

            runtime = end - start

            mt_name = func.__name__ if name is None else name

            mt_id = f"{category}_{func.__name__}"

            if mt_id not in TIME_MEASUREMENTS:
                TIME_MEASUREMENTS[mt_id] = {
                    "name": mt_name,
                    "category": category,
                    "source": source,
                    "doc": func.__doc__,
                    "file": inspect.getfile(func),
                    "line": inspect.getsourcelines(func)[1],
                    "amount": 0,
                    "overall": 0,
                    "avg": None,
                    "min": None,
                    "max": None,
                    "min_max_spread": None,
                    "max_params": {"args": [], "kwargs": {}},
                }

            runtime_dict = TIME_MEASUREMENTS[mt_id]

            runtime_dict["amount"] += 1
            runtime_dict["overall"] += runtime

            if runtime_dict["min"] is None or runtime < runtime_dict["min"]:
                runtime_dict["min"] = runtime

            if runtime_dict["max"] is None or runtime > runtime_dict["max"]:
                runtime_dict["max"] = runtime
                runtime_dict["max_params"] = {  # Store parameters as a shorten string
                    "args": str([str(arg)[:80] for arg in args]),
                    "kwargs": str(
                        {key: str(value)[:80] for key, value in kwargs.items()}
                    ),
                }
            runtime_dict["min_max_spread"] = (
                runtime_dict["max"] / runtime_dict["min"] * 100
            )
            runtime_dict["avg"] = runtime_dict["overall"] / runtime_dict["amount"]
            return result

        return wrapper  # type: ignore[return-value]

    return inner


def measure_time_func(  # type: ignore[explicit-any]
    func: T,
    category: str | None = None,
    source: str = "internal",
    name: str | None = None,
) -> T:
    """Wrapper for measuring the needed execution time of a specific function.

    Usage as function::

        from sphinx_needs.utils import measure_time

        # Old call: my_cool_function(a,b,c)
        new_func = measure_time_func('my_category', func=my_cool_function)
        new_func(a,b,c)
    """
    return measure_time(category, source, name)(func)


def _print_timing_results() -> None:
    for value in TIME_MEASUREMENTS.values():
        print(value["name"])
        print(f" amount:  {value['amount']}")
        print(f" overall: {value['overall']:2f}")
        print(f" avg:     {value['avg']:2f}")
        print(f" max:     {value['max']:2f}")
        print(f" min:     {value['min']:2f} \n")


def _store_timing_results_json(app: Sphinx, build_data: dict[str, Any]) -> None:  # type: ignore[explicit-any]
    json_result_path = Path(app.outdir) / "debug_measurement.json"

    data = {"build": build_data, "measurements": TIME_MEASUREMENTS}
    with json_result_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"Timing measurement results (JSON) stored under {json_result_path}")


def _store_timing_results_html(app: Sphinx, build_data: dict[str, Any]) -> None:  # type: ignore[explicit-any]
    jinja_env = Environment(
        loader=PackageLoader("sphinx_needs"), autoescape=select_autoescape()
    )
    template = jinja_env.get_template("time_measurements.html")
    out_file = Path(str(app.outdir)) / "debug_measurement.html"
    with out_file.open("w", encoding="utf-8") as f:
        f.write(template.render(data=TIME_MEASUREMENTS, build_data=build_data))
    print(f"Timing measurement report (HTML) stored under {out_file}")


def process_timing(app: Sphinx, _exception: Exception | None) -> None:
    if EXECUTE_TIME_MEASUREMENTS:
        build_data = {
            "project": app.config["project"],
            "start": START_TIME,
            "end": timer(),
            "duration": timer() - START_TIME,
            "timestamp": datetime.now().isoformat(),
        }

        _print_timing_results()
        _store_timing_results_json(app, build_data)
        _store_timing_results_html(app, build_data)
