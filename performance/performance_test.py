"""
Executes several performance tests.

"""

import os.path
import shutil
import subprocess
import tempfile
import time
import webbrowser
from contextlib import suppress
from pathlib import Path

import click
from jinja2 import Template
from tabulate import tabulate


@click.group()
def cli():
    pass


def start(
    needs=1000,
    needtables=0,
    dummies=0,
    pages=1,
    parallel=1,
    keep=False,
    browser=False,
    debug=False,
    basic=False,
):
    """
    Test run implementation
    """
    source_path = os.path.join(os.path.dirname(__file__), "project/")
    source_tmp_path = tempfile.mkdtemp()
    build_path = tempfile.mkdtemp()

    shutil.copytree(source_path, source_tmp_path, dirs_exist_ok=True)

    # Render conf.py
    source_tmp_path_conf = os.path.join(source_tmp_path, "conf.template")
    source_tmp_path_conf_final = os.path.join(source_tmp_path, "conf.py")
    template = Template(Path(source_tmp_path_conf).read_text())
    rendered = template.render(
        pages=pages,
        needs=needs,
        needtables=needtables,
        dummies=dummies,
        parallel=parallel,
        keep=keep,
        browser=browser,
        debug=debug,
        basic=basic,
    )
    with open(source_tmp_path_conf_final, "w") as file:
        file.write(rendered)

    # Render index files
    source_tmp_path_index = os.path.join(source_tmp_path, "index.template")
    source_tmp_path_index_final = os.path.join(source_tmp_path, "index.rst")
    template = Template(Path(source_tmp_path_index).read_text())
    title = "Index"
    rendered = template.render(
        pages=pages,
        title=title,
        needs=needs,
        needtables=needtables,
        dummies=dummies,
        parallel=parallel,
        keep=keep,
        browser=browser,
        debug=debug,
        basic=basic,
    )
    with open(source_tmp_path_index_final, "w") as file:
        file.write(rendered)

    # Render pages
    for p in range(pages):
        source_tmp_path_page = os.path.join(source_tmp_path, "page.template")
        source_tmp_path_page_final = os.path.join(source_tmp_path, f"page_{p}.rst")
        template = Template(Path(source_tmp_path_page).read_text())
        title = f"Page {p}"
        rendered = template.render(
            page=p,
            title=title,
            pages=pages,
            needs=needs,
            needtables=needtables,
            dummies=dummies,
            parallel=parallel,
            keep=keep,
            browser=browser,
            debug=debug,
            basic=basic,
        )
        with open(source_tmp_path_page_final, "w") as file:
            file.write(rendered)

    if browser:
        keep = True

    print(
        f"* Running on {pages} pages with {needs} needs, {needtables} needtables,"
        f" {dummies} dummies per page. Using {parallel} cores."
    )
    start_time = time.time()
    params = [
        "sphinx-build",
        "-a",
        "-E",
        "-j",
        str(parallel),
        "-A",
        f"needs={needs}",
        "-A",
        f"needtables={needtables}",
        "-A",
        f"dummies={dummies}",
        "-A",
        f"pages={pages}",
        "-A",
        f"keep={keep}",
        "-A",
        f"browser={browser}",
        "-A",
        f"debug={debug}",
        "-b",
        "html",
        source_tmp_path,
        build_path,
    ]

    project_path = os.path.join(build_path, "index.html")
    if keep and debug:
        print(f"  Project = {source_tmp_path}")
        print(f"  Build   = {project_path}")
    if debug:
        print(f"  Call: {' '.join(params)} ")

    if debug:
        subprocess.run(params)
    else:
        subprocess.run(params, stdout=subprocess.DEVNULL)

    end_time = time.time()

    if keep:
        print(f"  Project = {source_tmp_path}")
        print(f"  Build   = {project_path}")
    else:
        if debug:
            print(f"  Deleting project: {build_path}")
        shutil.rmtree(build_path)
        shutil.rmtree(source_tmp_path)

    result_time = end_time - start_time

    if browser:
        with suppress(Exception):
            webbrowser.open_new_tab(project_path)

    print(f"  Duration: {result_time:.2f} seconds")

    return result_time


@cli.command()
@click.option(
    "--profile",
    default=[],
    type=str,
    multiple=True,
    help="Activates profiling for given area",
)
@click.option(
    "--needs",
    default=[50, 10],
    type=int,
    multiple=True,
    help="Number of maximum needs.",
)
@click.option(
    "--needtables", default=-1, type=int, help="Number of maximum needtables."
)
@click.option("--dummies", default=-1, type=int, help="Number of standard rst dummies.")
@click.option(
    "--pages",
    default=[5, 1],
    type=int,
    multiple=True,
    help="Number of additional pages with needs.",
)
@click.option(
    "--parallel",
    default=[1, 4],
    type=int,
    multiple=True,
    help="Number of parallel processes to use. Same as -j for sphinx-build",
)
@click.option("--keep", is_flag=True, help="Keeps the temporary src and build folders")
@click.option("--browser", is_flag=True, help="Opens the project in your browser")
@click.option(
    "--snakeviz",
    is_flag=True,
    help="Opens snakeviz view for measured profiles in browser",
)
@click.option(
    "--debug", is_flag=True, help="Prints more information, incl. sphinx build output"
)
@click.option(
    "--basic",
    is_flag=True,
    help="Use only default config of Sphinx-Needs (e.g. no extra options)",
)
def series(
    profile,
    needs,
    needtables=-1,
    dummies=-1,
    pages=0,
    parallel=1,
    keep=False,
    browser=False,
    snakeviz=False,
    debug=False,
    basic=False,
):
    """
    Generate and start a series of tests.
    """
    needs = list(needs)
    configs = []

    profile_str = ",".join(profile)
    os.environ["NEEDS_PROFILING"] = profile_str

    for need in needs:
        for page in pages:
            for para in parallel:
                configs.append(
                    {
                        "needs": int(need),
                        "needtables": int(need / 10) if needtables < 0 else needtables,
                        "dummies": int(need / 10) if dummies < 0 else dummies,
                        "pages": page,
                        "parallel": para,
                        "keep": keep,
                        "browser": browser,
                        "debug": debug,
                        "basic": basic,
                    },
                )

    print(f"Running {len(configs)} test configurations.")
    results = []
    for config in configs:
        result = start(**config)
        results.append((config, result))

    print("\nRESULTS:\n")
    result_table = []
    for result in results:
        result_table.append(
            [
                f"{result[1]:.2f}",
                result[0]["pages"],
                result[0]["needs"],
                result[0]["needs"] * result[0]["pages"],
                result[0]["needtables"] * result[0]["pages"],
                result[0]["dummies"] * result[0]["pages"],
                result[0]["parallel"],
            ]
        )
    headers = [
        "runtime\nseconds",
        "pages\noverall",
        "needs\nper page",
        "needs\noverall",
        "needtables\noverall",
        "dummies\noverall",
        "parallel\ncores",
    ]
    print(tabulate(result_table, headers=headers))

    overall_runtime = sum(x[1] for x in results)
    print(f"\nOverall runtime: {overall_runtime:.2f} seconds.")

    if snakeviz:
        print("\nStarting snakeviz servers\n")
        procs = []
        for p in profile:
            proc = subprocess.Popen(["snakeviz", f"profile/{p}.prof"])
            procs.append(proc)

        print(f"\nKilling snakeviz server in {len(procs) * 5} secs.")
        time.sleep(len(procs) * 5)
        for proc in procs:
            proc.kill()


if "main" in __name__:
    cli()
