:hide-navigation:

Parsers
=======

``Sphinx-Test-Reports`` provides different parsers for test result files.
One for **XML-files**, following the **JUnit** format, and one for
generic **JSON-files**, which are not following any standard.

The needed parser is automatically selected by the file extensions ``xml`` or ``json``.

Junit Parser
------------
This parser reads **xml** files and handles the content as **JUnit** data.
Other XML formats are not supported.

As **JUnit** format is not really standardized, different test framework produce slightly different JUnit xml files.
``Sphinx-Test-Reports`` supports the "dialects" of:

* pytest
* GoogleTest
* CasperJS

There is a high chance, that other tet frameworks are supported as well, as long as they provide a Junit file.

.. _json_parser:

JSON Parser
-----------

The JSON parser can read any JSON file. But as the data structure is not following any standard, the user need to
provide a mapping between the used JSON structure and the internal structure used by ``Sphinx-Test-Reports``.

Even if this means some more configuration effort, the benefit is a completely customizable data structure.

For an example please take a look into :ref:`json_example`.

For mapping configuration please see :ref:`tr_json_mapping`.


Technical details
-----------------
Each parser is realized by a class, which needs to provide specific functions.
Also the internal object representation is the same. So each parser must map the external format to the internal
representation.

Only the parser cares about the format. Other internal functions (like directives) just work with the common
data representation and rely on it.
So parsers are not allowed to rename or even extend this internal representation.
If this is needed, all available parsers need to be updated as well.
