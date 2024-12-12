from pathlib import Path

import pytest
import json

from sphinx_needs.api import get_needs_view




@pytest.mark.parametrize(
    "test_app",
     [{"buildername": "html", "srcdir": "doc_test/doc_list2need_hide"}],
    indirect=True,
)
def test_doc_list2need_hide(test_app, snapshot):
    """
    The test validates the list2need directive with the hide option.
    The needs must be valid, but the rendered output must not contain the need content.
    
    To validate that the needs are valid, the needs are rendered using a needtable directive.
    """
    app = test_app
    app.build()



    index_html = Path(app.outdir, "index.html").read_text()
    assert '<tr class="need row-even"><td class="needs_id"><p><a class="reference internal" href="#NEED-A">NEED-A</a></p></td>' in index_html
    assert '<tr class="need row-odd"><td class="needs_id"><p><a class="reference internal" href="#NEED-B">NEED-B</a></p></td>' in index_html
    assert '<tr class="need row-even"><td class="needs_id"><p><a class="reference internal" href="#NEED-C">NEED-C</a></p></td>' in index_html
    
    
    assert 'class="need_container docutils container"' not in index_html
    
        
    
    
    
    