"""
Reset Sphinx Needs runtime modifications.

This is a dedicated module to avoid circular imports.
"""

from sphinx_needs.config import _NEEDS_CONFIG
from sphinx_needs.directives.need import NeedDirective
from sphinx_needs.directives.needextend import NeedextendDirective
from sphinx_needs.directives.needservice import NeedserviceDirective


def sphinx_needs_reset() -> None:
    """
    Reset Sphinx Needs runtime modifications.

    Problem is that Sphinx-Needs modifies the `option_spec` directive class attributes.

    This is a problem for consecutive test case executions that run in the same interpreter.
    Each test case should start with a clean SN state.

    Call this after build execution or before setup() has run.
    """
    # also called at the end of setup()
    _NEEDS_CONFIG.clear()

    NeedDirective.reset_options_spec()
    NeedextendDirective.reset_options_spec()
    NeedserviceDirective.reset_options_spec()
