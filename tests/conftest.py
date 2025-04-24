"""Pytest conftest module containing common test configuration and fixtures."""

import json
import os.path
import secrets
import shutil
import socket
import string
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
from docutils.nodes import document
from sphinx import version_info
from sphinx.application import Sphinx
from sphinx.testing.path import path
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode
from xprocess import ProcessStarter

pytest_plugins = "sphinx.testing.fixtures"


def generate_random_string() -> str:
    """
    Generate a random string of 10 characters consisting of letters (both uppercase and lowercase) and digits.

    :return: A random string.
    """
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for i in range(10))


def copy_srcdir_to_tmpdir(srcdir: path, tmp: path) -> path:
    """
    Copy Source Directory to Temporary Directory.

    This function copies the contents of a source directory to a temporary
    directory. It generates a random subdirectory within the temporary directory
    to avoid conflicts and enable parallel processes to run without conflicts.

    :param srcdir: Path to the source directory.
    :param tmp: Path to the temporary directory.

    :return: Path to the newly created directory in the temporary directory.
    """
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
    """
    Fixture to start and manage the test server process.

    :param sphinx_test_tempdir: The directory to serve.
    :return: Information about the server process.
    """
    addr = "127.0.0.1"
    port = 62343

    class Starter(ProcessStarter):
        pattern = "Serving HTTP on [0-9.]+ port 62343|Address already in use"
        timeout = 20
        terminate_on_interrupt = True
        args = [
            "python3",
            "-m",
            "http.server",
            "--directory",
            sphinx_test_tempdir,
            "--bind",
            addr,
            port,
        ]
        env = {"PYTHONUNBUFFERED": "1"}

    def check_server_connection(log_path: str):
        """
        Checks the connection status to a server.

        :param log_path: The path to the log file.
        :return: True if the server connection is successful, False otherwise.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((addr, port))
        sock.close()
        if result == 0:
            with open(str(log_path), "wb", 0) as stdout:
                stdout.write(
                    bytes(
                        "Serving HTTP on 127.0.0.1 port 62343 (http://127.0.0.1:62343/) ...\n",
                        "utf8",
                    )
                )
            return True
        return False

    if not check_server_connection(log_path=xprocess.getinfo("http_server").logpath):
        # Start the process and ensure it is running
        _, logfile = xprocess.ensure("http_server", Starter, persist_logs=False)

    http_server_process = xprocess.getinfo("http_server")
    server_url = f"http://{addr}:{port}"
    http_server_process.url = server_url

    yield http_server_process

    # clean up whole process tree afterward
    xprocess.getinfo("http_server").terminate()


def test_js(self) -> dict[str, Any]:
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

    if not cypress_testpath or not (
        os.path.isabs(cypress_testpath) and os.path.exists(cypress_testpath)
    ):
        return {
            "returncode": 1,
            "stdout": None,
            "stderr": f"The spec_pattern '{self.spec_pattern}' cannot be found.",
        }
    _, out_dir = str(self.outdir).split("sn_test_build_data")
    srcdir_url = f"http://127.0.0.1:62343/{out_dir.lstrip('/')}/"
    js_test_config = {
        "specPattern": cypress_testpath,
        "supportFile": get_abspath("js_test/cypress/support/e2e.js"),
        "fixturesFolder": False,
        "baseUrl": srcdir_url,
    }

    cypress_config = json.dumps(js_test_config)
    cypress_config_file = get_abspath("js_test/cypress.config.js")

    # Run the Cypress test command
    completed_process = subprocess.run(
        [
            "npx",
            "cypress",
            "run",
            # "--browser",
            # "chrome",
            "--config-file",
            rf"{cypress_config_file}",
            "--config",
            rf"{cypress_config}",
        ],
        capture_output=True,
    )

    # Send back return code, stdout, and stderr
    stdout = completed_process.stdout.decode("utf-8")
    stderr = completed_process.stderr.decode("utf-8")

    if completed_process.returncode != 0:
        print(stdout)
        print(stderr, file=sys.stderr)

    return {
        "returncode": completed_process.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


def pytest_addoption(parser):
    parser.addoption(
        "--sn-build-dir",
        action="store",
        default=None,
        help="Base directory for sphinx-needs builds",
    )


@pytest.fixture(scope="session")
def sphinx_test_tempdir(request) -> path:
    """
    Fixture to provide a temporary directory for Sphinx testing.

    This function creates a custom temporary folder to avoid potential conflicts
    with utility functions from Sphinx and pytest.

    :return Path: Path object representing the temporary directory.
    """
    # We create a temp-folder on our own, as the util-functions from sphinx and pytest make troubles.
    # It seems like they reuse certain-temp names

    temp_base = os.path.abspath(
        request.config.getoption("--sn-build-dir") or tempfile.gettempdir()
    )

    sphinx_test_tempdir = path(temp_base).joinpath("sn_test_build_data")
    utils_dir = sphinx_test_tempdir.joinpath("utils")

    # if not (sphinx_test_tempdir.exists() and sphinx_test_tempdir.isdir()):
    sphinx_test_tempdir.makedirs(exist_ok=True)
    # if not (utils_dir.exists() and utils_dir.isdir()):
    utils_dir.makedirs(exist_ok=True)

    # copy plantuml.jar to current test tempdir. We want to do this once
    # since the same plantuml.jar is used for each test
    plantuml_jar_file = path(__file__).parent.abspath() / "doc_test/utils"
    shutil.copytree(plantuml_jar_file, utils_dir, dirs_exist_ok=True)

    return sphinx_test_tempdir


@pytest.fixture(scope="function")
def test_app(make_app, sphinx_test_tempdir, request):
    """
    Fixture for creating a Sphinx application for testing.

    This fixture creates a Sphinx application with specified builder parameters and
    config overrides. It also copies the test source directory to the test temporary
    directory. The fixture yields the Sphinx application, and cleans up the temporary
    source directory after the test function has executed.

    :param make_app: A fixture for creating Sphinx applications.
    :param sphinx_test_tempdir: A fixture for providing the Sphinx test temporary directory.
    :param request: A pytest request object for accessing fixture parameters.

    :return: A Sphinx application object.
    """
    builder_params = request.param

    sphinx_conf_overrides = builder_params.get("confoverrides", {})
    if not builder_params.get("no_plantuml", False):
        # Since we don't want copy the plantuml.jar file for each test function,
        # we need to override the plantuml conf variable and set it to what we have already
        plantuml = "java -Djava.awt.headless=true -jar {}".format(
            os.path.join(sphinx_test_tempdir, "utils", "plantuml.jar")
        )
        sphinx_conf_overrides.update(plantuml=plantuml)

    # copy test srcdir to test temporary directory sphinx_test_tempdir
    srcdir = builder_params.get("srcdir")
    src_dir = copy_srcdir_to_tmpdir(srcdir, sphinx_test_tempdir)
    parent_path = Path(str(src_dir.parent.abspath()))

    if version_info >= (7, 2):
        src_dir = Path(str(src_dir))

    # return sphinx.testing fixture make_app and new srcdir which is in sphinx_test_tempdir
    app: SphinxTestApp = make_app(
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
    # Add the Sphinx warning as list to the app
    # Somehow "app._warning" seems to be just a boolean, if the builder is "latex" or "singlehtml".
    # In this case we don't catch the warnings.
    if builder_params.get("buildername", "html") == "html":
        app.warning_list = strip_colors(
            app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
        ).splitlines()
    else:
        app.warning_list = None

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

    app.cleanup()

    # Clean up the srcdir of each Sphinx app after the test function has executed
    if request.config.getoption("--sn-build-dir") is None:
        shutil.rmtree(parent_path, ignore_errors=True)


class DoctreeSnapshotExtension(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    _file_extension = "doctree.xml"

    def serialize(self, data, **kwargs):
        if not isinstance(data, document):
            raise TypeError(f"Expected document, got {type(data)}")
        doc = data.deepcopy()
        doc["source"] = "<source>"  # this will be a temp path
        doc.attributes.pop("translation_progress", None)  # added in sphinx 7.1
        return doc.pformat()


@pytest.fixture
def snapshot_doctree(snapshot):
    """Snapshot fixture for doctrees.

    Here we try to sanitize the doctree, to make the snapshots reproducible.
    """
    try:
        return snapshot.with_defaults(extension_class=DoctreeSnapshotExtension)
    except AttributeError:
        # fallback for older versions of pytest-snapshot
        return snapshot.use_extension(DoctreeSnapshotExtension)
