"""The extension loads, and declares what Sphinx needs to know about it."""

from __future__ import annotations

import sphinx_ub_directives


def test_the_extension_is_parallel_safe() -> None:
    metadata = sphinx_ub_directives.setup(object())
    assert metadata["parallel_read_safe"] is True
    assert metadata["version"] == sphinx_ub_directives.__version__
