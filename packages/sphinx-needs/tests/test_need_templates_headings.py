"""A heading in a need's pre or post template output opens a section in place.

sphinx-needs parses pre/post output with titles allowed, and documents that a
``pre_template`` can set a section heading before each need. On a reStructuredText page
the section is opened where the output is: a sub-section of the page's section, before
the need. On a MyST page it used to be appended to the page's section of the level
above, so it landed AFTER the need (and its post output), as a sibling of the section
the need is in. Both markups now open it in place.

The conformance corpus pins where a need inside such a section lands
(``pre-template-heading-opens-a-section-in-place``); this pins the ORDER, which
``needs.json`` cannot show.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from docutils import nodes

from sphinx_needs.nodes import Need

CONF = 'extensions = ["sphinx_needs", "myst_parser"]\n'

INDEX = """\
Top
===

.. toctree::

   page

Section A
---------

.. req:: On RST
   :id: REQ_R
   :pre_template: hrst
   :post_template: postrst

   Body.

.. req:: After
   :id: AFTER_R
"""

PAGE = """\
# MD page

## MD section

```{req} On MyST
:id: REQ_M
:pre_template: hmd
:post_template: postmd

Body.
```

```{req} After
:id: AFTER_M
```
"""

FILES = [
    (Path("conf.py"), CONF),
    (Path("index.rst"), INDEX),
    (Path("page.md"), PAGE),
    (Path("needs_templates", "hrst.need"), "Pre {{ id }}\n~~~~~~~~~~~~\n\npre text\n"),
    (Path("needs_templates", "hmd.need"), "### Pre {{ id }}\n\npre text\n"),
    (Path("needs_templates", "postrst.need"), "Post {{ id }}\n~~~~~~~~~~~~~\n"),
    (Path("needs_templates", "postmd.need"), "### Post {{ id }}\n"),
]


def _need(doctree: nodes.document, need_id: str) -> Need:
    return next(n for n in doctree.findall(Need) if need_id in n["ids"])


def _titled(doctree: nodes.document, title: str) -> nodes.section:
    return next(
        s
        for s in doctree.findall(nodes.section)
        if s.next_node(nodes.title).astext() == title
    )


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "files": FILES}], indirect=True
)
@pytest.mark.parametrize(
    ("docname", "need_id", "section"),
    [("index", "REQ_R", "Section A"), ("page", "REQ_M", "MD section")],
)
def test_a_pre_template_heading_opens_its_section_before_the_need(
    test_app: Any, docname: str, need_id: str, section: str
) -> None:
    app = test_app
    app.build()
    doctree = app.env.get_doctree(docname)
    need = _need(doctree, need_id)
    pre = _titled(doctree, f"Pre {need_id}")
    post = _titled(doctree, f"Post {need_id}")
    host = _titled(doctree, section)
    # both sections are children of the page's section the need is in, in place
    assert need.parent is host
    assert pre.parent is host
    assert post.parent is host
    order = host.children
    assert order.index(pre) < order.index(need) < order.index(post)
    # the next need follows the post output, as it is written after the first
    after = _need(doctree, "AFTER_R" if docname == "index" else "AFTER_M")
    assert after.parent is host
    assert order.index(post) < order.index(after)
