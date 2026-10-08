"""The readers' shared error type."""


class ReportReadError(Exception):
    """The report exists and cannot be read.

    Raised by both readers. The JUnit reader: the file is not well-formed XML (the
    message is the path, lxml's line and column, then lxml's sentence), its bytes are not
    valid in its encoding, or a numeric attribute of a ``<testsuite>`` / ``<testcase>`` is
    not a number (the message names the element, the attribute and the value). The JSON
    reader: the file is not UTF-8, not valid JSON (the path, the line and column, then
    the decoder's sentence), or not a list of test suites. The message always starts
    with the path.
    """
