from sphinx.errors import SphinxError, SphinxWarning


class TestReportFileNotSetException(SphinxError):
    """
    Raised if a needed test_file path is not given in directive.
    """


class TestReportFileInvalidException(SphinxError):
    """
    Raised if the given path is not valid.
    """


class TestReportInvalidOption(SphinxError):
    """
    Raised if an option is not given or invalid.
    """


class TestReportIncompleteConfiguration(SphinxWarning):
    """
    Raised if given arguments / options are not correct configured
    """


class InvalidConfigurationError(SphinxError):
    """
    Raised if wrong values given in conf.py
    """
