import os
import tempfile

import sphinx


def test_file_registration():
    """
    Tests a build via the Sphinx Build API.
    """
    temp_dir = tempfile.mkdtemp()
    src_dir = os.path.join(os.path.dirname(__file__), "../doc_test/doc_style_modern")

    with open(os.path.join(temp_dir, "warnings.txt"), "w") as warnings:
        sphinx_app = sphinx.application.Sphinx(
            srcdir=src_dir,
            confdir=src_dir,
            outdir=temp_dir,
            doctreedir=temp_dir,
            buildername="html",
            parallel=4,
            warning=warnings,
        )

        # 1. Build
        sphinx_app.build()

        # Only check Sphinx-Needs files
        css_files = [x for x in sphinx_app.builder.css_files if x.startswith("_static/sphinx-needs")]
        script_files = [x for x in sphinx_app.builder.script_files if x.startswith("_static/sphinx-needs")]
        css_run_1 = len(css_files)
        script_run_1 = len(script_files)

        # Check for duplicates
        assert css_run_1 == len(set(css_files))
        assert script_run_1 == len(set(script_files))

        assert sphinx_app.statuscode == 0

        # 2. Build
        sphinx_app.build()

        # Only check Sphinx-Needs files
        css_files = [x for x in sphinx_app.builder.css_files if x.startswith("_static/sphinx-needs")]
        script_files = [x for x in sphinx_app.builder.script_files if x.startswith("_static/sphinx-needs")]
        css_run_2 = len(css_files)
        script_run_2 = len(script_files)

        # Check for duplicates
        assert css_run_2 == len(set(css_files))
        assert script_run_2 == len(set(script_files))

        assert sphinx_app.statuscode == 0
        assert css_run_1 == css_run_2
        assert script_run_1 == script_run_2
