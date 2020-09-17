import sys
import sphinx
import urllib
from pkg_resources import parse_version

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging
    logging.basicConfig()  # Only need to do this once


try:
    from sphinx.errors import NoUri  # Sphinx 3.0
except ImportError:
    from sphinx.environment import NoUri  # Sphinx < 3.0

if sys.version_info < (3,0):
    urlParse = urllib.quote_plus
else:
    urlParse = urllib.parse.quote_plus