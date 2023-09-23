"""Pytest conftest module containing common test configuration and fixtures."""
import json
import os.path
import secrets
import shutil
import string
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
from sphinx.application import Sphinx
from sphinx.testing.path import path
from xprocess import ProcessStarter

pytest_plugins = "sphinx.testing.fixtures"


def generate_random_string() -> str:
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for i in range(10))


def copy_srcdir_to_tmpdir(srcdir: path, tmp: path) -> path:
    srcdir = path(__file__).parent.abspath() / srcdir
    tmproot = tmp.joinpath(generate_random_string()) / path(srcdir).basename()
    shutil.copytree(srcdir, tmproot)
    return tmproot


def get_abspath(relpath: str) -> str:
    """
    Get the absolute path from a relative path.

    This function returns an absolute path relative to the conftest.py file.

    :param relpath: The relative path to convert.
    :return: The absolute path, or the input if it's not a valid relative path.
    """
    if isinstance(relpath, str) and relpath:
        abspath = Path(__file__).parent.joinpath(relpath).resolve()
        return str(abspath)
    return relpath


@pytest.fixture(scope="session")
def test_server(xprocess, sphinx_test_tempdir):
    class Starter(ProcessStarter):
        # pattern = "HTTP Server started on port [0-9]+!"
        pattern = "Serving HTTP on [0-9.]+ port [0-9]+"
        # wait for 10 seconds before timing out
        timeout = 10
        # terminate and clean up all started processes and their resources upon interruptions
        # during pytest runs (CTRL+C, SIGINT and internal errors)
        terminate_on_interrupt = True
        # command to start process
        # args = ["python", f"{path(__file__).parent.abspath()}/server.py", sphinx_test_tempdir]
        args = ["python", "-m", "http.server", "--directory", sphinx_test_tempdir, "--bind", "127.0.0.1", "62343"]

    # ensure process is running and return its logfile
    logfile = xprocess.ensure("http_server", Starter, restart=True)  # noqa:F841
    http_server_process = xprocess.getinfo("http_server")
    server_url = "http://localhost:62343"
    http_server_process.url = server_url

    yield http_server_process

    # clean up whole process tree afterward
    http_server_process.terminate()


def test_js(self) -> Dict[str, Any]:
    """
    Executes Cypress tests using the specified `spec_pattern`.

    :param self: An instance of the :class:`Sphinx` application object this function is bounded to.
    :return: A dictionary with test execution information.
             Keys:
                - 'returncode': Return code of the Cypress test execution.
                - 'stdout': Standard output of the Cypress test execution.
                - 'stderr': Standard error of the Cypress test execution.
    """
    cypress_testpath = get_abspath(self.spec_pattern)

    if not cypress_testpath or not (os.path.isabs(cypress_testpath) and os.path.exists(cypress_testpath)):
        return {
            "returncode": 1,
            "stdout": None,
            "stderr": f"The spec_pattern '{self.spec_pattern}' cannot be found.",
        }
    _, out_dir = str(self.outdir).split("sn_test_build_data")
    srcdir_url = f"http://localhost:62343/{out_dir.lstrip('/')}/"
    js_test_config = {
        "specPattern": cypress_testpath,
        "supportFile": get_abspath("js_test/cypress/support/e2e.js"),
        "fixturesFolder": False,
        "baseUrl": srcdir_url,
    }

    cypress_config = json.dumps(js_test_config)
    cypress_config_file = get_abspath("js_test/cypress.config.js")

    try:
        import subprocess

        # Run the Cypress test command
        completed_process = subprocess.run(
            [
                "npx",
                "cypress",
                "run",
                "--browser",
                "chrome",
                "--config-file",
                rf"{cypress_config_file}",
                "--config",
                rf"{cypress_config}",
            ],
            capture_output=True,
        )

        # Send back return code, stdout, and stderr
        return {
            "returncode": completed_process.returncode,
            "stdout": completed_process.stdout,
            "stderr": completed_process.stderr,
        }
    except (Exception, subprocess.CalledProcessError) as e:
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": e,
        }


@pytest.fixture(scope="session")
def sphinx_test_tempdir():
    # We create a temp-folder on our own, as the util-functions from sphinx and pytest make troubles.
    # It seems like they reuse certain-temp names
    sphinx_test_tempdir = path(tempfile.gettempdir()).joinpath("sn_test_build_data")
    utils_dir = sphinx_test_tempdir.joinpath("utils")

    if not (sphinx_test_tempdir.exists() and sphinx_test_tempdir.isdir()):
        sphinx_test_tempdir.makedirs()
    if not (utils_dir.exists() and utils_dir.isdir()):
        utils_dir.makedirs()

    # copy plantuml.jar to current test tempdir. We want to do this once
    # since the same plantuml.jar is used for each test
    plantuml_jar_file = path(__file__).parent.abspath() / "doc_test/utils"
    shutil.copytree(plantuml_jar_file, utils_dir, dirs_exist_ok=True)

    return sphinx_test_tempdir


@pytest.fixture(scope="function")
def test_app(make_app, sphinx_test_tempdir, request):
    builder_params = request.param

    sphinx_conf_overrides = builder_params.get("confoverrides", {})
    # Since we don't want copy the plantuml.jar file for each test function,
    # we need to override the plantuml conf variable and set it to what we have already
    plantuml = "java -Djava.awt.headless=true -jar %s" % os.path.join(sphinx_test_tempdir, "utils", "plantuml.jar")
    sphinx_conf_overrides.update(plantuml=plantuml)

    # copy test srcdir to test temporary directory sphinx_test_tempdir
    srcdir = builder_params.get("srcdir")
    src_dir = copy_srcdir_to_tmpdir(srcdir, sphinx_test_tempdir)

    # return sphinx.testing fixture make_app and new srcdir which is in sphinx_test_tempdir
    app: Sphinx = make_app(
        buildername=builder_params.get("buildername", "html"),
        srcdir=src_dir,
        freshenv=builder_params.get("freshenv"),
        confoverrides=sphinx_conf_overrides,
        status=builder_params.get("status"),
        warning=builder_params.get("warning"),
        tags=builder_params.get("tags"),
        docutilsconf=builder_params.get("docutilsconf"),
        parallel=builder_params.get("parallel", 0),
    )
    # Add the spec_pattern as an attribute to the Sphinx app object
    app.spec_pattern = builder_params.get("spec_pattern", "*.cy.js")
    # Add the ``test_js`` function as an attribute to the Sphinx app object
    # This is done by accessing the special method ``__get__`` which allows the ``test_js`` function
    # to be bound to the Sphinx app object, enabling it to access the object's attributes.
    # We can later call ``test_js`` function as an attribute of the Sphinx app object.
    # Since we've bound the ``test_js`` function to the Sphinx object using ``__get__``,
    # ``test_js`` behaves like a method.
    app.test_js = test_js.__get__(app, Sphinx)

    yield app

    # Clean up the srcdir of each Sphinx app after the test function has executed
    shutil.rmtree(src_dir.parent.abspath(), ignore_errors=True)
