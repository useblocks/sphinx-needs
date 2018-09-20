import re

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/add_sections')
def test_section_is_usable_in_filters(app, status, warning):
    app.builder.build_all()
    html = Path(app.outdir, 'index.html').read_text()

    tables = re.findall("(<table .*?</table>)", html, re.DOTALL)
    assert len(tables) == 2

    # All requirements should be in first table
    assert 'R_12345' in tables[0]
    assert 'First Section' in tables[0]
    assert 'R_12346' in tables[0]
    assert 'Second Section' in tables[0]

    # Only requirements from the first section should be in table 2
    assert 'R_12345' in tables[1]
    assert 'First Section' in tables[1]
    assert 'R_12346' not in tables[1]
    assert 'Second Section' not in tables[1]