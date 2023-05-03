import inspect
import json
import os.path
from functools import wraps
from pathlib import Path
from timeit import default_timer as timer  # Used for timing measurements
from typing import Any, Callable, Dict, List, Optional

from jinja2 import Environment, PackageLoader, select_autoescape
from sphinx.application import Sphinx

TIME_MEASUREMENTS: Dict[str, Any] = {}  # Stores the timing results
EXECUTE_TIME_MEASUREMENTS = False  # Will be used to de/activate measurements. Set during a Sphinx Event

START_TIME = 0


def measure_time(
    category: "str | None" = None, source: str = "internal", name: "str | None" = None, func: "object | None" = None
) -> Callable[..., Callable[..., Any]]:
    """
    Measures the needed execution time of a specific function.

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

    Usage as function::

        from sphinx_needs.utils import measure_time

        # Old call: my_cool_function(a,b,c)
        new_func = measure_time('my_category', func=my_cool_function)
        new_func(a,b,c)

    :param category: Name of a category, which helps to cluster the measured functions.
    :param source: Should be "internal" or "user". Used to easily structure function written by user.
    :param name: Name to use for the measured. If not given, the function name is used.
    :param func: Can contain a func, which shall get decorated. Not used if ``measure_time`` is used as decorator.
    """

    def inner(func: Any) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: List[object], **kwargs: Dict[object, object]) -> Any:
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

            if name is None:
                mt_name = func.__name__
            else:
                mt_name = name

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
                runtime_dict["max_params"] = {
                    "args": str(args),
                    "kwargs": str(kwargs),
                }
            runtime_dict["min_max_spread"] = runtime_dict["max"] / runtime_dict["min"] * 100
            runtime_dict["avg"] = runtime_dict["overall"] / runtime_dict["amount"]
            return result

        return wrapper

    # if `measure_time` is used as function and not as decorator, execute the `inner()` with given func directly
    if func is not None:
        return inner(func)

    return inner


def print_timing_results() -> None:
    for value in TIME_MEASUREMENTS.values():
        print(value["name"])
        print(f' amount:  {value["amount"]}')
        print(f' overall: {value["overall"]:2f}')
        print(f' avg:     {value["avg"]:2f}')
        print(f' max:     {value["max"]:2f}')
        print(f' min:     {value["min"]:2f} \n')


def store_timing_results_json(outdir: str, build_data: Dict[str, Any]) -> None:
    json_result_path = os.path.join(outdir, "debug_measurement.json")

    data = {"build": build_data, "measurements": TIME_MEASUREMENTS}

    with open(json_result_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"Timing measurement results (JSON) stored under {json_result_path}")


def store_timing_results_html(outdir: str, build_data: Dict[str, Any]) -> None:
    jinja_env = Environment(loader=PackageLoader("sphinx_needs"), autoescape=select_autoescape())
    template = jinja_env.get_template("time_measurements.html")
    out_file = Path(outdir) / "debug_measurement.html"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(template.render(data=TIME_MEASUREMENTS, build_data=build_data))
    print(f"Timing measurement report (HTML) stored under {out_file}")


def process_timing(app: Sphinx, _exception: Optional[Exception]) -> None:
    if EXECUTE_TIME_MEASUREMENTS:
        build_data = {
            "project": app.config["project"],
            "start": START_TIME,
            "end": timer(),
            "duration": timer() - START_TIME,
        }

        print_timing_results()
        store_timing_results_json(app.outdir, build_data)
        store_timing_results_html(app.outdir, build_data)
