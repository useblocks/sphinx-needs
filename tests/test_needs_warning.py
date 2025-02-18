import os
from pathlib import Path

import pytest
from sphinx import version_info
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needs_warnings",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_needs_warnings(test_app):
    app = test_app
    app.build()

    # stdout warnings
    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()

    expected = [
        "WARNING: 'invalid_status' in 'needs_warnings' is already registered. [needs.config]",
        "WARNING: api_warning_filter: failed",
        "\t\tfailed needs: 1 (TC_002)",
        "\t\tused filter: status == 'example_2' [needs.warnings]",
        "WARNING: api_warning_func: failed",
        "\t\tfailed needs: 1 (TC_003)",
        "\t\tused filter: custom_warning_func [needs.warnings]",
        "WARNING: invalid_status: failed",
        "\t\tfailed needs: 2 (SP_TOO_001, US_63252)",
        "\t\tused filter: status not in ['open', 'closed', 'done', 'example_2', 'example_3'] [needs.warnings]",
        "WARNING: type_match: failed",
        "\t\tfailed needs: 1 (TC_001)",
        "\t\tused filter: my_custom_warning_check [needs.warnings]",
    ]

    if version_info >= (8, 2):
        expected.insert(
            1,
            "WARNING: cannot cache unpickleable configuration value: 'needs_warnings' (because it contains a function, class, or module object) [config.cache]",
        )
    elif version_info >= (8, 0):
        expected.insert(
            1,
            "WARNING: cannot cache unpickable configuration value: 'needs_warnings' (because it contains a function, class, or module object) [config.cache]",
        )
    elif version_info >= (7, 3):
        expected.insert(
            1,
            "WARNING: cannot cache unpickable configuration value: 'needs_warnings' (because it contains a function, class, or module object)",
        )

    assert warnings == expected


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needs_warnings_return_status_code",
        }
    ],
    indirect=True,
)
def test_needs_warnings_return_status_code(test_app):
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    # Check return code when "-W --keep-going" not used
    out_normal = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )
    assert out_normal.returncode == 0

    # Check return code when only "-W" is used
    out_w = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir, "-W"], capture_output=True
    )
    assert out_w.returncode >= 1

    # Check return code when only "--keep-going" is used
    out_keep_going = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir, "--keep-going"],
        capture_output=True,
    )
    assert out_keep_going.returncode == 0

    # Check return code when "-W --keep-going" is used
    out_w_keep_going = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir, "-W", "--keep-going"],
        capture_output=True,
    )
    assert out_w_keep_going.returncode == 1

    # Check no Sphinx raised warnings
    assert "WARNING" not in out_w_keep_going.stdout.decode("utf-8")

    warnings = out_w_keep_going.stderr.decode("utf-8")

    # Check Sphinx-needs raised warnings amount
    assert warnings.count("WARNING: ") == 2

    # Check warnings contents
    assert "WARNING: invalid_status: failed" in warnings
    assert "failed needs: 2 (SP_TOO_001, US_63252)" in warnings
    assert (
        "used filter: status not in ['open', 'closed', 'done', 'example_2', 'example_3']"
        in warnings
    )

    # Check needs warning from custom defined filter code
    assert "WARNING: type_match: failed" in warnings
    assert "failed needs: 1 (TC_001)" in warnings
    assert "used filter: my_custom_warning_check" in warnings
