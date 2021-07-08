"""
Executes several performance tests.

"""
import os.path
import shutil
import subprocess
import tempfile
import time
import webbrowser

import click
from tabulate import tabulate


@click.group()
def cli():
    pass


@cli.command()
@click.option("--needs", default=100, type=int, help="Number of needs.")
@click.option("--needtables", default=0, type=int, help="Number of needtables.")
@click.option("--dummies", default=0, type=int, help="Number of standard rst dummies.")
@click.option("--keep", is_flag=True, help="Keeps the temporary build folders")
@click.option("--browser", is_flag=True, help="Opens the project in your browser")
@click.option("--debug", is_flag=True, help="Prints some more outputs")
def single(needs=1000, needtables=0, dummies=0, keep=False, browser=False, debug=False):
    """
    Start a single test run.
    :param needs:
    :param needtable:
    :param keep:
    :return:
    """
    start(needs, needtables, dummies, keep, browser, debug)


def start(needs=1000, needtables=0, dummies=0, keep=False, browser=False, debug=False):
    """
    Test run implementation
    """
    source_path = os.path.join(os.path.dirname(__file__), "project/")
    build_path = tempfile.mkdtemp()

    if browser:
        keep = True

    print(f"* Running with {needs} needs, {needtables} needtables, {dummies} dummies")
    start_time = time.time()
    params = [
        "sphinx-build",
        "-a",
        "-E",
        "-A",
        f"needs={needs}",
        "-A",
        f"needtables={needtables}",
        "-A",
        f"dummies={dummies}",
        "-A",
        f"keep={keep}",
        "-A",
        f"browser={browser}",
        "-A",
        f"debug={debug}",
        "-b",
        "html",
        source_path,
        build_path,
    ]

    if debug:
        print(f'  Call: {" ".join(params)} ')
    subprocess.run(params, stdout=subprocess.DEVNULL)
    end_time = time.time()

    project_path = os.path.join(build_path, "index.html")
    if keep and debug:
        print(f"  Project = {project_path}")
    if not keep:
        if debug:
            print(f"  Deleting project: {build_path}")
        shutil.rmtree(build_path)

    result_time = end_time - start_time

    if browser:
        try:
            webbrowser.open_new_tab(project_path)
        except Exception:
            pass

    print(f"  Duration: {result_time:.2f} seconds")

    return result_time


@cli.command()
@click.option("--needs", default=[1000], type=int, multiple=True, help="Number of maximum needs.")
@click.option("--needtables", default=-1, type=int, help="Number of maximum needtables.")
@click.option("--dummies", default=-1, type=int, help="Number of standard rst dummies.")
@click.option("--keep", is_flag=True, help="Keeps the temporary build folders")
@click.option("--browser", is_flag=True, help="Opens the project in your browser")
@click.option("--debug", is_flag=True, help="Prints some more outputs")
def series(needs, needtables=-1, dummies=-1, keep=False, browser=False, debug=False):
    """
    Generate and start a series of tests.
    """
    needs = list(needs)
    configs = []
    if len(needs) == 1:
        # Define a default test series
        current = needs[0]

        while current >= 1:
            configs.append(
                {
                    "needs": int(current),
                    "needtables": int(current / 10) if needtables < 0 else needtables,
                    "dummies": int(current) if dummies < 0 else dummies,
                    "keep": keep,
                    "browser": browser,
                    "debug": debug,
                },
            )
            current = round(current / 10)
    else:
        while needs:
            current = needs.pop()
            configs.append(
                {
                    "needs": int(current),
                    "needtables": int(current / 10) if needtables < 0 else needtables,
                    "dummies": int(current / 10) if dummies < 0 else dummies,
                    "keep": keep,
                    "browser": browser,
                    "debug": debug,
                },
            )

    results = []
    for config in configs:
        result = start(**config)
        results.append((config, result))

    print("\nRESULTS:\n")
    result_table = []
    for result in results:
        result_table.append([f"{result[1]:.2f}", result[0]["needs"], result[0]["needtables"], result[0]["dummies"]])
    headers = ["runtime s", "needs #", "needtables #", "dummies #"]
    print(tabulate(result_table, headers=headers))


if "main" in __name__:
    cli()
