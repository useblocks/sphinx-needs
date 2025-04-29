"""Reset Sphinx Needs to on-disk state."""

from sphinx_needs.config import _NEEDS_CONFIG
from sphinx_needs.directives.need import NeedDirective
from sphinx_needs.directives.needbar import NeedbarDirective
from sphinx_needs.directives.needextend import NeedextendDirective
from sphinx_needs.directives.needextract import NeedextractDirective
from sphinx_needs.directives.needgantt import NeedganttDirective
from sphinx_needs.directives.needimport import NeedimportDirective
from sphinx_needs.directives.needlist import NeedlistDirective
from sphinx_needs.directives.needpie import NeedpieDirective
from sphinx_needs.directives.needreport import NeedReportDirective
from sphinx_needs.directives.needsequence import NeedsequenceDirective
from sphinx_needs.directives.needservice import NeedserviceDirective
from sphinx_needs.directives.needtable import NeedtableDirective
from sphinx_needs.directives.needuml import NeedumlDirective


def reset_directives() -> None:
    """Reset modifications of Sphinx-Needs directive classes."""
    # sorted by order of dependency, e.g. NeedDirective is used in NeedserviceDirective
    directives = [
        NeedDirective,
        NeedbarDirective,
        NeedextendDirective,
        NeedextractDirective,
        NeedganttDirective,
        NeedimportDirective,
        NeedlistDirective,
        NeedpieDirective,
        NeedReportDirective,
        NeedsequenceDirective,
        NeedserviceDirective,
        NeedtableDirective,
        NeedumlDirective,
    ]
    for directive in directives:
        if hasattr(directive, "reset"):
            NeedDirective.reset()


def sphinx_needs_reset() -> None:
    """
    Reset Sphinx Needs runtime modifications.

    This is required for consecutive test case executions that run in the same interpreter.
    Each test case should start with a clean SN state.

    Call this after build execution or before setup() has run.
    """
    # also called at the end of setup()
    _NEEDS_CONFIG.clear()

    reset_directives()
