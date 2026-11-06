from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import add_need

extensions = ["sphinx_needs"]


def _part(part_id):
    return {"id": part_id, "content": f"given {part_id}"}


# each case: the need's id, then what ``add_need`` is given besides it
CASES = {
    # content marks no part: both given parts are dropped
    "plain": (
        "ADD_PLAIN",
        {"content": "Plain content.", "parts": {"bp": _part("bp"), "ap": _part("ap")}},
    ),
    # content marks another part: the given one is dropped, the content's is kept
    "marks_other": (
        "ADD_MARKS_OTHER",
        {"content": "Has :np:`(cp)content cp`.", "parts": {"ap": _part("ap")}},
    ),
    # content marks the given id: the id is kept, with the content's text
    "marks_same": (
        "ADD_MARKS_SAME",
        {"content": "Has :np:`(ap)content ap`.", "parts": {"ap": _part("ap")}},
    ),
    # a hidden need is not rendered, so its content is not re-read for parts
    "hidden": (
        "ADD_HIDDEN",
        {"content": "Plain.", "hide": True, "parts": {"ap": _part("ap")}},
    ),
    # an external need has no node, so its content is not re-read for parts
    "external": (
        "ADD_EXTERNAL",
        {
            "content": "Plain.",
            "is_external": True,
            "external_url": "https://example.org/x.html#ADD_EXTERNAL",
            "parts": {"ap": _part("ap")},
        },
    ),
    # nothing given, nothing dropped
    "empty": ("ADD_EMPTY", {"content": "Plain.", "parts": {}}),
}


class AddNeedParts(SphinxDirective):
    """Call ``add_need`` with ``parts``, for one of the cases above."""

    required_arguments = 1

    def run(self):
        need_id, kwargs = CASES[self.arguments[0]]
        return add_need(
            self.env.app,
            self.state,
            self.env.docname,
            self.lineno,
            "req",
            self.arguments[0],
            id=need_id,
            **kwargs,
        )


def setup(app):
    app.add_directive("add-need-parts", AddNeedParts)
