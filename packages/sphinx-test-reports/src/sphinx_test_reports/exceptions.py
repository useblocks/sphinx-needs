from sphinx.errors import SphinxError, SphinxWarning


class TestReportFileNotSetError(SphinxError):
    """
    Raised if a needed test_file path is not given in directive.
    """


class TestReportFileInvalidError(SphinxError):
    """
    Raised if the given path is not valid.
    """


class TestReportInvalidOptionError(SphinxError):
    """
    Raised if an option is not given or invalid.
    """


class TestReportIncompleteConfigurationError(SphinxWarning):
    """
    Raised if given arguments / options are not correct configured
    """


class InvalidConfigurationError(SphinxError):
    """
    Raised if wrong values given in conf.py
    """
