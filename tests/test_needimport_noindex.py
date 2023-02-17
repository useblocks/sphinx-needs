import os
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app", [{"buildername": "latex", "srcdir": "doc_test/doc_needimport_noindex"}], indirect=True
)
def test_doc_needimport_noindex(test_app):
    app = test_app
    app.build()

    latex_path = str(Path(app.outdir, "needstestdocs.tex"))
    latex = Path(latex_path).read_text()
    print(f"in path {app.outdir}", sys.stderr)

    assert os.path.exists(latex_path)
    assert 0 < len(latex)
    assert "AAA" in latex
