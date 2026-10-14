from types import SimpleNamespace

import pytest

from sphinx_needs.diagrams_common import calculate_link


@pytest.mark.parametrize("docname", [None, ""])
def test_calculate_link_need_without_document(docname):
    """A need with neither an external url nor a document gets no link.

    ``add_need`` takes ``docname=None``, so such a need exists; drawing it in a needflow
    or needuml reached ``return link`` with ``link`` never bound, an ``UnboundLocalError``
    that ended the build. ``calculate_link`` reads only these two keys on this path, and
    nothing of the builder.
    """
    need = {"is_external": False, "docname": docname}
    assert calculate_link(SimpleNamespace(builder=None), need, None) == ""
