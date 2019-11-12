from sphinx.errors import SphinxError


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
