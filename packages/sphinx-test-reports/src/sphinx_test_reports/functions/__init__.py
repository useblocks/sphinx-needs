from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sphinx.application import Sphinx

    from sphinx_needs.data import NeedsMutable
    from sphinx_needs.need_item import NeedItem, NeedPartItem
    from sphinx_needs.views import NeedsView


def tr_link(
    app: Sphinx,
    need: NeedItem | NeedPartItem | None,
    needs: NeedsView | NeedsMutable,
    test_option: str,
    target_option: str,
    *args: Any,
    **kwargs: Any,
) -> list[str]:
    # Guard on the VALUE, not the key: the test fields are registered on every need, so
    # the key is present on a need that is not a test-case too, with the value `None`.
    # No links is the empty LIST: an empty string is read as one link to the id `""`,
    # which sphinx-needs reports as a dead outgoing link.
    if need is None:
        # A call outside a need still fails, as the `None.get` it used to reach did;
        # sphinx-needs reports either as the function's error.
        raise ValueError("No need given for tr_link")
    test_value = need.get(test_option)
    if not test_value:
        return []

    # Allow for multiple values in option
    test_opt_values = test_value.split(",")

    links = []
    for need_target in needs.values():
        # the same on the target side: a need whose target option is unset is no target
        target_value = need_target.get(target_option)
        if not target_value:
            continue
        for test_opt_raw in test_opt_values:
            test_opt = test_opt_raw.strip()
            if test_opt == target_value and len(test_opt) > 0:
                links.append(need_target["id"])

    return links


# What a call reads, for sphinx-needs to compute it in order, like a built-in function:
# `test_option` of its own need, and `target_option` of every need (`id` is computed by
# nothing). An attribute, not `sphinx_needs.api.reads`, so that a sphinx-needs older
# than the declaration (9.0.0, the floor) simply ignores it.
vars(tr_link)["needs_reads"] = lambda test_option, target_option, *args, **kwargs: {
    "own": [test_option],
    "every": [target_option],
}
