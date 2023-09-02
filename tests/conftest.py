"""Pytest conftest module containing common test configuration and fixtures."""
import json
import os.path
import shutil
import subprocess
from pathlib import Path
from tempfile import mkdtemp
from typing import Any, Dict

import pytest
from sphinx.application import Sphinx
from sphinx.testing.path import path

pytest_plugins = "sphinx.testing.fixtures"


def copy_srcdir_to_tmpdir(srcdir, tmp):
    srcdir = path(__file__).parent.abspath() / srcdir
    tmproot = tmp / path(srcdir).basename()
    shutil.copytree(srcdir, tmproot)
    return tmproot


def get_abspath(relpath):
    if relpath and isinstance(relpath, str):
        abspath = Path(__file__).parent.joinpath(relpath).resolve()
        return str(abspath)
    return relpath


def test_js(self) -> Dict[str, Any]:
    cypress_testpath = get_abspath(self.spec_pattern)

    if not cypress_testpath and not (os.path.isabs(cypress_testpath) and os.path.exists(cypress_testpath)):
        return {
            "returncode": 1,
            "stdout": None,
            "stderr": f"The spec_pattern you provided cannot be found. (spec_pattern: {self.spec_pattern})",
        }

    js_test_config = {
        "specPattern": cypress_testpath,
        "supportFile": get_abspath("js_test/cypress/support/e2e.js"),
        "fixturesFolder": False,
        "baseUrl": "http://localhost:65323",
    }

    cypress_config = f"{json.dumps(js_test_config)}"
    cypress_config_file = get_abspath("js_test/cypress.config.js")

    # Start the HTTP server using subprocess
    server_process = subprocess.Popen(["python", "-m", "http.server", "-d", f"{self.outdir}", "65323"])

    try:
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

        # To stop the server, we can terminate the process
        server_process.terminate()
        server_process.wait(timeout=5)  # Wait for up to 5 seconds for the process to exit
        # print("Server stopped successfully.")

        # Send back return code, stdout, and stderr
        return {
            "returncode": completed_process.returncode,
            "stdout": completed_process.stdout,
            "stderr": completed_process.stderr,
        }
    except subprocess.TimeoutExpired:
        server_process.kill()
        return {
            "returncode": 1,
            "stdout": None,
            "stderr": "Server forcibly terminated due to timeout.",
        }
    except (Exception, subprocess.CalledProcessError) as e:
        # Stop server when an exception occurs
        server_process.terminate()
        server_process.wait(timeout=5)  # Wait for up to 5 seconds for the process to exit
        return {
            "returncode": 1,
            "stdout": "Server stopped due to error.",
            "stderr": e,
        }


@pytest.fixture(scope="function")
def test_app(make_app, request):
    # We create a temp-folder on our own, as the util-functions from sphinx and pytest make troubles.
    # It seems like they reuse certain-temp names
    sphinx_test_tempdir = path(mkdtemp())

    builder_params = request.param

    # copy plantuml.jar to current test temdir
    plantuml_jar_file = path(__file__).parent.abspath() / "doc_test/utils"
    shutil.copytree(plantuml_jar_file, sphinx_test_tempdir / "utils")

    # copy test srcdir to test temporary directory sphinx_test_tempdir
    srcdir = builder_params.get("srcdir")
    src_dir = copy_srcdir_to_tmpdir(srcdir, sphinx_test_tempdir)

    # return sphinx.testing fixture make_app and new srcdir which is in sphinx_test_tempdir
    app: Sphinx = make_app(
        buildername=builder_params.get("buildername", "html"),
        srcdir=src_dir,
        freshenv=builder_params.get("freshenv"),
        confoverrides=builder_params.get("confoverrides"),
        status=builder_params.get("status"),
        warning=builder_params.get("warning"),
        tags=builder_params.get("tags"),
        docutilsconf=builder_params.get("docutilsconf"),
        parallel=builder_params.get("parallel", 0),
    )
    # Add the spec_pattern as an attribute to the Sphinx app object
    app.spec_pattern = builder_params.get("spec_pattern", "")
    # Add the test_js() function as an attribute to the Sphinx app object
    app.test_js = test_js.__get__(app, Sphinx)

    yield app

    # cleanup test temporary directory
    shutil.rmtree(sphinx_test_tempdir, False)
