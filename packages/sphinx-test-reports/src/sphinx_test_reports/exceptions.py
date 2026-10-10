from sphinx.errors import SphinxError, SphinxWarning


class TestReportFileNotSetError(SphinxError):
    """
    Raised if a needed test_file path is not given in directive.

    Not raised by the directives since 3.0 (a located ``test_reports.*`` warning
    instead); kept for ``except`` clauses.
    """


class TestReportFileInvalidError(SphinxError):
    """
    Raised if the given path is not valid.
    """


class TestReportInvalidOptionError(SphinxError):
    """
    Raised if an option is not given or invalid.

    Not raised by the directives since 3.0 (a located ``test_reports.*`` warning
    instead); kept for ``except`` clauses.
    """


class TestReportIncompleteConfigurationError(SphinxWarning):
    """
    Raised if given arguments / options are not correct configured

    Not raised by the directives since 3.0 (a located ``test_reports.*`` warning
    instead); kept for ``except`` clauses.
    """


class InvalidConfigurationError(SphinxError):
    """
    Raised if wrong values given in conf.py
    """
