from pathlib import Path

import pytest
from sphinx import version_info
from sphinx.application import Sphinx
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_warning", "no_plantuml": True}],
    indirect=True,
)
def test_proper_warning(test_app: Sphinx):
    test_app.build()

    warnings = strip_colors(test_app._warning.getvalue()).splitlines()
    prefix = " [docutils]" if version_info >= (8, 0) else ""
    assert warnings == [
        f'{Path(str(test_app.srcdir)) / "index.rst"}:9: ERROR: Unknown interpreted text role "unknown0".{prefix}',
        f'{Path(str(test_app.srcdir)) / "index.rst"}:16: ERROR: Unknown interpreted text role "unknown1".{prefix}',
        f'{Path(str(test_app.srcdir)) / "index.rst"}:24: ERROR: Unknown interpreted text role "unknown2".{prefix}',
        f'{Path(str(test_app.srcdir)) / "index.rst"}:31: ERROR: Unknown interpreted text role "unknown3".{prefix}',
        f'{Path(str(test_app.srcdir)) / "index.rst"}:6: ERROR: Unknown interpreted text role "unknown4".{prefix}',
    ]

    html = Path(test_app.outdir, "index.html").read_text(encoding="utf8")
    assert 'href="#SP_TOO_000" title="SP_TOO_000">SP_TOO_000' in html
    assert 'href="#SP_TOO_001" title="SP_TOO_001">SP_TOO_001' in html
    assert 'href="#SP_TOO_002" title="SP_TOO_002">SP_TOO_002' in html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_warning",
            "no_plantuml": True,
            "confoverrides": {"rst_prolog": ".. |drift| replace:: drift\n"},
        }
    ],
    indirect=True,
)
def test_proper_warning_is_unaffected_by_rst_prolog(test_app: Sphinx):
    """The same document, built with a prolog in front of it, warns in the same places.

    Sphinx prepends ``rst_prolog`` to every document it parses, so the parser's own line
    numbers no longer line up with the file's. Nothing a reader sees should move because
    of that: the five lines below are the ones :func:`test_proper_warning` asserts,
    repeated deliberately rather than shared, because "the same locations, on a document
    whose line counter has been shifted" is the whole claim.

    Two of the five are the interesting ones. ``unknown0`` and ``unknown4`` come from
    ``:pre_template:``/``:post_template:`` content, which exists in no file at all and is
    therefore anchored at the need's own directive; that anchor is an offset into the
    parser's shifted line space, so it has to be given in those coordinates rather than
    in the resolved ones a need now records (see #1349).
    """
    test_app.build()

    warnings = strip_colors(test_app._warning.getvalue()).splitlines()
    prefix = " [docutils]" if version_info >= (8, 0) else ""
    assert warnings == [
        f'{Path(str(test_app.srcdir)) / "index.rst"}:9: ERROR: Unknown interpreted text role "unknown0".{prefix}',
        f'{Path(str(test_app.srcdir)) / "index.rst"}:16: ERROR: Unknown interpreted text role "unknown1".{prefix}',
        f'{Path(str(test_app.srcdir)) / "index.rst"}:24: ERROR: Unknown interpreted text role "unknown2".{prefix}',
        f'{Path(str(test_app.srcdir)) / "index.rst"}:31: ERROR: Unknown interpreted text role "unknown3".{prefix}',
        f'{Path(str(test_app.srcdir)) / "index.rst"}:6: ERROR: Unknown interpreted text role "unknown4".{prefix}',
    ]
